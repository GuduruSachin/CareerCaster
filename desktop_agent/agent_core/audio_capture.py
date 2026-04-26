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
    def __init__(self, target_rate=16000, chunk_size=1024):
        self.target_rate = target_rate
        self.chunk_size = chunk_size
        self.pa = pyaudio.PyAudio()
        
        self.interviewer_queue = queue.Queue()
        self.user_queue = queue.Queue()
        
        # VU Meter "Taps" - Holds current max level for the meter
        self.interviewer_level = 0
        self.user_level = 0
        
        self.is_running = False
        self.streams = []
        self.itv_rate = target_rate
        self.user_rate = target_rate

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
        Starts audio capture streams using hardware's native rate and resampling to target rate.
        """
        self.is_running = True
        
        # 1. Interviewer Source (Loopback/Speakers)
        itv_target = interviewer_idx if (interviewer_idx is not None and interviewer_idx != -1) else self.find_wasapi_loopback()
        
        if itv_target is not None and itv_target != -1:
            try:
                itv_info = self.pa.get_device_info_by_index(itv_target)
                self.itv_rate = int(itv_info.get('defaultSampleRate', 44100))
                
                self.streams.append(self.pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.itv_rate,
                    input=True,
                    input_device_index=itv_target,
                    frames_per_buffer=self.chunk_size,
                    stream_callback=self._interviewer_callback
                ))
                print(f"[+] Interviewer capture started on device {itv_target} at {self.itv_rate}Hz")
            except Exception as e:
                self._handle_stream_error("Interviewer", e)

        # 2. User Source (Microphone)
        mic_target = user_idx if user_idx != -1 else None # If None, PyAudio uses system default
        
        try:
            if mic_target is None:
                try:
                    default_input = self.pa.get_default_input_device_info()
                    mic_target = default_input['index']
                except Exception as e:
                    print(f"[!] WARNING: No default microphone found: {e}")
                    mic_target = None

            if mic_target is not None:
                mic_info = self.pa.get_device_info_by_index(mic_target)
                self.user_rate = int(mic_info.get('defaultSampleRate', 44100))
                
                self.streams.append(self.pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.user_rate,
                    input=True,
                    input_device_index=mic_target,
                    frames_per_buffer=self.chunk_size,
                    stream_callback=self._user_callback
                ))
                print(f"[+] User capture started on device {mic_target} at {self.user_rate}Hz")
            else:
                print("[!] User capture disabled: No valid input device.")
        except Exception as e:
            self._handle_stream_error("User", e)

    def _handle_stream_error(self, source, error):
        print(f"[!] {source} stream failed: {error}")
        if "-9997" in str(error):
            print(f"[ADVICE] Error -9997 (Invalid Sample Rate) detected for {source}. Suggestion: Disable 'Exclusive Mode' in Windows Sound Settings for this device.")

    def _resample(self, audio_data, orig_rate):
        """DSP Resampling Layer: Downsamples hardware audio to exactly 16kHz."""
        if orig_rate == self.target_rate:
            return audio_data
        
        duration = len(audio_data) / orig_rate
        target_size = int(duration * self.target_rate)
        
        # Using numpy.interp (Linear Interpolation) for high-fidelity resampling
        return np.interp(
            np.linspace(0, duration, target_size),
            np.linspace(0, duration, len(audio_data)),
            audio_data
        ).astype(np.float32)

    def _calculate_level(self, audio_data, source_type='system'):
        """
        Calculates 0-100 normalized signal level with source-specific gain compensation.
        """
        rms = np.sqrt(np.mean(np.square(audio_data)))
        multiplier = 1000 if source_type == 'mic' else 400
        return min(int(rms * multiplier), 100)

    def _interviewer_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        self.interviewer_level = self._calculate_level(audio_data, source_type='system')
        
        resampled_data = self._resample(audio_data, self.itv_rate)
        self.interviewer_queue.put(resampled_data)
        return (None, pyaudio.paContinue)

    def _user_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
        self.user_level = self._calculate_level(audio_data, source_type='mic')
        
        resampled_data = self._resample(audio_data, self.user_rate)
        self.user_queue.put(resampled_data)
        return (None, pyaudio.paContinue)

    def stop_capture(self):
        self.is_running = False
        for s in self.streams:
            try:
                s.stop_stream()
                s.close()
            except: pass
        self.streams = []
