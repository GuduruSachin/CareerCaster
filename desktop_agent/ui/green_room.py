import json
import os
import time
import logging
import threading
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QComboBox, QPushButton, QProgressBar, 
                             QFrame, QScrollArea, QSizePolicy, QCheckBox, QGridLayout, 
                             QMessageBox, QDialog)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

# Library Imports
try:
    from google import genai
except ImportError:
    genai = None

from core.paths import get_settings_path
from core.credentials import get_master_api_key
from agent_core.audio_scanner import AudioScanner
from agent_core.audio_capture import AudioCaptureEngine

LOGGER = logging.getLogger("CareerCaster")

class ConsentDialog(QDialog):
    """Custom, branded consent dialog for hardware access."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hardware Permissions")
        self.setFixedWidth(400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # UI Container
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: #121212;
                border: 1px solid #2A2A2A;
                border-radius: 12px;
            }
            QLabel { color: #A0AAB7; font-family: 'Segoe UI'; font-size: 14px; background: transparent; border: none; }
            QLabel#Title { color: #FFFFFF; font-size: 18px; font-weight: 800; selection-background-color: transparent; }
            QPushButton#Allow {
                background: #00E5FF;
                color: black;
                font-weight: 800;
                border-radius: 6px;
                padding: 10px;
                min-width: 100px;
            }
            QPushButton#Decline {
                background: transparent;
                color: #6B7280;
                border: 1px solid #1E1E1E;
                border-radius: 6px;
                padding: 10px;
                min-width: 100px;
            }
            QPushButton#Decline:hover {
                color: #FFFFFF;
                border: 1px solid #2A2A2A;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        title = QLabel("Hardware Access Required")
        title.setObjectName("Title")
        layout.addWidget(title)
        
        desc = QLabel("CareerCaster needs access to your <b>Microphone</b> (to listen to you) and <b>System Speakers</b> (to listen to the interviewer).<br><br>Allow this hardware access?")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        btn_lay = QHBoxLayout()
        btn_lay.setSpacing(10)
        btn_lay.addStretch()
        
        self.no_btn = QPushButton("Decline")
        self.no_btn.setObjectName("Decline")
        self.no_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.no_btn.clicked.connect(self.reject)
        
        self.yes_btn = QPushButton("Allow Access")
        self.yes_btn.setObjectName("Allow")
        self.yes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.yes_btn.clicked.connect(self.accept)
        
        btn_lay.addWidget(self.no_btn)
        btn_lay.addWidget(self.yes_btn)
        layout.addLayout(btn_lay)
        
        main_lay = QVBoxLayout(self)
        main_lay.addWidget(self.container)

class GreenRoom(QMainWindow):
    """
    CareerCaster v1.7 - Intelligent Command Center.
    Centralizes all AI reasoning and hardware control.
    """
    ready_to_start = pyqtSignal(dict, dict)

    def __init__(self, session_data=None):
        super().__init__()
        self.session_data = session_data or {}
        self.setWindowTitle("CareerCaster Pro")
        self.setMinimumWidth(450)
        self.setMinimumHeight(600)
        self.resize(550, 800)
        
        # 1. UI ROOT CONSTRUCTION
        self.root_widget = QWidget()
        self.root_widget.setObjectName("MainContainer")
        self.root_widget.setMinimumHeight(750)
        self.root_layout = QVBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(25, 30, 25, 30)
        self.root_layout.setSpacing(25)
        
        # 2. POPULATE LAYOUT (MANDATORY BEFORE ANCHORING)
        self.init_ui_sections()
        
        # 3. APPLY STYLES (DIRECT STYLE INJECTION)
        self.setup_stylesheet()
        
        # 4. ANCHOR UI (SCROLL ARCHITECTURE)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("MainScrollArea")
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #0A0A0A; }")
        self.scroll_area.setWidget(self.root_widget)
        self.setCentralWidget(self.scroll_area)

        # 5. INITIALIZE STATE (Synchronous to prevent early access crashes)
        self.api_key = None
        self.active_model_name = self.session_data.get("active_model", {}).get("name", "gemini-3-flash-preview")
        self.api_latency = -1
        self.available_models = []
        self.devices = {"loopback": [], "mics": []}
 
        # 6. ASYNC LOGIC TRIGGER (PREVENT STARTUP HANGS)
        QTimer.singleShot(250, self.delayed_init)

    def delayed_init(self):
        """Hardened async initialization to prevent startup hangs."""
        # AI Logic Sync (IO Bound)
        try:
            self.api_key = get_master_api_key()
        except Exception as e:
            LOGGER.error(f"Failed to retrieve API key: {e}")
            self.api_key = None
            
        # Consent Check
        dialog = ConsentDialog(self)
        has_consent = (dialog.exec() == QDialog.DialogCode.Accepted)

        # Hardware Setup
        if has_consent:
            try:
                from agent_core.audio_scanner import AudioScanner
                from agent_core.audio_capture import AudioCaptureEngine
                self.scanner = AudioScanner()
                self.audio_engine = AudioCaptureEngine()
                self.devices = self.scanner.get_wasapi_devices() or {"loopback": [], "mics": []}
            except Exception as e:
                LOGGER.error(f"Hardware initialization failed: {e}")
                self.devices = {"loopback": [], "mics": []}
            
            # Init hardware meters
            self.meter_timer = QTimer()
            self.meter_timer.timeout.connect(self.update_meters)
            self.meter_timer.start(50)
            
            # Populate and Load
            self.populate_devices()
            self.load_saved_settings()
            
            self.itv_combo.currentIndexChanged.connect(self.on_device_selection_changed)
            self.mic_combo.currentIndexChanged.connect(self.on_device_selection_changed)
            self.on_device_selection_changed()
        else:
            self.devices = {"loopback": [], "mics": []}
            self.itv_combo.addItem("Access Denied", -1)
            self.mic_combo.addItem("Access Denied", -1)
            self.itv_combo.setEnabled(False)
            self.mic_combo.setEnabled(False)
        
        # Background Discovery & Pre-loading
        threading.Thread(target=self.discover_ai_models, daemon=True).start()
        threading.Thread(target=self.prewarm_stt, daemon=True).start()
        
        # Event Handlers
        self.model_selector.currentTextChanged.connect(self.on_model_changed)
        self.validate_all()

    def setup_stylesheet(self):
        """Bento-Style Professional Theme - High Reliability & Solid Palette."""
        self.setStyleSheet("""
            QMainWindow, QScrollArea, QWidget#MainContainer {
                background-color: #0A0A0A;
                border: none;
            }
            QScrollArea { background-color: #0A0A0A; border: none; }
            QScrollArea > QWidget { background-color: #0A0A0A; }
            QScrollArea QWidget#qt_scrollarea_viewport { background-color: #0A0A0A; }
            
            /* Typography Hardening */
            QLabel {
                color: #A0AAB7;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                background: transparent;
            }
            
            /* Bento Section Headers (Manual Upper in Code) */
            QLabel#SectionHeader {
                color: #00E5FF;
                font-weight: 800;
                font-size: 11px;
                letter-spacing: 1.5px;
                margin-bottom: 5px;
            }
            
            /* Data Values */
            QLabel#DataValue {
                color: #FFFFFF;
                font-size: 15px;
                font-weight: 600;
            }
 
            /* Bento Card Design */
            QFrame#ControlCard {
                background-color: #121212;
                border: 1px solid #1E1E1E;
                border-radius: 12px;
            }
            QFrame#ControlCard:hover {
                border: 1px solid #2A2A2A;
            }
 
            /* Component Polarity */
            QComboBox {
                background-color: #1A1A1A;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                padding: 12px 15px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QComboBox:hover { border: 1px solid #3A3A3A; }
            QComboBox QAbstractItemView {
                background-color: #1A1A1A;
                color: white;
                selection-background-color: #00E5FF;
                selection-color: black;
            }
 
            QProgressBar {
                background-color: #0A0A0A;
                border: 1px solid #1A1A1A;
                border-radius: 3px;
                height: 5px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #00E5FF;
                border-radius: 2px;
            }
 
            /* Action Button Surface */
            QPushButton#ActionBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00E5FF, stop:1 #00A3FF);
                color: #000000;
                font-weight: 800;
                font-size: 15px;
                border-radius: 12px;
                padding: 20px;
                letter-spacing: 1.5px;
            }
            QPushButton#ActionBtn:hover {
                background: #00FBFF;
            }
            QPushButton#ActionBtn:disabled {
                background: #1E1E1E;
                color: #444444;
                border: 1px solid #1E1E1E;
            }
            
            QCheckBox { color: #8F9BA8; font-size: 12px; spacing: 10px; }
            QCheckBox::indicator { width: 20px; height: 20px; border-radius: 5px; border: 1px solid #2A2A2A; background: #1A1A1A; }
            QCheckBox::indicator:checked { background-color: #00E5FF; border: 1px solid #00E5FF; }
 
            /* Tactical Scrollbar */
            QScrollBar:vertical { background: #0A0A0A; width: 8px; margin: 0; }
            QScrollBar::handle:vertical { background: #1E1E1E; border-radius: 4px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    def init_ui_sections(self):
        """Construct a clean, professional bento-style setup screen."""
        # --- 1. BRANDING HEADER ---
        header = QWidget()
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(0, 10, 0, 30)
        
        pre_title = QLabel("INTERVIEW ARCHITECT")
        pre_title.setObjectName("SectionHeader")
        
        main_title = QLabel("CareerCaster")
        main_title.setStyleSheet("font-size: 40px; font-weight: 800; color: #FFFFFF; letter-spacing: -1.5px;")
        
        header_lay.addWidget(pre_title)
        header_lay.addWidget(main_title)
        self.root_layout.addWidget(header)

        # --- 2. AUDIO HARDWARE SECTION ---
        self.audio_card = QFrame()
        self.audio_card.setObjectName("ControlCard")
        # Removed hardcoded height to allow symmetric display of mic + loopback
        audio_lay = QVBoxLayout(self.audio_card)
        audio_lay.setContentsMargins(30, 30, 30, 30)
        audio_lay.setSpacing(25) # Increased spacing for better separation

        h_audio = QLabel("AUDIO HARDWARE SETUP")
        h_audio.setObjectName("SectionHeader")
        audio_lay.addWidget(h_audio)

        # Output Monitor (Loopback)
        itv_box = QVBoxLayout()
        itv_box.setSpacing(10)
        
        lbl_out = QLabel("INTERVIEWER SOURCE")
        lbl_out.setStyleSheet("color: #6B7280; font-weight: 800; font-size: 9px; letter-spacing: 1.2px;")
        itv_box.addWidget(lbl_out)
        
        self.itv_combo = QComboBox()
        self.itv_combo.setMinimumHeight(48)
        itv_box.addWidget(self.itv_combo)
        
        self.itv_meter = QProgressBar()
        self.itv_meter.setMinimumHeight(6)
        itv_box.addWidget(self.itv_meter)
        
        audio_lay.addLayout(itv_box)
        audio_lay.addSpacing(15)

        # Input Monitor (Microphone)
        mic_box = QVBoxLayout()
        mic_box.setSpacing(10)
        
        lbl_in = QLabel("YOUR MICROPHONE")
        lbl_in.setStyleSheet("color: #6B7280; font-weight: 800; font-size: 9px; letter-spacing: 1.2px;")
        mic_box.addWidget(lbl_in)
        
        self.mic_combo = QComboBox()
        self.mic_combo.setMinimumHeight(48)
        mic_box.addWidget(self.mic_combo)
        
        self.mic_meter = QProgressBar()
        self.mic_meter.setMinimumHeight(6)
        mic_box.addWidget(self.mic_meter)
        
        audio_lay.addLayout(mic_box)
        
        self.root_layout.addWidget(self.audio_card)

        # --- 3. AI CONFIGURATION SECTION ---
        ai_card = QFrame()
        ai_card.setObjectName("ControlCard")
        ai_card.setMinimumHeight(220)
        ai_lay = QVBoxLayout(ai_card)
        ai_lay.setContentsMargins(30, 30, 30, 30)
        ai_lay.setSpacing(20)

        h_ai = QLabel("AI INTELLIGENCE CONFIG")
        h_ai.setObjectName("SectionHeader")
        ai_lay.addWidget(h_ai)

        ai_row = QHBoxLayout()
        ai_row.setSpacing(15)
        
        v_model = QVBoxLayout()
        v_model.setSpacing(8)
        lbl_model = QLabel("REASONING ENGINE")
        lbl_model.setStyleSheet("color: #6B7280; font-weight: 800; font-size: 9px; letter-spacing: 1.2px;")
        v_model.addWidget(lbl_model)
        
        self.model_selector = QComboBox()
        self.model_selector.setMinimumHeight(48)
        v_model.addWidget(self.model_selector)
        ai_row.addLayout(v_model, 3)
        
        stat_box = QVBoxLayout()
        stat_box.setSpacing(8)
        stat_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.status_msg = QLabel("WAITING...")
        self.status_msg.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10px; color: #4B5563; font-weight: bold;")
        self.status_led = QLabel()
        self.status_led.setFixedSize(60, 4)
        self.status_led.setStyleSheet("background: #1A1A1A; border-radius: 2px;")
        
        stat_box.addWidget(self.status_msg)
        stat_box.addWidget(self.status_led)
        ai_row.addLayout(stat_box, 1)
        
        ai_lay.addLayout(ai_row)

        self.stealth_toggle = QCheckBox("HIDE INTERFACE ON LAUNCH (STEALTH MODE)")
        self.stealth_toggle.setChecked(not self.session_data.get("disable_stealth", False))
        self.stealth_toggle.setMinimumHeight(30)
        ai_lay.addWidget(self.stealth_toggle)

        self.root_layout.addWidget(ai_card)

        # --- 5. INITIALIZE ACTION ---
        self.root_layout.addStretch(1)
        
        self.start_btn = QPushButton("LAUNCH INTERVIEW ASSISTANT")
        self.start_btn.setObjectName("ActionBtn")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(65)
        self.start_btn.clicked.connect(self.finalize_and_start)
        self.root_layout.addWidget(self.start_btn)

        foot = QLabel("SECURE ENCRYPTED SESSION • v1.8 PRO")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setStyleSheet("color: #4B5563; font-size: 10px; font-weight: bold; margin-top: 15px;")
        self.root_layout.addWidget(foot)

    def discover_ai_models(self):
        """v1.8.15: Latency-Driven Discovery - Only shows verified models, fastest first."""
        if not self.api_key:
            QTimer.singleShot(0, lambda: self.on_ai_fail("API Key Missing"))
            return

        def run_discovery():
            try:
                client = genai.Client(api_key=self.api_key)
                
                # 1. Fetch Candidates (Broad Sweep)
                candidates = [] # list of (short_name, full_name)
                try:
                    remote = client.models.list()
                    for rm in remote:
                        if "generateContent" in rm.supported_methods:
                            m_full = rm.name
                            m_short = m_full.split("/")[-1]
                            # Filter for usable chat models
                            if "vision" not in m_short and "embedding" not in m_short and "text" not in m_short:
                                candidates.append((m_short, m_full))
                except:
                    # Fallback list if API call fails
                    candidates = [("gemini-1.5-flash", "models/gemini-1.5-flash"), 
                                 ("gemini-2.0-flash", "models/gemini-2.0-flash")]

                # 2. Parallel Latency Verification
                verified_results = [] # list of {"short":, "full":, "lat":}
                verified_lock = threading.Lock()
                
                def ping_model(m_short, m_full):
                    try:
                        t0 = time.time()
                        client.models.generate_content(
                            model=m_full, 
                            contents="ping", 
                            config={"max_output_tokens": 1}
                        )
                        lat = int((time.time() - t0) * 1000)
                        with verified_lock:
                            verified_results.append({"short": m_short, "full": m_full, "lat": lat})
                    except Exception:
                        pass 

                # Test all retrieved valid models cleanly without prioritizing specific "seed" models.
                threads = []
                for m_short, m_full in candidates:
                    t = threading.Thread(target=ping_model, args=(m_short, m_full))
                    t.daemon = True
                    t.start()
                    threads.append(t)
                
                # Wait for verification (max 2 seconds)
                for t in threads: t.join(timeout=2.0)
                
                if verified_results:
                    # Sort by latency ASC
                    final_sorted = sorted(verified_results, key=lambda x: x["lat"])
                    self.available_models = final_sorted # Store dicts now
                    self.api_latency = final_sorted[0]["lat"]
                    QTimer.singleShot(0, self.on_ai_success)
                else:
                    QTimer.singleShot(0, lambda: self.on_ai_fail("No Models Connected"))

            except Exception as e:
                LOGGER.error(f"AI Discovery Fatal: {e}")
                QTimer.singleShot(0, lambda: self.on_ai_fail("System Error"))
        
        threading.Thread(target=run_discovery, daemon=True).start()

    def on_ai_success(self):
        """Populates the selector with verified models and selects the fastest one."""
        self.model_selector.clear()
        
        if not self.available_models:
            self.on_ai_fail("Empty Discovery")
            return

        # self.available_models is a list of {"short":, "full":, "lat":}
        for m in self.available_models:
            self.model_selector.addItem(m["short"], m["full"])

        self.model_selector.setCurrentIndex(0)
        self.model_selector.setEnabled(True)
            
        self.status_led.setStyleSheet("background-color: #00FF7F; border-radius: 2px;")
        self.status_msg.setText(f"FASTEST: {self.api_latency}ms")
        self.status_msg.setStyleSheet("font-family: 'Consolas'; color: #00FF88; font-weight: bold; font-size: 11px;")
        
        # Save choice to session immediately (using the FULL name in itemData)
        self.on_model_changed(self.model_selector.currentData())
        self.validate_all()

    def on_ai_fail(self, err):
        self.status_led.setStyleSheet("background-color: #FF4500; border-radius: 2px;")
        self.status_msg.setText(f"OFFLINE ({err[:25]})")
        self.status_msg.setStyleSheet("font-family: 'Consolas'; color: #FF4500; font-weight: bold; font-size: 11px;")
        self.validate_all()

    def on_model_changed(self, full_name):
        # Triggered by currentTextChanged too? No, I should use currentIndexChanged for data access
        if not full_name: return
        if 'active_model' not in self.session_data: self.session_data['active_model'] = {}
        self.session_data['active_model']['name'] = full_name
        LOGGER.info(f"Command Center: AI Model switched to {full_name}")
        self.validate_all()

    def populate_devices(self):
        self.itv_combo.clear()
        self.mic_combo.clear()
        for dev in self.devices["loopback"]: self.itv_combo.addItem(dev["name"], dev["id"])
        for dev in self.devices["mics"]: self.mic_combo.addItem(dev["name"], dev["id"])
        if self.itv_combo.count() == 0: self.itv_combo.addItem("No WASAPI Loopback Found", -1)
        if self.mic_combo.count() == 0: self.mic_combo.addItem("No Microphone Found", -1)

    def load_saved_settings(self):
        path = get_settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    settings = json.load(f)
                    for i in range(self.itv_combo.count()):
                        if self.itv_combo.itemData(i) == settings.get("interviewer_device_id"):
                            self.itv_combo.setCurrentIndex(i)
                    for i in range(self.mic_combo.count()):
                        if self.mic_combo.itemData(i) == settings.get("mic_device_id"):
                            self.mic_combo.setCurrentIndex(i)
            except: pass

    def on_device_selection_changed(self):
        self.audio_engine.stop_capture()
        itv_id = self.itv_combo.currentData()
        mic_id = self.mic_combo.currentData()
        
        # v1.8.16: Robust mapping to ensure None is passed for system defaults
        # itv_id or mic_id will be index ints, or -1 if "No device found"
        # We only start if at least one side is possibly valid
        itv_idx = itv_id if (itv_id is not None and itv_id != -1) else None
        mic_idx = mic_id if (mic_id is not None and mic_id != -1) else None
        
        self.audio_engine.start_capture(
            interviewer_idx=itv_idx,
            user_idx=mic_idx
        )
        self.validate_all()

    def update_meters(self):
        self.itv_meter.setValue(self.audio_engine.interviewer_level)
        self.mic_meter.setValue(self.audio_engine.user_level)

    def validate_all(self):
        if not hasattr(self, 'root_layout'): return
        if not hasattr(self, 'start_btn') or self.start_btn is None: return
        
        has_itv = hasattr(self, 'itv_combo') and self.itv_combo.currentData() != -1
        has_mic = hasattr(self, 'mic_combo') and self.mic_combo.currentData() != -1
        # v1.8.10: Decoupled AI check - if models are found or selected, it's green
        has_ai = self.model_selector.count() > 0 or self.model_selector.currentText() != ""
        
        # Robust Context Check: Support both legacy and new keys
        ctx_text = self.session_data.get("resume_text") or self.session_data.get("resume_data") or ""
        has_context = len(str(ctx_text)) > 20 # Loosened for short resumes
        
        self.start_btn.setEnabled(has_itv and has_mic and has_ai and has_context)

    def finalize_and_start(self):
        # Improved Launch Logic: Don't block UI if pre-warm is already running
        self.start_btn.setText("LAUNCHING...")
        self.start_btn.setEnabled(False)
        self.do_launch()

    def do_launch(self):

        hw_config = {
            "interviewer_device_id": self.itv_combo.currentData(),
            "mic_device_id": self.mic_combo.currentData()
        }
        with open(get_settings_path(), "w") as f:
            json.dump(hw_config, f)
            
        self.audio_engine.stop_capture()
        self.meter_timer.stop()
        self.session_data['disable_stealth'] = not self.stealth_toggle.isChecked()
        
        # v1.8.12: Emit both configs to maintain sync
        self.ready_to_start.emit(hw_config, self.session_data)

    def prewarm_stt(self):
        """Pre-loads the heavy STT/Whisper models in the background."""
        try:
            from agent_core.stt_service import STTService
            STTService() # Triggers singleton init
            LOGGER.info("STT Engine Pre-warmed successfully.")
        except Exception as e:
            LOGGER.error(f"STT Pre-warm failed: {e}")
