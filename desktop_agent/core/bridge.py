import time
import threading
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from core.audio_capture import AudioCaptureEngine
from core.stt_service import STTService

class CareerBridge(QObject):
    """
    The Orchestrator matching audio patterns to AI triggers.
    Ensures zero room-noise interference by splitting loopback vs user mic.
    """
    status_changed = pyqtSignal(str) # 'Listening', 'Transcribing', 'Generating'
    interviewer_text_detected = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.audio = AudioCaptureEngine()
        self.stt = STTService()
        
        self.interviewer_buffer = []
        self.user_buffer = []
        
        self.is_active = False
        
        self.silence_counter = 0
        self.SILENCE_THRESHOLD_MS = 500
        self.CHUNK_DURATION_MS = 64 # based on 1024 chunk / 16000 hz

    def start(self):
        self.is_active = True
        self.audio.start_capture()
        threading.Thread(target=self._processing_loop, daemon=True).start()
        self.status_changed.emit("Listening")

    def _processing_loop(self):
        while self.is_active:
            # 1. Process Interviewer (Trigger Source)
            while not self.audio.interviewer_queue.empty():
                chunk = self.audio.interviewer_queue.get()
                self.interviewer_buffer.append(chunk)
                
                # Check for VAD in chunk
                if self.stt.is_speech(chunk):
                    self.silence_counter = 0
                else:
                    self.silence_counter += self.CHUNK_DURATION_MS
                
                # If silence exceeds threshold, finish segment
                if self.silence_counter >= self.SILENCE_THRESHOLD_MS and len(self.interviewer_buffer) > 10:
                    self._handle_interviewer_segment()
            
            # 2. Process User (Sync/History Source)
            # Similar logic for user to prevent echo or duplicate context
            while not self.audio.user_queue.empty():
                chunk = self.audio.user_queue.get()
                self.user_buffer.append(chunk)
            
            time.sleep(0.01)

    def _handle_interviewer_segment(self):
        self.status_changed.emit("Transcribing")
        full_audio = np.concatenate(self.interviewer_buffer)
        text = self.stt.transcribe_segment(full_audio)
        
        if len(text) > 5:
            self.interviewer_text_detected.emit(text)
            self.status_changed.emit("Generating")
            
        self.interviewer_buffer = []
        self.silence_counter = 0
        self.status_changed.emit("Listening")

    def stop(self):
        self.is_active = False
        self.audio.stop_capture()
