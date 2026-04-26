import os
import sys
import numpy as np
import logging
import threading

LOGGER = logging.getLogger("CareerCaster")

# Lazy loading to prevent start-up hang
_WHISPER_MODEL = None
_VAD_MODEL = None
_TORCH = None

class STTService:
    """
    CareerCaster Local Transcription Engine.
    Uses faster-whisper with VAD for low-latency interview capture.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(STTService, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, model_size="distil-small.en"):
        if self.initialized:
            return
            
        # Ensure we have the global refs if they were already loaded by another thread/call
        self.model = _WHISPER_MODEL
        self.vad_model = _VAD_MODEL
        
        if self.model and self.vad_model:
            self.initialized = True
            return

        # Use a background thread for the actual heavy lifting
        threading.Thread(target=self._initialize_core, args=(model_size,), daemon=True).start()

    def _initialize_core(self, model_size):
        global _WHISPER_MODEL, _VAD_MODEL, _TORCH
        
        try:
            import torch
            from faster_whisper import WhisperModel
            _TORCH = torch
            
            # CPU optimized with int8
            if _WHISPER_MODEL is None:
                LOGGER.info(f"[*] Core Loading: Whisper Model ({model_size})...")
                _WHISPER_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")
            
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_dir = sys._MEIPASS
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
            model_path = os.path.join(base_dir, "models", "silero_vad.jit")
            
            if os.path.exists(model_path) and _VAD_MODEL is None:
                LOGGER.info("[*] Core Loading: VAD Model...")
                _VAD_MODEL = _TORCH.jit.load(model_path, map_location='cpu')
                _VAD_MODEL.eval()
                
            # Update the singleton instance properties
            self.model = _WHISPER_MODEL
            self.vad_model = _VAD_MODEL
            self.initialized = True
            LOGGER.info("[+] STT Core Ready.")
        except Exception as e:
            LOGGER.error(f"STT Initialization Failed: {e}")
            # Even on failure, mark as initialized to avoid re-triggering broken thread
            self.initialized = True 


    def transcribe_segment(self, audio_np):
        """Transcribes a single NumPy audio segment."""
        # Check global first in case it finished in the background
        if not self.model: self.model = _WHISPER_MODEL
        if not self.model: return ""
        
        try:
            segments, info = self.model.transcribe(audio_np, beam_size=5, language="en")
            text = " ".join([s.text for s in segments]).strip()
            return text
        except Exception as e:
            LOGGER.error(f"Transcription error: {e}")
            return ""

    def is_speech(self, audio_np, threshold=0.25):
        """VAD check to see if a segment contains speech."""
        if not self.vad_model: self.vad_model = _VAD_MODEL
        if self.vad_model is None: 
            # If not initialized yet, we can't reliably detect speech.
            # Returning False allows the silence_counter to increment,
            # which will eventually trigger a transcription attempt that will 
            # return "" until the model is ready. This prevents locking the buffer.
            return False 
        
        try:
            audio_tensor = _TORCH.from_numpy(audio_np).unsqueeze(0)
            speech_prob = self.vad_model(audio_tensor, 16000).item()
            
            if speech_prob > threshold:
                return True
        except Exception as e:
            LOGGER.debug(f"VAD calculation error: {e}")
            return False
        return False
