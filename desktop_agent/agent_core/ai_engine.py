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

    def __init__(self, api_key, prompt, history=None, model_name="gemini-3-flash-preview", jd_context="N/A", cv_context="N/A", project_notes="N/A"):
        super().__init__()
        self.api_key = api_key
        self.prompt = prompt
        self.history = history or [] # Expected format: list of {"role": "user"|"model", "parts": [{"text": ...}]}
        self.model_name = model_name
        self.jd_context = jd_context
        self.cv_context = cv_context
        self.project_notes = project_notes

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
        specific_guardrail = ""
        
        if persona_mode == "STAR":
            specific_guardrail = "Use the Situation-Task-Action-Result (STAR) framework based strictly on projects identified in the [CV SNIPPET] and [PROJECT NOTES]."
        elif persona_mode == "ARCHITECT":
            specific_guardrail = "Focus on technical Trade-offs and Scalability. Benchmark against the [JD SNIPPET] and [PROJECT NOTES]."
        else:
            specific_guardrail = "Provide a balanced professional response grounded in your experience and supported by [PROJECT NOTES]."

        try:
            client = genai.Client(api_key=self.api_key)
            
            # 4. FIRST-PERSON HUMAN MONOLOGUE GUARDRAILS
            bridge_instr = ""
            if is_caution:
                bridge_instr = "FORCE BRIDGE: Since the tech is missing from your CV, say: 'I haven't used [Tech] in production yet, but I've done deep work with [Related Tech from Snippet/Notes]...'"

            system_instruction = f"""
            Identify as the candidate. Speak ONLY in the first person ('I', 'Me', 'My').
            {bridge_instr}
            {specific_guardrail}

            Contextual Assets:
            [PROJECT NOTES]: {self.project_notes}

            Guidelines for a natural, conversational response:
            1. Length: Keep the response concise. Aim for 1-2 short paragraphs that sound like natural spoken language. Do NOT provide overly long "Level 3" essays unless absolutely necessary.
            2. Tone: Friendly, professional, and conversational. Use contractions (I've, We're, It's).
            3. Formatting: Do NOT use markdown bolding, italics, or code blocks. The text will be read aloud or quickly scanned on an overlay, so keep it plain text.
            4. Start Immediately: Skip filler phrases. Start your answer directly and naturally.
            """

            # Prompt Framing: Modular and snippet-focused
            refined_prompt = f"""
            [CV SNIPPET]: {cv_snippet}
            [JD SNIPPET]: {jd_snippet}
            
            INTERVIEWER QUESTION: {self.prompt}
            
            Please deliver your response as the candidate:
            """

            # Audit: Log Refined Parameters
            AUDITOR.info(f"[CONTEXT_ENGINE] - Mode: {persona_mode} | Caution: {is_caution} | History: {len(self.history)}")
            AUDITOR.info(f"[SENT_TO_AI] - System Instruction: {system_instruction.strip()}")

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
            # [API TESTING BYPASS] - Mocking response to save AI tokens while testing STT.
            mock_message = f"**[STT TESTING MODE - AI DISABLED]**\nI heard:\n\"{self.prompt}\"\n\nTell me when you are ready to enable the AI again."
            import time
            for chunk in mock_message.split(" "):
                token = chunk + " "
                full_response += token
                self.token_received.emit(token)
                time.sleep(0.05)
            
            '''
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
                    import time # ensure time is imported if not already
                    import logging
                    error_msg = str(stream_err)
                    # Check if it is a 503 or transient error
                    if "503" in error_msg or "UNAVAILABLE" in error_msg or "temporarily" in error_msg.lower():
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logging.getLogger("CareerCaster").warning(f"AI API 503. Retrying in {delay}s...")
                            time.sleep(delay)
                            continue
                    # Default: reraise if we can't handle it or exhausted retries
                    raise stream_err
            '''
            
            # Audit: Final Metrics
            duration = time.time() - start_time
            AUDITOR.info(f"[RECEIVED_FROM_AI] - Full Response: {full_response}")
            AUDITOR.info(f"[METRICS] - Duration: {duration:.2f}s | Mode: {persona_mode} | Caution: {is_caution}")

            self.finished.emit()
        except Exception as e:
            LOGGER.error(f"AIWorker Error: {str(e)}")
            AUDITOR.error(f"[ERROR] - Engine Failed: {str(e)}")
            self.error_occurred.emit(str(e))
