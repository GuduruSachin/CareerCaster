# Shared logic and constants for CareerCaster
import os

SESSION_DIR = os.path.join(os.path.expanduser("~"), ".careercaster")

def ensure_session_dir():
    if not os.path.exists(SESSION_DIR):
        os.makedirs(SESSION_DIR)
