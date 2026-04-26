import os
import sys
import numpy as np
import logging

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
            
        global _WHISPER_MODEL, _VAD_MODEL, _TORCH
        
        try:
            import torch
            from faster_whisper import WhisperModel
            _TORCH = torch
        except ImportError as e:
            LOGGER.error(f"STT Dependencies missing: {e}")
            raise
            
        # CPU optimized with int8
        if _WHISPER_MODEL is None:
            LOGGER.info(f"[*] Loading Whisper Model ({model_size})...")
            _WHISPER_MODEL = WhisperModel(model_size, device="cpu", compute_type="int8")
        
        # --- PHASE 3: ZERO-DOWNLOAD ASSET LOADING ---
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        model_path = os.path.join(base_dir, "models", "silero_vad.jit")
        
        if not os.path.exists(model_path):
            LOGGER.error(f"VAD Model missing at {model_path}")
            # Fallback or stub
            self.model = _WHISPER_MODEL
            self.vad_model = None
            self.initialized = True
            return
        
        if _VAD_MODEL is None:
            LOGGER.info("[*] Loading VAD Model...")
            _VAD_MODEL = _TORCH.jit.load(model_path, map_location='cpu')
            _VAD_MODEL.eval()
            
        self.model = _WHISPER_MODEL
        self.vad_model = _VAD_MODEL
        self.initialized = True

    def transcribe_segment(self, audio_np):
        """Transcribes a single NumPy audio segment."""
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
        if self.vad_model is None: return True # Fallback to always-on if VAD failed
        
        try:
            audio_tensor = _TORCH.from_numpy(audio_np).unsqueeze(0)
            speech_prob = self.vad_model(audio_tensor, 16000).item()
            
            if speech_prob > threshold:
                return True
        except Exception as e:
            LOGGER.debug(f"VAD calculation error: {e}")
            return True
        return False
