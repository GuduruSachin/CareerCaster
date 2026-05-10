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
import sys
from .context_refiner import extract_snippets, detect_intent, check_knowledge_gap

LOGGER = logging.getLogger("CareerCaster")

# --- HIGH-PRECISION AI AUDITOR SETUP ---
def setup_ai_auditor():
    auditor = logging.getLogger("AIAuditor")
    auditor.setLevel(logging.INFO)
    
    logs_dir = get_logs_dir()
    log_file = os.path.join(logs_dir, "ai_transactions.log")
    
    # We use a clean format without timestamps for console/audit to match user preference
    formatter = logging.Formatter('%(message)s')
    
    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    
    # Remove existing handlers if re-initialized
    if auditor.hasHandlers():
        auditor.handlers.clear()
        
    auditor.addHandler(fh)
    auditor.addHandler(sh)
    auditor.propagate = False # Prevent leaking to main app logger
    return auditor

AUDITOR = setup_ai_auditor()

class AIWorker(QThread):
    """
    CareerCaster v1.2 - RE-ENGINEERED AI Engine.
    Handles dynamic persona pivoting and human-centric monologue generation.
    """
    question_count = 0

    token_received = pyqtSignal(str)
    caution_signal = pyqtSignal(bool)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, prompt, history=None, model_name="gemini-3-flash-preview", jd_context="N/A", cv_context="N/A", project_notes="N/A", compiled_persona=""):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.history = history or [] # Expected format: list of {"role": "user"|"model", "parts": [{"text": ...}]}
        self.model_name = model_name
        self.jd_context = jd_context
        self.cv_context = cv_context
        self.project_notes = project_notes
        self.compiled_persona = compiled_persona

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
        persona_mode = detect_intent(self.prompt)
        is_caution = check_knowledge_gap(self.prompt, self.cv_context)
        
        # 2. ZERO-FLICKER METADATA (Immediate caution signaling)
        self.caution_signal.emit(is_caution)

        # 3. CONTEXT-AWARE PERSONA CONFIGURATION
        specific_guardrail = ""
        
        if persona_mode == "STAR":
            specific_guardrail = "Use the Situation-Task-Action-Result (STAR) framework based strictly on projects identified in the [CANDIDATE PERSONA] and [PROJECT NOTES]."
        elif persona_mode == "ARCHITECT":
            specific_guardrail = "Focus on technical Trade-offs and Scalability. Benchmark against the [PROJECT NOTES]."
        elif persona_mode == "DIRECT_TECH":
            specific_guardrail = "Provide a direct, clear, and concise technical explanation. Compare concepts if asked (e.g., difference between). Explain clearly without overly using buzzwords."
        else:
            specific_guardrail = "Provide a balanced professional response grounded in your experience and supported by [CANDIDATE PERSONA] and [PROJECT NOTES]."

        try:
            client = genai.Client(api_key=self.api_key)
            
            # 4. FIRST-PERSON HUMAN MONOLOGUE GUARDRAILS
            bridge_instr = ""
            if is_caution:
                bridge_instr = "FORCE BRIDGE: Since the tech is missing from your experience, say: 'I haven't used [Tech] in production yet, but I've done deep work with [Related Tech from Notes/Persona]...'"

            contextual_assets = "" 
            if persona_mode != "DIRECT_TECH":
                contextual_assets = f"""Contextual Assets:
[CANDIDATE PERSONA]: {self.compiled_persona}
[PROJECT NOTES]: {self.project_notes}"""

            system_instruction = f"""
            Identify as the candidate. Speak ONLY in the first person ('I', 'Me', 'My').
            {bridge_instr}
            {specific_guardrail}

            {contextual_assets}

            Guidelines for a natural, conversational response:
            1. Length: Adjust your length dynamically across questions. Give short, direct answers for simple factual questions. For behavioral or complex technical questions, give a comprehensive but natural answer. Do not aggressively compress when detail is needed, but avoid unnecessary rambling.
            2. Tone: Friendly, professional, and conversational. Use contractions (I've, We're, It's).
            3. Formatting: Do NOT use markdown bolding, italics, or code blocks. The text will be read aloud or quickly scanned on an overlay, so keep it plain text.
            4. Start Immediately: Skip filler phrases. Start your answer directly and naturally.
            """

            # Prompt Framing: Modular and snippet-focused
            if persona_mode == "DIRECT_TECH":
                refined_prompt = f"""
                INTERVIEWER QUESTION: {self.prompt}
                
                Please deliver your technical response clearly:
                """
            else:
                # If it's a general or STAR question, but we want extra context, 
                # we can still pass a quick snippet of CV to jog memory if persona wasn't enough
                refined_prompt = f"""
                INTERVIEWER QUESTION: {self.prompt}
                
                Please deliver your response as the candidate:
                """

            # Audit: Log Refined Parameters
            AIWorker.question_count += 1
            AUDITOR.info("\n" + "="*50)
            AUDITOR.info(f"Question {AIWorker.question_count}\n")
            AUDITOR.info(f"1) TEXT HEARD (VOICE TO TEXT): {self.prompt}")
            AUDITOR.info(f"2) FRAMED QUESTION: {self.prompt}")
            AUDITOR.info(f"3) PROMPT SENDING TO AI:\nSystem Instruction:\n{system_instruction.strip()}\n\nRefined Prompt:\n{refined_prompt.strip()}")

            # Prepare messages with history
            messages = self.history + [{"role": "user", "parts": [{"text": refined_prompt.strip()}]}]

            # Prepare configuration using the imported types module
            config = types.GenerateContentConfig(
                system_instruction=system_instruction.strip(),
                temperature=0.7 # Slight randomness for more human rhythm
            )

            # Define exponential backoff for retries
            max_retries = 3
            base_delay = 1 # second
            
            # 5. Stream Duration Monitoring with Retries
            full_response = ""
            for attempt in range(max_retries):
                try:
                    for chunk in client.models.generate_content_stream(
                        model=self.model_name,
                        contents=messages,
                        config=config
                    ):
                        if chunk.text:
                            token = chunk.text
                            full_response += token
                            self.token_received.emit(token)
                    break # Success! Break out of the retry loop
                except Exception as stream_err:
                    import logging
                    error_msg = str(stream_err)
                    
                    # Intercept 429 Resource Exhausted cleanly
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                        self.token_received.emit("\n\n**[API QUOTA EXCEEDED]**\nThe selected Gemini model is out of tokens or hitting a rate limit. Please select a different model in the Control Panel or wait a few minutes.")
                        return

                    # Check if it is a 503 or transient error
                    if "503" in error_msg or "UNAVAILABLE" in error_msg or "temporarily" in error_msg.lower():
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logging.getLogger("CareerCaster").warning(f"AI API 503. Retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                    # Default: reraise if we can't handle it or exhausted retries
                    raise stream_err
            
            # Audit: Final Metrics
            duration = time.time() - start_time
            AUDITOR.info(f"4) ANSWER RECEIVED FROM AI: {full_response}")
            AUDITOR.info(f"[METRICS] - Duration: {duration:.2f}s | Mode: {persona_mode} | Caution: {is_caution}")
            AUDITOR.info("="*50 + "\n")

            self.finished.emit()
        except Exception as e:
            LOGGER.error(f"AIWorker Error: {str(e)}")
            AUDITOR.error(f"[ERROR] - Engine Failed: {str(e)}")
            self.error_occurred.emit(str(e))
