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
from core.context_refiner import extract_snippets, detect_intent, check_knowledge_gap

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
    CareerCaster v1.2 - RE-ENGINEERED AI Engine.
    Handles dynamic persona pivoting and human-centric monologue generation.
    """
    token_received = pyqtSignal(str)
    caution_signal = pyqtSignal(bool)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, prompt, history=None, model_name="gemini-3-flash-preview", jd_context="N/A", cv_context="N/A"):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.history = history or [] # Expected format: list of {"role": "user"|"model", "parts": [{"text": ...}]}
        self.model_name = model_name
        self.jd_context = jd_context
        self.cv_context = cv_context

    def run(self):
        if not genai:
            self.error_occurred.emit("Google GenAI SDK not installed.")
            return
        
        if not self.api_key:
            self.error_occurred.emit("API Key missing from session.")
            return

        start_time = time.time()
        full_response = ""
        
        # 1. LOCAL CONTEXT REFINEMENT (RAG-LITE)
        jd_snippet = extract_snippets(self.prompt, self.jd_context)
        cv_snippet = extract_snippets(self.prompt, self.cv_context)
        persona_mode = detect_intent(self.prompt)
        is_caution = check_knowledge_gap(self.prompt, self.cv_context)
        
        # Immediate Signal Emission to prevent UI flickering
        self.caution_signal.emit(is_caution)

        # Persona Pivot Logic
        persona_title = "user's INTERNAL MONOLOGUE"
        extra_instr = ""
        if persona_mode == "STAR-Experience":
            persona_title = "Senior Project Lead"
            extra_instr = "Force the AI to use the STAR method (Situation, Task, Action, Result) based on the provided CV_SNIPPET."
        elif persona_mode == "Architect-Technical":
            persona_title = "Lead Software Architect"
            extra_instr = "Deep dive into architectural trade-offs and system design patterns."

        try:
            client = genai.Client(api_key=self.api_key)
            
            # 3. Human-Centric System Instruction
            system_instruction = f"""
            Persona: You are the {persona_title}.
            {extra_instr}

            Narrative Format: Deliver answers in 2 to 3 short paragraphs with DOUBLE LINE BREAKS. 
            Strictly FORBID bullet points, numbered lists, and markdown headers (###). 

            Human Tone: Use conversational anchors like "Essentially...", "In my experience...", or "The main trade-off here is...". 
            Use regular, professional language—avoid academic jargon. Avoid repeating identical phrases from history.

            Visual Scanning: BOLD 3-5 critical technical keywords per paragraph (e.g. **Microservices**).

            Hallucination Guardrail:
            - If tech is missing from context, use a "Bridge" answer: "I haven't worked with [Tech X] directly, but in my experience with [Related Tech Y], I approach it like this..."
            - If you bridge or guess, prepend [CAUTION] to the response.

            Anti-Latency Rules: ZERO FILLER | TOKEN CAPPING (~80-100 words).
            """

            # Prompt Framing: Tiny, high-impact prompt
            refined_prompt = f"""
            Using this [CV SNIPPET]: {cv_snippet}
            And this [JD SNIPPET]: {jd_snippet}
            
            Answer this question in [{persona_mode}] mode: {self.prompt}
            """

            # Audit: Log Refinement Results
            AUDITOR.info(f"[CONTEXT_REFINED] - Mode: {persona_mode} | Caution_Emit: {is_caution} | History_Depth: {len(self.history)}")
            AUDITOR.info(f"[SENT_TO_AI] - Refined Prompt: {refined_prompt.strip()}")

            # Prepare messages with history
            messages = self.history + [{"role": "user", "parts": [{"text": refined_prompt.strip()}]}]

            # 4. Stream Duration Monitoring
            for chunk in client.models.generate_content_stream(
                model=self.model_name,
                contents=messages,
                config={'system_instruction': system_instruction.strip()}
            ):
                if chunk.text:
                    token = chunk.text
                    full_response += token
                    self.token_received.emit(token)
            
            # Audit: Log Metrics
            duration = time.time() - start_time
            AUDITOR.info(f"[RECEIVED_FROM_AI] - Full Response: {full_response}")
            AUDITOR.info(f"[METRICS] - Duration: {duration:.2f}s | Caution_Active: {is_caution} | Mode: {persona_mode}")

            self.finished.emit()
        except Exception as e:
            LOGGER.error(f"AIWorker Error: {str(e)}")
            AUDITOR.error(f"[ERROR] - AI Transaction Failed: {str(e)}")
            self.error_occurred.emit(str(e))
