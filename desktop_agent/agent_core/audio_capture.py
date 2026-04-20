import os
import queue
import threading
import numpy as np
import pyaudio

class AudioCaptureEngine:
    """
    CareerCaster 'Stealth Ears' v1.0
    Implements WASAPI Loopback capture for Interviewer (System Output)
    and Standard Mic capture for User (Candidate).
    """
    def __init__(self, sample_rate=16000, chunk_size=1024):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.pa = pyaudio.PyAudio()
        
        self.interviewer_queue = queue.Queue()
        self.user_queue = queue.Queue()
        
        self.is_running = False
        self.streams = []

    def find_wasapi_loopback(self):
        """Finds the WASAPI Loopback device index on Windows."""
        default_host_api = self.pa.get_default_host_api_info()
        found_wasapi = False
        for i in range(self.pa.get_host_api_count()):
            api_info = self.pa.get_host_api_info_by_index(i)
            if "WASAPI" in api_info.get("name", ""):
                found_wasapi = True
                api_index = i
                break
        
        if not found_wasapi:
            return None

        for i in range(self.pa.get_device_count()):
            dev_info = self.pa.get_device_info_by_index(i)
            # Look for loopback/stereo mix/output
            if dev_info.get("hostApi") == api_index and dev_info.get("maxInputChannels") > 0:
                if "loopback" in dev_info.get("name", "").lower():
                    return i
        return None

    def start_capture(self):
        self.is_running = True
        
        # Interviewer Stream (Loopback)
        loopback_idx = self.find_wasapi_loopback()
        if loopback_idx is not None:
            self.streams.append(self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=loopback_idx,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._interviewer_callback
            ))
            
        # User Stream (Mic)
        self.streams.append(self.pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._user_callback
        ))

    def _interviewer_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        self.interviewer_queue.put(audio_data)
        return (None, pyaudio.paContinue)

    def _user_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        self.user_queue.put(audio_data)
        return (None, pyaudio.paContinue)

    def stop_capture(self):
        self.is_running = False
        for s in self.streams:
            s.stop_stream()
            s.close()
        self.pa.terminate()
