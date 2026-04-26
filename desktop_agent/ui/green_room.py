import json
import os
import time
import logging
import threading
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QComboBox, QPushButton, QProgressBar, 
                             QFrame, QScrollArea, QSizePolicy, QCheckBox, QGridLayout)
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

class GreenRoom(QMainWindow):
    """
    CareerCaster v1.7 - Intelligent Command Center.
    Centralizes all AI reasoning and hardware control.
    """
    ready_to_start = pyqtSignal(dict)

    def __init__(self, session_data=None):
        super().__init__()
        self.session_data = session_data or {}
        self.setWindowTitle("CareerCaster Pro")
        self.setFixedWidth(500)
        self.setMinimumHeight(600)
        self.setMaximumHeight(900)
        
        # 1. UI ROOT CONSTRUCTION
        self.root_widget = QWidget()
        self.root_widget.setMinimumHeight(750)
        self.root_layout = QVBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(30, 40, 30, 40)
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
            
        # Hardware Setup
        try:
            from agent_core.audio_scanner import AudioScanner
            from agent_core.audio_capture import AudioCaptureEngine
            self.scanner = AudioScanner()
            self.audio_engine = AudioCaptureEngine()
            self.devices = self.scanner.get_wasapi_devices() or {"loopback": [], "mics": []}
        except Exception as e:
            LOGGER.error(f"Hardware initialization failed: {e}")
            self.devices = {"loopback": [], "mics": []}
        
        # Initial context refresh (Safe: atoms are anchored)
        self.refresh_context()

        # Init hardware meters
        self.meter_timer = QTimer()
        self.meter_timer.timeout.connect(self.update_meters)
        self.meter_timer.start(50)
        
        # Populate and Load
        self.populate_devices()
        self.load_saved_settings()
        
        # Background Discovery
        threading.Thread(target=self.discover_ai_models, daemon=True).start()
        
        # Event Handlers
        self.itv_combo.currentIndexChanged.connect(self.on_device_selection_changed)
        self.mic_combo.currentIndexChanged.connect(self.on_device_selection_changed)
        self.model_selector.currentTextChanged.connect(self.on_model_changed)
        self.on_device_selection_changed()

    def setup_stylesheet(self):
        """Solid-State Professional Theme - High Reliability & Contrast."""
        self.setStyleSheet("""
            QMainWindow, QScrollArea, QWidget#MainContainer {
                background-color: #0B0D11;
                border: none;
            }
            QScrollArea { border: none; }
            
            /* Labels */
            QLabel {
                color: #A0AAB7;
                font-family: 'Segoe UI', system-ui;
                font-size: 13px;
                background: transparent;
            }
            
            /* High-Visibility Section Headers */
            QLabel#SectionHeader {
                color: #00E5FF;
                font-weight: 800;
                font-size: 11px;
                letter-spacing: 1.5px;
                text-transform: uppercase;
                margin-bottom: 5px;
            }
            
            /* Data Display */
            QLabel#DataValue {
                color: #FFFFFF;
                font-size: 15px;
                font-weight: 600;
            }

            /* Solid Professional Cards */
            QFrame#ControlCard {
                background-color: #161A21;
                border: 1px solid #252A34;
                border-radius: 12px;
            }
            QFrame#ControlCard:hover {
                border: 1px solid #303743;
            }

            /* Component Overrides */
            QComboBox {
                background-color: #1C222D;
                border: 1px solid #313948;
                border-radius: 8px;
                padding: 12px 15px;
                color: #FFFFFF;
                font-size: 13px;
            }
            QComboBox:hover { border: 1px solid #445065; }
            QComboBox QAbstractItemView {
                background-color: #1C222D;
                color: white;
                selection-background-color: #00E5FF;
                selection-color: black;
            }

            QProgressBar {
                background-color: #0D1014;
                border: 1px solid #1C222D;
                border-radius: 3px;
                height: 5px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #00E5FF;
                border-radius: 2px;
            }

            /* Main Action Button */
            QPushButton#ActionBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00E5FF, stop:1 #00A3FF);
                color: #000000;
                font-weight: 800;
                font-size: 15px;
                border-radius: 12px;
                padding: 20px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#ActionBtn:hover {
                background: #00FBFF;
            }
            QPushButton#ActionBtn:disabled {
                background: #252A34;
                color: #4C566A;
                border: 1px solid #252A34;
            }
            
            QCheckBox { color: #8F9BA8; font-size: 12px; spacing: 10px; }
            QCheckBox::indicator { width: 20px; height: 20px; border-radius: 5px; border: 1px solid #313948; background: #1C222D; }
            QCheckBox::indicator:checked { background-color: #00E5FF; border: 1px solid #00E5FF; }

            /* Professional Scrollbar */
            QScrollBar:vertical { background: #0B0D11; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #1C222D; border-radius: 5px; min-height: 30px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

    def init_ui_sections(self):
        """Construct a clean, professional bento-style setup screen."""
        # --- 1. BRANDING HEADER ---
        header = QWidget()
        header_lay = QVBoxLayout(header)
        header_lay.setContentsMargins(0, 0, 0, 30)
        
        pre_title = QLabel("INTERVIEW ASSISTANT")
        pre_title.setObjectName("SectionHeader")
        
        main_title = QLabel("CAREERCASTER")
        main_title.setStyleSheet("font-size: 34px; font-weight: 900; color: #FFFFFF; letter-spacing: -1.5px;")
        
        header_lay.addWidget(pre_title)
        header_lay.addWidget(main_title)
        self.root_layout.addWidget(header)

        # --- 2. AUDIO HARDWARE SECTION ---
        audio_card = QFrame()
        audio_card.setObjectName("ControlCard")
        audio_lay = QVBoxLayout(audio_card)
        audio_lay.setContentsMargins(25, 25, 25, 25)
        audio_lay.setSpacing(20)

        h_audio = QLabel("SYSTEM AUDIO SETUP")
        h_audio.setObjectName("SectionHeader")
        audio_lay.addWidget(h_audio)

        # Output Monitor
        v_out = QVBoxLayout()
        v_out.setSpacing(8)
        lbl_out = QLabel("INTERVIEWER SOURCE (Speakers/Headphones)")
        lbl_out.setStyleSheet("color: #6B7280; font-weight: 700; font-size: 11px;")
        v_out.addWidget(lbl_out)
        self.itv_combo = QComboBox()
        v_out.addWidget(self.itv_combo)
        self.itv_meter = QProgressBar()
        v_out.addWidget(self.itv_meter)
        audio_lay.addLayout(v_out)

        # Input Monitor
        v_in = QVBoxLayout()
        v_in.setSpacing(8)
        lbl_in = QLabel("YOUR MICROPHONE SOURCE")
        lbl_in.setStyleSheet("color: #6B7280; font-weight: 700; font-size: 11px;")
        v_in.addWidget(lbl_in)
        self.mic_combo = QComboBox()
        v_in.addWidget(self.mic_combo)
        self.mic_meter = QProgressBar()
        v_in.addWidget(self.mic_meter)
        audio_lay.addLayout(v_in)
        
        self.root_layout.addWidget(audio_card)

        # --- 3. SESSION CONTEXT SECTION ---
        session_card = QFrame()
        session_card.setObjectName("ControlCard")
        session_lay = QVBoxLayout(session_card)
        session_lay.setContentsMargins(25, 25, 25, 25)
        session_lay.setSpacing(12)

        h_session = QLabel("INTERVIEW DATA SUMMARY")
        h_session.setObjectName("SectionHeader")
        session_lay.addWidget(h_session)

        self.candidate_label = QLabel("IDENTIFIED CANDIDATE: ...")
        self.candidate_label.setObjectName("DataValue")
        self.role_label = QLabel("TARGET POSITION: ...")
        self.role_label.setObjectName("DataValue")
        
        session_lay.addWidget(self.candidate_label)
        session_lay.addWidget(self.role_label)
        
        self.context_status = QLabel("● RESUME CONTEXT LOADED")
        self.context_status.setStyleSheet("color: #10B981; font-weight: 800; font-size: 10px; margin-top: 5px;")
        session_lay.addWidget(self.context_status)
        
        self.root_layout.addWidget(session_card)

        # --- 4. AI CONFIGURATION SECTION ---
        ai_card = QFrame()
        ai_card.setObjectName("ControlCard")
        ai_lay = QVBoxLayout(ai_card)
        ai_lay.setContentsMargins(25, 25, 25, 25)
        ai_lay.setSpacing(15)

        h_ai = QLabel("AI CO-PILOT CONFIG")
        h_ai.setObjectName("SectionHeader")
        ai_lay.addWidget(h_ai)

        ai_row = QHBoxLayout()
        self.model_selector = QComboBox()
        self.model_selector.setMinimumWidth(250)
        ai_row.addWidget(self.model_selector)
        
        stat_box = QVBoxLayout()
        stat_box.setSpacing(4)
        self.status_msg = QLabel("CONNECTING...")
        self.status_msg.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #4B5563; font-weight: bold;")
        self.status_led = QLabel()
        self.status_led.setFixedSize(35, 4)
        self.status_led.setStyleSheet("background: #313948; border-radius: 2px;")
        stat_box.addWidget(self.status_msg)
        stat_box.addWidget(self.status_led)
        
        ai_row.addLayout(stat_box)
        ai_row.addStretch()
        ai_lay.addLayout(ai_row)

        self.stealth_toggle = QCheckBox("HIDE INTERFACE ON START (STEALTH MODE)")
        self.stealth_toggle.setChecked(not self.session_data.get("disable_stealth", False))
        ai_lay.addWidget(self.stealth_toggle)

        self.root_layout.addWidget(ai_card)

        # --- 5. INITIALIZE ACTION ---
        self.root_layout.addStretch()
        
        self.start_btn = QPushButton("FINALIZE & START COPILOT")
        self.start_btn.setObjectName("ActionBtn")
        self.start_btn.setEnabled(False)
        self.start_btn.setMinimumHeight(65)
        self.start_btn.clicked.connect(self.finalize_and_start)
        self.root_layout.addWidget(self.start_btn)

        foot = QLabel("SECURE ENCRYPTED SESSION • v1.8 PRO")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        foot.setStyleSheet("color: #4B5563; font-size: 10px; font-weight: bold; margin-top: 15px;")
        self.root_layout.addWidget(foot)

    def discover_ai_models(self):
        """V1.7: Auto-Tests AI connectivity and identifies available models."""
        if not self.api_key:
            QTimer.singleShot(0, lambda: self.on_ai_fail("API Key Missing"))
            return
            
        start = time.time()
        test_list = ["gemini-3-flash-preview", "gemini-1.5-flash", "gemini-1.5-pro"]
        success_list = []
        
        try:
            client = genai.Client(api_key=self.api_key)
            for m in test_list:
                try:
                    client.models.generate_content(model=m, contents="ping")
                    success_list.append(m)
                except: continue
            
            if success_list:
                self.api_latency = int((time.time() - start) * 1000)
                self.available_models = success_list
                QTimer.singleShot(0, self.on_ai_success)
            else:
                QTimer.singleShot(0, lambda: self.on_ai_fail("API Rejected Ping"))
        except Exception as e:
            QTimer.singleShot(0, lambda: self.on_ai_fail(str(e)))

    def on_ai_success(self):
        self.model_selector.clear()
        self.model_selector.addItems(self.available_models)
        self.model_selector.setEnabled(True)
        
        if self.active_model_name in self.available_models:
            self.model_selector.setCurrentText(self.active_model_name)
            
        self.status_led.setStyleSheet("background-color: #00FF7F; border-radius: 2px;")
        self.status_msg.setText(f"SECURE ({self.api_latency}ms)")
        self.status_msg.setStyleSheet("font-family: 'Consolas'; color: #00FF88; font-weight: bold; font-size: 11px;")
        self.validate_all()

    def on_ai_fail(self, err):
        self.status_led.setStyleSheet("background-color: #FF4500; border-radius: 2px;")
        self.status_msg.setText(f"OFFLINE ({err[:25]})")
        self.status_msg.setStyleSheet("font-family: 'Consolas'; color: #FF4500; font-weight: bold; font-size: 11px;")
        self.validate_all()

    def on_model_changed(self, name):
        if 'active_model' not in self.session_data: self.session_data['active_model'] = {}
        self.session_data['active_model']['name'] = name
        LOGGER.info(f"Command Center: AI Model switched to {name}")

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
        if itv_id != -1 or mic_id != -1:
            self.audio_engine.start_capture(
                interviewer_idx=itv_id if itv_id != -1 else None,
                user_idx=mic_id if mic_id != -1 else None
            )
        self.validate_all()

    def update_meters(self):
        self.itv_meter.setValue(self.audio_engine.interviewer_level)
        self.mic_meter.setValue(self.audio_engine.user_level)

    def validate_all(self):
        if not hasattr(self, 'root_layout'): return
        if not hasattr(self, 'start_btn') or self.start_btn is None: return
        if not hasattr(self, 'api_latency'): return
        
        has_itv = hasattr(self, 'itv_combo') and self.itv_combo.currentData() != -1
        has_mic = hasattr(self, 'mic_combo') and self.mic_combo.currentData() != -1
        has_ai = self.api_latency != -1
        has_context = len(self.session_data.get("resume_data", "")) > 50
        self.start_btn.setEnabled(has_itv and has_mic and has_ai and has_context)

    def finalize_and_start(self):
        with open(get_settings_path(), "w") as f:
            json.dump({
                "interviewer_device_id": self.itv_combo.currentData(),
                "mic_device_id": self.mic_combo.currentData()
            }, f)
        self.audio_engine.stop_capture()
        self.meter_timer.stop()
        self.session_data['disable_stealth'] = not self.stealth_toggle.isChecked()
        self.ready_to_start.emit(self.session_data)

    def refresh_context(self):
        if not hasattr(self, 'root_layout'): return
        if not hasattr(self, 'session_data'): return
        name = self.session_data.get("candidate_name") or self.session_data.get("user_name", "Candidate")
        role = self.session_data.get("target_role") or "Target Performance"
        
        self.setWindowTitle(f"CAREERCASTER | {name.upper()}")
        
        if hasattr(self, 'candidate_label'):
            self.candidate_label.setText(f"IDENTIFIED CANDIDATE: <b>{name.upper()}</b>")
        if hasattr(self, 'role_label'):
            self.role_label.setText(f"TARGET POSITION: <b>{role.upper()}</b>")
            
        self.validate_all()
