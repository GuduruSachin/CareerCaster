import pyaudio
import numpy as np
import wave
import io
import base64

class AudioProcessor:
    def __init__(self, chunk_size=1024):
        self.pa = pyaudio.PyAudio()
        self.chunk_size = chunk_size
        self.format = pyaudio.paInt16
        self.channels = 1 # Mono for transcription
        self.rate = self._detect_best_sample_rate()
        
    def _detect_best_sample_rate(self):
        """
        Tests common sample rates and returns the first one compatible with the hardware.
        """
        rates = [16000, 44100, 48000]
        device_index = self.find_wasapi_loopback_device()
        
        for rate in rates:
            try:
                if self.pa.is_format_supported(
                    rate=rate,
                    input_device=device_index,
                    input_channels=self.channels,
                    input_format=self.format
                ):
                    print(f"Auto-detected compatible sample rate: {rate}Hz")
                    return rate
            except Exception:
                continue
        
        print("Warning: No standard sample rate verified. Defaulting to 16000Hz.")
        return 16000

    def find_wasapi_loopback_device(self):
        """
        Finds the WASAPI loopback device index.
        """
        try:
            # Get default WASAPI host API index
            wasapi_info = None
            for i in range(self.pa.get_host_api_count()):
                info = self.pa.get_host_api_info_by_index(i)
                if info["name"].find("Windows WASAPI") != -1:
                    wasapi_info = info
                    break
            
            if not wasapi_info:
                print("WASAPI Host API not found.")
                return None

            # Look for the loopback device
            for i in range(self.pa.get_device_count()):
                info = self.pa.get_device_info_by_index(i)
                # We look for a device that is an output device but can be used as input (loopback)
                if info["hostApi"] == wasapi_info["index"] and info["maxInputChannels"] > 0:
                    # Usually contains "Loopback" in the name on Windows
                    if "Loopback" in info["name"]:
                        return i
            
            # Fallback: return the first WASAPI device with input channels
            for i in range(self.pa.get_device_count()):
                info = self.pa.get_device_info_by_index(i)
                if info["hostApi"] == wasapi_info["index"] and info["maxInputChannels"] > 0:
                    return i
                    
        except Exception as e:
            print(f"Error finding WASAPI device: {e}")
        return None

    def pcm_to_base64_wav(self, pcm_data):
        """
        Converts raw PCM data to a Base64 encoded WAV file string.
        """
        return base64.b64encode(self.pcm_to_wav_bytes(pcm_data)).decode('utf-8')

    def pcm_to_wav_bytes(self, pcm_data):
        """
        Converts raw PCM data to WAV file bytes.
        """
        with io.BytesIO() as wav_buffer:
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pa.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(pcm_data)
            return wav_buffer.getvalue()

    def close(self):
        self.pa.terminate()
