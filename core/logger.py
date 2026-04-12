import json
import os
from datetime import datetime
import threading

# Ensure logs directory exists
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOG_FILE = os.path.join(LOGS_DIR, "api_history.jsonl")
_log_lock = threading.Lock()

def log_api_transaction(model_used, prompt_length, response_text, status, error_details=None):
    """
    Logs an API transaction to a JSONL file in a thread-safe manner.
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "model_used": model_used,
        "prompt_length": prompt_length,
        "response_text": response_text,
        "status": status,
        "error_details": error_details
    }
    
    try:
        with _log_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Logging Error: {e}")
