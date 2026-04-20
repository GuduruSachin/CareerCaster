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
        
        # --- PHASE 3: ZERO-DOWNLOAD ASSET LOADING ---
        # Reliable pathing for both Development (Hard Drive) and Production (RAM Bundle)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # This is the temporary folder where the EXE extracts assets
            base_dir = sys._MEIPASS
        else:
            # Fallback for standard script execution
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        model_path = os.path.join(base_dir, "models", "silero_vad.jit")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"VAD Model missing. Path checked: {model_path}")
        
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
