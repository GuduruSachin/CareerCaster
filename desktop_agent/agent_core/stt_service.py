import os
import sys
import torch
import numpy as np
from faster_whisper import WhisperModel

class STTService:
    """
    CareerCaster Local Transcription Engine.
    Uses faster-whisper with VAD for low-latency interview capture.
    """
    def __init__(self, model_size="distil-small.en"):
        # CPU optimized with int8
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        
        # Load Silero VAD from local directory for offline stability
        # Path Safety: Use _MEIPASS when frozen (PyInstaller bundle root)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        model_path = os.path.join(base_path, "models", "silero_vad.jit")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"VAD Model not found at {model_path}. Please ensure models/silero_vad.jit exists.")
        
        self.vad_model = torch.jit.load(model_path)

    def transcribe_segment(self, audio_np):
        """Transcribes a single NumPy audio segment."""
        segments, info = self.model.transcribe(audio_np, beam_size=5, language="en")
        text = " ".join([s.text for s in segments]).strip()
        return text

    def is_speech(self, audio_np, threshold=0.5):
        """VAD check to see if a segment contains speech."""
        # Hardening: Silero VAD JIT models require a batch dimension [1, samples]
        audio_tensor = torch.from_numpy(audio_np).unsqueeze(0)
        speech_prob = self.vad_model(audio_tensor, 16000).item()
        return speech_prob > threshold
