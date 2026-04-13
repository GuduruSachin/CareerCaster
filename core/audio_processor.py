import pyaudio
import numpy as np
import wave
import io
import base64
import json
import os
import logging
import logging.handlers
from core.paths import get_logs_dir

# --- API Telemetry Logger Setup ---
LOG_PATH = os.path.join(get_logs_dir(), "api_performance.log")
api_logger = logging.getLogger("api_telemetry")
api_logger.setLevel(logging.INFO)

# Rotating handler: 2MB max, keep 5 backups
if not api_logger.handlers:
    handler = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=2*1024*1024, backupCount=5)
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    api_logger.addHandler(handler)

def log_api_telemetry(persona, char_count, latency, response_s, status):
    """
    Logs API interaction telemetry in a secure, structured format.
    """
    # Truncate response_s to 50 chars for the log
    preview_s = (response_s[:50] + '...') if len(response_s) > 50 else response_s
    preview_s = preview_s.replace('\n', ' ') # Sanitize for single-line log
    
    log_msg = f"[REQUEST] (Persona: {persona}, Context: {char_count} chars) "
    log_msg += f"[RESPONSE] (Latency: {latency:.2f}s, S: \"{preview_s}\") "
    log_msg += f"[STATUS] ({status})"
    
    if latency > 3.0:
        log_msg += " [WARNING: HIGH_LATENCY]"
        
    api_logger.info(log_msg)

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
        rates = [44100, 48000, 16000, 22050, 32000]
        device_index = self.find_wasapi_loopback_device()
        
        for rate in rates:
            try:
                # First check if format is supported
                if self.pa.is_format_supported(
                    rate=rate,
                    input_device=device_index,
                    input_channels=self.channels,
                    input_format=self.format
                ):
                    # Robust Check: Try to actually open the stream to avoid [Errno -9997]
                    test_stream = self.pa.open(
                        format=self.format,
                        channels=self.channels,
                        rate=rate,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=1024
                    )
                    test_stream.close()
                    print(f"Verified compatible sample rate: {rate}Hz")
                    return rate
            except Exception as e:
                print(f"Sample rate {rate}Hz not supported: {e}")
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

    def calculate_rms(self, pcm_data):
        """
        Calculates the Root Mean Square (RMS) energy of PCM data.
        """
        if not pcm_data:
            return 0
        # Convert bytes to int16 array
        audio_data = np.frombuffer(pcm_data, dtype=np.int16)
        if len(audio_data) == 0:
            return 0
        # Calculate RMS
        rms = np.sqrt(np.mean(audio_data.astype(np.float32)**2))
        # Normalize to 0.0 - 1.0 range (approximate for int16)
        return rms / 32768.0

    def get_ai_prompt(self, session_data, persona="Strategic Leadership"):
        """
        Returns the refined AI prompt for Anti-AI Detection Mode.
        """
        resume = session_data.get("resume_text", "")[:4000]
        notes = session_data.get("project_notes", "")[:2000]
        jd = session_data.get("jd_text", "")[:2000]
        tags = session_data.get("context_tags", {})

        persona_guide = ""
        if persona == "Strategic Leadership":
            persona_guide = "Focus on trade-offs, ROI, stakeholder management, and high-level architectural 'Why.' Use 'Human Pivots' like 'The real headache was...' or 'What actually moved the needle was...'"
        else:
            persona_guide = "Focus on the 'How.' Mention specific libraries (OpenCV), protocols (WASAPI), and low-level hurdles (UUID hardware-locking). Use 'Human Pivots' like 'To be fair, we considered...' or 'If I did it again, I'd probably...'"

        return f"""
        ROLE: Senior Architect Mentor (Anti-AI Detection Mode)
        GOAL: Act as a strategic memory-assistant. Provide exactly ONE response per turn.
        {persona_guide}

        1. THE 'HOOK' SYSTEM:
        - Do NOT write full, polished paragraphs.
        - Write in 'Speaker Notes' style: 5-8 word technical 'hooks' or bullet points.
        - This forces the user to bridge the gaps with their own voice.

        2. HUMANIZED LINGUISTICS:
        - Strictly forbid 'robot' transitions: (Firstly, Moreover, In conclusion, Furthermore).
        - Use 'Human Pivots'.

        CANDIDATE CONTEXT:
        - RESUME: {resume}
        - PROJECT NOTES: {notes}
        - JOB DESCRIPTION: {jd}
        - FOCUS TAGS: {json.dumps(tags)}

        DECISION LOGIC:
        1. **Scenario-Based/Experience Questions**: Use STAR segments.
        2. **Technical/Conceptual Questions**: Put the entire answer in 'S' and leave others empty.

        OUTPUT FORMAT:
        Return JSON with keys: 'S', 'T', 'A', 'R', 'ProTip'.
        'ProTip' is a 10-word prediction of the next technical follow-up.

        EXAMPLE JSON:
        {{
          "S": "Legacy monolith scaling bottleneck",
          "T": "Reduce DB contention",
          "A": "Redis caching + Query optimization",
          "R": "50% latency drop",
          "ProTip": "They will ask about cache invalidation strategies next."
        }}
        """

    def recover_stream(self):
        """
        Attempts to re-initialize the PyAudio instance and find the loopback device.
        Used when the stream hits an exception (e.g., device disconnected).
        """
        try:
            self.pa.terminate()
            import time
            time.sleep(2)
            self.pa = pyaudio.PyAudio()
            self.rate = self._detect_best_sample_rate()
            return True
        except Exception as e:
            print(f"Stream Recovery Failed: {e}")
            return False

    def close(self):
        self.pa.terminate()
