import logging
import os
import time
from PyQt6.QtCore import QThread, pyqtSignal

# Import the new Google GenAI SDK
try:
    from google import genai
except ImportError:
    genai = None

from core.paths import get_logs_dir

LOGGER = logging.getLogger("CareerCaster")

# --- HIGH-PRECISION AI AUDITOR SETUP ---
def setup_ai_auditor():
    auditor = logging.getLogger("AIAuditor")
    auditor.setLevel(logging.INFO)
    
    logs_dir = get_logs_dir()
    log_file = os.path.join(logs_dir, "ai_transactions.log")
    
    # Format: YYYY-MM-DD HH:MM:SS,mmm - [DIRECTION] - MessageContent
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    
    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    
    # Remove existing handlers if re-initialized
    if auditor.hasHandlers():
        auditor.handlers.clear()
        
    auditor.addHandler(fh)
    auditor.propagate = False # Prevent leaking to main app logger
    return auditor

AUDITOR = setup_ai_auditor()

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

        start_time = time.time()
        full_response = ""

        try:
            client = genai.Client(api_key=self.api_key)
            
            # Requirement 4: System Guardrails
            system_instruction = (
                "You are a professional interview assistant. Your goal is to provide concise, "
                "bullet-pointed technical advice. NEVER use introductory phrases like 'Sure!' or "
                "'Here is the code.' Focus on C# and Angular patterns. Use technical, high-level terminology. "
                "Keep responses brief for quick reading."
            )

            # Audit: Log Outbound Request
            AUDITOR.info(f"[SENT_TO_AI] - System Instruction: {system_instruction}")
            AUDITOR.info(f"[SENT_TO_AI] - User Prompt: {self.prompt}")

            # Requirement 2 & 3: High-Speed Streaming Logic
            for chunk in client.models.generate_content_stream(
                model=self.model_name,
                contents=self.prompt,
                config={'system_instruction': system_instruction}
            ):
                if chunk.text:
                    full_response += chunk.text
                    self.token_received.emit(chunk.text)
            
            # Audit: Log Inbound Response & Metrics
            duration = time.time() - start_time
            AUDITOR.info(f"[RECEIVED_FROM_AI] - Full Response: {full_response}")
            AUDITOR.info(f"[METRICS] - Stream Duration: {duration:.2f} seconds")

            self.finished.emit()
        except Exception as e:
            LOGGER.error(f"AIWorker Error: {str(e)}")
            AUDITOR.error(f"[ERROR] - AI Transaction Failed: {str(e)}")
            self.error_occurred.emit(str(e))
