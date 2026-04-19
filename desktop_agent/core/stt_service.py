import os
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
        
        # Load Silero VAD for precise endpointing
        model_vad, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                         model='silero_vad',
                                         force_reload=False)
        self.vad_model = model_vad
        self.get_speech_timestamps = utils[0]

    def transcribe_segment(self, audio_np):
        """Transcribes a single NumPy audio segment."""
        segments, info = self.model.transcribe(audio_np, beam_size=5, language="en")
        text = " ".join([s.text for s in segments]).strip()
        return text

    def is_speech(self, audio_np, threshold=0.5):
        """VAD check to see if a segment contains speech."""
        audio_tensor = torch.from_numpy(audio_np)
        speech_prob = self.vad_model(audio_tensor, 16000).item()
        return speech_prob > threshold
