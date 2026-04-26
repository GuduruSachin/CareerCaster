import pyaudiowpatch as pyaudio
import logging
import numpy as np

LOGGER = logging.getLogger("CareerCaster")

class AudioScanner:
    """
    Inventory specialist for CareerCaster.
    Enumerates and filters Windows WASAPI devices for high-fidelity capture.
    """
    def __init__(self):
        self.pa = pyaudio.PyAudio()

    def get_wasapi_devices(self):
        """
        Returns a structured list of available WASAPI devices.
        Categories: Inputs (Mics) and Loopback (Speakers).
        """
        devices = {
            "mics": [],
            "loopback": []
        }
        
        try:
            # 1. Identify WASAPI Host API Index
            wasapi_index = -1
            for i in range(self.pa.get_host_api_count()):
                api_info = self.pa.get_host_api_info_by_index(i)
                if "WASAPI" in api_info.get("name", ""):
                    wasapi_index = i
                    break
            
            if wasapi_index == -1:
                LOGGER.error("WASAPI Host API not found on this system.")
                return devices

            # 2. Enumerate all devices under that API
            for i in range(self.pa.get_device_count()):
                dev_info = self.pa.get_device_info_by_index(i)
                if dev_info.get("hostApi") == wasapi_index and dev_info.get("maxInputChannels") > 0:
                    device_data = {
                        "id": i,
                        "name": dev_info.get("name"),
                        "channels": dev_info.get("maxInputChannels"),
                        "rate": int(dev_info.get("defaultSampleRate"))
                    }
                    
                    # Use PyAudioWPatch's native property or fallback to heuristic
                    is_loopback = dev_info.get("isLoopbackDevice", False)
                    name_lower = device_data["name"].lower()
                    
                    if is_loopback or "loopback" in name_lower or "stereo mix" in name_lower:
                        devices["loopback"].append(device_data)
                    else:
                        devices["mics"].append(device_data)
                        
            return devices
            
        except Exception as e:
            LOGGER.error(f"Hardware scan failed: {e}")
            return devices
        # self.pa.terminate() removed to preserve global audio context

    @staticmethod
    def get_signal_level(audio_chunk):
        """Calculates RMS level for VU meters."""
        if len(audio_chunk) == 0: return 0
        rms = np.sqrt(np.mean(np.square(audio_chunk)))
        return min(int(rms * 100 * 5), 100) # Scaled for QProgressBar
