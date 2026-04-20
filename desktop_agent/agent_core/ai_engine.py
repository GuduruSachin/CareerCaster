import logging
import os
import time
from PyQt6.QtCore import QThread, pyqtSignal

# Import the new Google GenAI SDK
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from core.paths import get_logs_dir
from .context_refiner import extract_snippets, detect_intent, check_knowledge_gap

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
        
        # 1. DYNAMIC RAG-LITE CONTEXT REFINEMENT
        jd_snippet = extract_snippets(self.prompt, self.jd_context)
        cv_snippet = extract_snippets(self.prompt, self.cv_context)
        persona_mode = detect_intent(self.prompt)
        is_caution = check_knowledge_gap(self.prompt, self.cv_context)
        
        # 2. ZERO-FLICKER METADATA (Immediate caution signaling)
        self.caution_signal.emit(is_caution)

        # 3. CONTEXT-AWARE PERSONA CONFIGURATION
        persona_identity = "Umesh (Senior Developer)"
        specific_guardrail = ""
        
        if persona_mode == "STAR":
            specific_guardrail = "Use the Situation-Task-Action-Result (STAR) framework based strictly on projects identified in the [CV SNIPPET]."
        elif persona_mode == "ARCHITECT":
            specific_guardrail = "Focus on technical Trade-offs and Scalability. Benchmark against the [JD SNIPPET]."
        else:
            specific_guardrail = "Provide a balanced professional response grounded in your experience."

        try:
            client = genai.Client(api_key=self.api_key)
            
            # 4. FIRST-PERSON HUMAN MONOLOGUE GUARDRAILS
            bridge_instr = ""
            if is_caution:
                bridge_instr = "FORCE BRIDGE: Since the tech is missing from your CV, say: 'I haven't used [Tech] in production yet, but I've done deep work with [Related Tech from Snippet]...'"

            system_instruction = f"""
            Identity: You ARE Umesh (Senior Developer). You must speak ONLY in the first person ('I', 'Me', 'My').
            {bridge_instr}
            {specific_guardrail}

            1. Situational Response Weighting:
               - Level 1 (Intro/Short): For greetings/small talk, provide a 1-paragraph friendly spoken response.
               - Level 2 (Technical/Explanatory): For 'How-to' or 'What is', provide ~2 paragraphs focusing on Trade-offs and logic.
               - Level 3 (Strategic/STAR): For 'Tell me about...' or 'Walk me through...', provide ~3 detailed paragraphs using STAR method anchored in [CV SNIPPET] projects (e.g., Enterprise Dashboard, CLR System).

            2. Speech-Centered Vocabulary (Workshop English):
               - Replace academic terms: 'makes it easy' (NOT 'facilitates'), 'fast' (NOT 'optimal').
               - Forced Contractions: Use 'I've', 'Don't', 'We're', 'It's', 'I'm' to ensure natural rhythm.
               - Forbidden Words: Essentially, Furthermore, Moreover, Delineate, Comprehensive, Subject to.

            3. Technical Bug Patches & Latency:
               - Encoding: Use ASCII-only characters. NO smart-quotes or special symbols. Use standard ' and ".
               - Latency: SKIP all fillers like 'That's a great question'. Start the answer IMMEDIATELY.

            4. Visual Scannability:
               - Bold Strategy: BOLD ONLY technical nouns (e.g., **stored procedures**, **latency**, **SSO**) to act as cues.
               - No Junk: Strictly FORBID code blocks, images, or bullet points.
            """

            # Prompt Framing: Modular and snippet-focused
            refined_prompt = f"""
            [CV SNIPPET]: {cv_snippet}
            [JD SNIPPET]: {jd_snippet}
            
            INTERVIEWER QUESTION: {self.prompt}
            
            Umesh, deliver your response:
            """

            # Audit: Log Refined Parameters
            AUDITOR.info(f"[CONTEXT_ENGINE] - Mode: {persona_mode} | Caution: {is_caution} | History: {len(self.history)}")
            AUDITOR.info(f"[SENT_TO_AI] - System Instruction: {system_instruction.strip()}")

            # Prepare messages with history
            messages = self.history + [{"role": "user", "parts": [{"text": refined_prompt.strip()}]}]

            # 5. Stream Duration Monitoring
            for chunk in client.models.generate_content_stream(
                model=self.model_name,
                contents=messages,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction.strip(),
                    temperature=0.7 # Slight randomness for more human rhythm
                )
            ):
                if chunk.text:
                    token = chunk.text
                    full_response += token
                    self.token_received.emit(token)
            
            # Audit: Final Metrics
            duration = time.time() - start_time
            AUDITOR.info(f"[RECEIVED_FROM_AI] - Full Response: {full_response}")
            AUDITOR.info(f"[METRICS] - Duration: {duration:.2f}s | Mode: {persona_mode} | Caution: {is_caution}")

            self.finished.emit()
        except Exception as e:
            LOGGER.error(f"AIWorker Error: {str(e)}")
            AUDITOR.error(f"[ERROR] - Engine Failed: {str(e)}")
            self.error_occurred.emit(str(e))
