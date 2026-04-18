import sys
import os
import time
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QSharedMemory

# Modular Imports
from ui.overlay import StealthOverlay

# MODULE-LEVEL GLOBAL ANCHORS (Python 3.13 Persistence Strategy)
APPLICATION_INSTANCE = None
MAIN_OVERLAY = None
DIAGNOSTIC_TIMER = None
MUTEX_LOCK = None
LOGGER = None
HEARTBEAT_COUNT = 0

# --- ARCHITECTURAL IMPORT STABILIZATION & PATH ROBUSTNESS ---
ROOT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# --- FILE-BASED LOGGING SYSTEM ---
def setup_logging():
    global LOGGER
    logs_dir = os.path.join(ROOT_DIR, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir, exist_ok=True)
    
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

# --- SECURITY MOCK FOR MODULATED TESTING ---
try:
    from core.security import SecurityManager
except ImportError:
    class SecurityManager:
        @staticmethod
        def get_hardware_id(): return "MODULAR-HWID-MOCK"
        @staticmethod
        def decrypt_session(p, k): return {"id": "SESS-MODULAR", "project": "CareerCaster Modular"}

def run_heartbeat():
    global HEARTBEAT_COUNT
    HEARTBEAT_COUNT += 1
    if LOGGER:
        LOGGER.info(f"Layer 4.Refactor: Heartbeat #{HEARTBEAT_COUNT} - Loop Valid at {time.strftime('%H:%M:%S')}")

def initialize_refined_skeleton():
    global APPLICATION_INSTANCE, MAIN_OVERLAY, DIAGNOSTIC_TIMER, MUTEX_LOCK, LOGGER

    LOGGER = setup_logging()

    LOGGER.info("[STEP 1/5] MUTEX: Checking for existing instances...")
    MUTEX_LOCK = QSharedMemory("CareerCaster_Unique_Lock")
    if not MUTEX_LOCK.create(1):
        if MUTEX_LOCK.attach():
            LOGGER.error("[CRITICAL] Mutex Check: Another instance detected. Exiting.")
            sys.exit(0)

    LOGGER.info("[STEP 2/5] ENGINE: Initializing QApplication and event loop...")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    APPLICATION_INSTANCE = QApplication(sys.argv)
    
    LOGGER.info("[STEP 3/5] SECURITY: Syncing Hardware ID and session encryption...")
    decrypted_data = None
    try:
        hw_id = SecurityManager.get_hardware_id()
        if len(sys.argv) > 1 and sys.argv[1].endswith('.cc'):
            session_path = sys.argv[1]
            # In a real environment, decrypt_session would load the JSON from user's dashboard
            decrypted_data = SecurityManager.decrypt_session(session_path, hw_id)
            LOGGER.info(f"Session Sync: Loaded {decrypted_data.get('id')} with model {decrypted_data.get('active_model', {}).get('name')}")
    except Exception as e:
        LOGGER.warning(f"Security Sync Failed: {e}")

    # Requirement 2: Entry point passing verified API key and Model name to Overlay
    LOGGER.info("[STEP 4/5] INTERFACE: Constructing Modular Assistant UI...")
    MAIN_OVERLAY = StealthOverlay(session_data=decrypted_data)
    
    LOGGER.info("[STEP 5/5] WATCHDOG: Diagnostic heartbeat active.")
    DIAGNOSTIC_TIMER = QTimer()
    DIAGNOSTIC_TIMER.timeout.connect(run_heartbeat)
    DIAGNOSTIC_TIMER.start(5000)

    if MAIN_OVERLAY.test_mode_active:
        MAIN_OVERLAY.inject_message("Modular Refactor complete. Dynamic AI Sync active.", sender="SYSTEM")
    
    MAIN_OVERLAY.show()
    
    exit_code = APPLICATION_INSTANCE.exec()
    LOGGER.info("Interface shutdown sequence complete.")
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
