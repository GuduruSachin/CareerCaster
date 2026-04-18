import logging
from PyQt6.QtCore import QThread, pyqtSignal

# Import the new Google GenAI SDK
try:
    from google import genai
except ImportError:
    genai = None

LOGGER = logging.getLogger("CareerCaster")

class AIWorker(QThread):
    """
    CareerCaster v1.1 - AI Engine Core.
    Handles real-time streaming tokens from the selected Gemini model.
    """
    token_received = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, prompt, model_name="gemini-3-flash-preview"):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.model_name = model_name

    def run(self):
        if not genai:
            self.error_occurred.emit("Google GenAI SDK not installed.")
            return
        
        if not self.api_key:
            self.error_occurred.emit("API Key missing from session.")
            return

        try:
            client = genai.Client(api_key=self.api_key)
            
            # Requirement 4: System Guardrails
            system_instruction = (
                "You are a professional interview assistant. Your goal is to provide concise, "
                "bullet-pointed technical advice. NEVER use introductory phrases like 'Sure!' or "
                "'Here is the code.' Focus on C# and Angular patterns. Use technical, high-level terminology. "
                "Keep responses brief for quick reading."
            )

            # Requirement 2 & 3: High-Speed Streaming Logic
            for chunk in client.models.generate_content_stream(
                model=self.model_name,
                contents=self.prompt,
                config={'system_instruction': system_instruction}
            ):
                if chunk.text:
                    self.token_received.emit(chunk.text)
            
            self.finished.emit()
        except Exception as e:
            LOGGER.error(f"AIWorker Error: {str(e)}")
            self.error_occurred.emit(str(e))
