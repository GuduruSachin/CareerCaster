import time
import threading
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from .audio_capture import AudioCaptureEngine
from .stt_service import STTService

class CareerBridge(QObject):
    """
    The Orchestrator matching audio patterns to AI triggers.
    Ensures zero room-noise interference by splitting loopback vs user mic.
    """
    status_changed = pyqtSignal(str) # 'Listening', 'Transcribing', 'Generating'
    interviewer_text_detected = pyqtSignal(str)
    interviewer_partial_text_detected = pyqtSignal(str)
    
    def __init__(self, interviewer_idx=None, mic_idx=None):
        super().__init__()
        self.audio = AudioCaptureEngine()
        self.stt = STTService()
        
        self.interviewer_idx = interviewer_idx
        self.mic_idx = mic_idx
        
        self.interviewer_buffer = []
        self.user_buffer = []
        
        self.is_active = False
        
        self.silence_counter = 0
        self.SILENCE_THRESHOLD_MS = 2500 # Wait for 2.5s pause to ensure question is complete
        self.CHUNK_DURATION_MS = 64 # based on 1024 chunk / 16000 hz
        self.last_partial_time = 0

    def start(self):
        self.is_active = True
        self.audio.start_capture(
            interviewer_idx=self.interviewer_idx,
            user_idx=self.mic_idx
        )
        threading.Thread(target=self._processing_loop, daemon=True).start()
        self.status_changed.emit("Listening")

    def _processing_loop(self):
        print(f"[*] Audio Pipeline Active. Interviewer IDX: {self.interviewer_idx}")
        while self.is_active:
            # 1. Process Interviewer (Trigger Source)
            while not self.audio.interviewer_queue.empty():
                chunk = self.audio.interviewer_queue.get()
                self.interviewer_buffer.append(chunk)
                
                # Check for VAD in chunk
                if self.stt.is_speech(chunk, threshold=0.015):
                    self.silence_counter = 0
                else:
                    self.silence_counter += self.CHUNK_DURATION_MS
                
                # Periodic partial transcription for live UI feedback
                current_time = time.time()
                if current_time - self.last_partial_time > 1.5 and len(self.interviewer_buffer) > 15:
                    self.last_partial_time = current_time
                    threading.Thread(target=self._handle_partial_segment, args=(list(self.interviewer_buffer),), daemon=True).start()

                # If silence exceeds threshold, finish segment
                if self.silence_counter >= self.SILENCE_THRESHOLD_MS and len(self.interviewer_buffer) > 10:
                    self._handle_interviewer_segment()
            
            # 2. Process User (Sync/History Source)
            # Similar logic for user to prevent echo or duplicate context
            while not self.audio.user_queue.empty():
                chunk = self.audio.user_queue.get()
                self.user_buffer.append(chunk)
            
            time.sleep(0.01)

    def _handle_partial_segment(self, buffer_copy):
        try:
            full_audio = np.concatenate(buffer_copy)
            text = self.stt.transcribe_segment(full_audio)
            if len(text) > 3:
                # We can add a partial_text_detected signal if we want, or just log
                # For now, just logging. Or we will add signal `interviewer_partial_text_detected`
                if hasattr(self, 'interviewer_partial_text_detected'):
                    self.interviewer_partial_text_detected.emit(text)
        except Exception as e:
            pass

    def _handle_interviewer_segment(self):
        print(f"[*] Analyzing Interviewer Segment ({len(self.interviewer_buffer)} chunks)...")
        self.status_changed.emit("Transcribing")
        full_audio = np.concatenate(self.interviewer_buffer)
        text = self.stt.transcribe_segment(full_audio)
        print(f"[*] Transcription Result: '{text}'")
        
        if len(text) > 5:
            print("[+] Triggering AI Response...")
            self.interviewer_text_detected.emit(text)
            self.status_changed.emit("Generating")
            
        self.interviewer_buffer = []
        self.silence_counter = 0
        self.status_changed.emit("Listening")

    def stop(self):
        self.is_active = False
        self.audio.stop_capture()
