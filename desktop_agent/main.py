import sys
import os
import types
import warnings

# --- PHASE 2: TOTAL STEALTH SUPPRESSION ---
# Block all Torch/PyInstaller noise at the absolute entry point
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*distributed.*")

import time
import logging

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QSharedMemory, Qt

# Modular Imports
from ui.overlay import StealthOverlay
from ui.green_room import GreenRoom

# MODULE-LEVEL GLOBAL ANCHORS (Python 3.13 Persistence Strategy)
APPLICATION_INSTANCE = None
MAIN_OVERLAY = None
GREEN_ROOM = None
DIAGNOSTIC_TIMER = None
MUTEX_LOCK = None
LOGGER = None
HEARTBEAT_COUNT = 0
SESSION_DATA = {}

# --- ARCHITECTURAL IMPORT STABILIZATION & PATH ROBUSTNESS ---
if getattr(sys, 'frozen', False):
    # Running as Bundled EXE
    ROOT_DIR = sys._MEIPASS
    # Ensure bundle root is at the top of sys.path for standard imports
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
else:
    # Running as Script
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(ROOT_DIR)

    # Priority 1: Project Root (for shared /core security/paths)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Priority 2: Agent Root (for /ui overlay and /agent_core)
    if ROOT_DIR not in sys.path:
        sys.path.append(ROOT_DIR)

import json
from core.security import SecurityManager
from core.paths import get_logs_dir, secure_cleanup

# --- FILE-BASED LOGGING SYSTEM ---
def setup_logging():
    global LOGGER
    logs_dir = get_logs_dir()
    log_file = os.path.join(logs_dir, "session.log")
    
    LOGGER = logging.getLogger("CareerCaster")
    LOGGER.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    
    fh = logging.FileHandler(log_file)
    fh.setFormatter(formatter)
    
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    
    LOGGER.addHandler(fh)
    LOGGER.addHandler(sh)
    return LOGGER

# --- SECURITY REMOVED MOCK (USING REAL CORE) ---

def run_heartbeat():
    global HEARTBEAT_COUNT
    HEARTBEAT_COUNT += 1
    if LOGGER:
        LOGGER.info(f"Layer 4.Refactor: Heartbeat #{HEARTBEAT_COUNT} - Loop Valid at {time.strftime('%H:%M:%S')}")

def start_stealth_overlay(hardware_config):
    """Transition callback from Green Room to Stealth Overlay."""
    global MAIN_OVERLAY, GREEN_ROOM, SESSION_DATA
    if GREEN_ROOM:
        GREEN_ROOM.close()
    
    MAIN_OVERLAY = StealthOverlay(session_data=SESSION_DATA, hardware_config=hardware_config)
    MAIN_OVERLAY.show()
    LOGGER.info("Stealth Overlay launched via Green Room transition.")

def initialize_refined_skeleton():
    global APPLICATION_INSTANCE, MAIN_OVERLAY, GREEN_ROOM, DIAGNOSTIC_TIMER, MUTEX_LOCK, LOGGER, SESSION_DATA

    LOGGER = setup_logging()

    # Singleton instance check
    MUTEX_LOCK = QSharedMemory("CareerCaster_Unique_Lock")
    if not MUTEX_LOCK.create(1):
        if MUTEX_LOCK.attach():
            LOGGER.error("Another instance of CareerCaster is already running. Exiting.")
            sys.exit(0)

    # Core Engine Setup
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    APPLICATION_INSTANCE = QApplication(sys.argv)
    
    # Session & Security Synchronization
    decrypted_data = {}
    auth_error = None
    try:
        security = SecurityManager()
        if len(sys.argv) > 1 and sys.argv[1].endswith('.cc'):
            session_path = sys.argv[1]
            LOGGER.info(f"Targeting session file: {session_path}")
            if os.path.exists(session_path):
                LOGGER.info("Session file found. Accessing...")
                with open(session_path, "rb") as f:
                    encrypted_data = f.read()
                
                try:
                    raw_json = security.decrypt_data(encrypted_data)
                    decrypted_data = json.loads(raw_json)
                    
                    # BACKWARD COMPATIBILITY & ENTERPRISE MAPPING
                    # Map dashboard keys to engine-expected keys
                    if 'resume_text' in decrypted_data and 'resume_data' not in decrypted_data:
                        decrypted_data['resume_data'] = decrypted_data['resume_text']
                    if 'jd_text' in decrypted_data and 'job_description' not in decrypted_data:
                        decrypted_data['job_description'] = decrypted_data['jd_text']
                    if 'project_notes' in decrypted_data and 'project' not in decrypted_data:
                        decrypted_data['project'] = decrypted_data['project_notes']

                    sess_id = decrypted_data.get('session_id', 'Unknown')
                    model = decrypted_data.get('active_model', {}).get('name', 'N/A')
                    LOGGER.info(f"Session Sync Success: {sess_id} | Model: {model}")
                except Exception as de:
                    auth_error = f"Authentication Error: {de}"
                    LOGGER.error(auth_error)
            else:
                auth_error = f"Session file missing at path: {os.path.abspath(session_path)}"
                LOGGER.warning(auth_error)
    except Exception as e:
        auth_error = f"Security initialization failed: {e}"
        LOGGER.error(auth_error)

    # Fallback to diagnostic state if sync fails
    if not decrypted_data:
        decrypted_data = {
            "id": "DIAG-1.1", 
            "preview_mode": True if auth_error else False, 
            "test_mode": True,
            "project": "CareerCaster Agent"
        }
        
    SESSION_DATA = decrypted_data

    # UI Construction: Stage 1 - Green Room
    GREEN_ROOM = GreenRoom(session_data=SESSION_DATA)
    GREEN_ROOM.ready_to_start.connect(start_stealth_overlay)
    
    # Heartbeat Watchdog
    DIAGNOSTIC_TIMER = QTimer()
    DIAGNOSTIC_TIMER.timeout.connect(run_heartbeat)
    DIAGNOSTIC_TIMER.start(5000)

    GREEN_ROOM.show()
    GREEN_ROOM.refresh_context()
    
    exit_code = APPLICATION_INSTANCE.exec()
    LOGGER.info("Interface shutdown sequence complete.")
    secure_cleanup()
    logging.shutdown()
    sys.exit(exit_code)

if __name__ == "__main__":
    try:
        initialize_refined_skeleton()
    except Exception as e:
        if LOGGER:
            LOGGER.critical(f"[ROOT FATAL] {e}")
        else:
            print(f"[ROOT FATAL] {e}", flush=True)
        time.sleep(5)
        sys.exit(1)
