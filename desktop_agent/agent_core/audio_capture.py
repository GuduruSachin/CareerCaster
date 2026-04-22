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
        
        # VU Meter "Taps" - Holds current max level for the meter
        self.interviewer_level = 0
        self.user_level = 0
        
        self.is_running = False
        self.streams = []

    def find_wasapi_loopback(self):
        """Finds the WASAPI Loopback device index on Windows."""
        try:
            default_host_api = self.pa.get_default_host_api_info()
        except:
            print("[!] Could not get default host API info.")
            return None

        found_wasapi = False
        api_index = -1
        for i in range(self.pa.get_host_api_count()):
            api_info = self.pa.get_host_api_info_by_index(i)
            if "WASAPI" in api_info.get("name", ""):
                found_wasapi = True
                api_index = i
                break
        
        if not found_wasapi:
            print("[!] WASAPI Host API not found.")
            return None

        for i in range(self.pa.get_device_count()):
            dev_info = self.pa.get_device_info_by_index(i)
            if dev_info.get("hostApi") == api_index:
                name = dev_info.get("name", "")
                inputs = dev_info.get("maxInputChannels")
                if inputs > 0 and "loopback" in name.lower():
                    return i
        return None

    def start_capture(self, interviewer_idx=None, user_idx=None):
        """
        Starts audio capture streams.
        If indices are provided, it uses those. Otherwise, it attempts auto-discovery.
        """
        self.is_running = True
        
        # 1. Interviewer Source (Loopback/Speakers)
        itv_target = interviewer_idx if interviewer_idx is not None else self.find_wasapi_loopback()
        
        if itv_target is not None:
            try:
                self.streams.append(self.pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=itv_target,
                    frames_per_buffer=self.chunk_size,
                    stream_callback=self._interviewer_callback
                ))
                print(f"[+] Interviewer capture started on device {itv_target}")
            except Exception as e:
                print(f"[!] Interviewer stream failed: {e}")

        # 2. User Source (Microphone)
        mic_target = user_idx # If None, PyAudio uses system default
        
        try:
            self.streams.append(self.pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=mic_target,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._user_callback
            ))
            print(f"[+] User capture started on device {mic_target or 'DEFAULT'}")
        except Exception as e:
            print(f"[!] User stream failed: {e}")

    def _calculate_level(self, audio_data, source_type='system'):
        """
        Calculates 0-100 normalized signal level with source-specific gain compensation.
        Laptop mics need higher multipliers; System loopback is naturally loud.
        """
        rms = np.sqrt(np.mean(np.square(audio_data)))
        multiplier = 1000 if source_type == 'mic' else 400
        return min(int(rms * multiplier), 100)

    def _interviewer_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        self.interviewer_level = self._calculate_level(audio_data, source_type='system')
        self.interviewer_queue.put(audio_data)
        return (None, pyaudio.paContinue)

    def _user_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        self.user_level = self._calculate_level(audio_data, source_type='mic')
        self.user_queue.put(audio_data)
        return (None, pyaudio.paContinue)

    def stop_capture(self):
        self.is_running = False
        for s in self.streams:
            s.stop_stream()
            s.close()
        self.pa.terminate()
