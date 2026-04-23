import json
import os
import time
import logging
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QComboBox, QPushButton, QProgressBar, 
                             QFrame, QScrollArea, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

# Library Imports
try:
    from google import genai
except ImportError:
    genai = None

from core.paths import get_settings_path
from .styles import (MAIN_WINDOW_STYLE, STATUS_BAR_STYLE, READY_STYLE, THINKING_STYLE)
from agent_core.audio_scanner import AudioScanner
from agent_core.audio_capture import AudioCaptureEngine

LOGGER = logging.getLogger("CareerCaster")

class GreenRoom(QMainWindow):
    """
    CareerCaster v1.2 - Hardware Validation Engine.
    Ensures devices and AI connectivity are nominal before the interview.
    """
    ready_to_start = pyqtSignal(dict) # Emits dict of selected device indices

    def __init__(self, session_data=None):
        super().__init__()
        self.session_data = session_data or {}
        self.setWindowTitle("CareerCaster Pro")
        self.setFixedWidth(500)
        self.setMinimumHeight(500)
        self.setMaximumHeight(900)
        
        # Hardware Setup
        self.scanner = AudioScanner()
        self.audio_engine = AudioCaptureEngine()
        self.devices = self.scanner.get_wasapi_devices()
        
        # State
        self.selected_interviewer = -1
        self.selected_mic = -1
        self.api_latency = -1
        self.is_scanning = False
        
        # UI Root - Scroll Area Implementation
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("MainScrollArea")
        
        self.root_widget = QWidget()
        self.root_widget.setMinimumHeight(750)
        self.root_layout = QVBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(30, 40, 30, 40)
        self.root_layout.setSpacing(25)
        
        self.scroll_area.setWidget(self.root_widget)
        self.setCentralWidget(self.scroll_area)

        # 1. UI ATOM INITIALIZATION (MANDATORY BEFORE ANY REFRESH OR TIMERS)
        self.setStyleSheet(f"""
            QMainWindow, QScrollArea#MainScrollArea, QWidget#MainScrollArea > QWidget {{ 
                background-color: #0A0A0A; 
            }}
            QScrollArea {{ border: none; background: #0A0A0A; }}
            QLabel {{ color: #E0E0E0; font-family: 'Segoe UI'; }}
            QComboBox {{ 
                background-color: #1A1A1A; color: white; border: 1px solid #333; 
                padding: 8px; border-radius: 4px; font-size: 13px;
            }}
            QPushButton {{ 
                background-color: #00FFFF; color: black; font-weight: bold; 
                padding: 12px; border-radius: 6px; border: none; font-size: 14px;
            }}
            QPushButton:disabled {{ background-color: #333; color: #666; }}
            QPushButton:hover:!disabled {{ background-color: #00D1D1; }}
            QProgressBar {{ 
                border: 1px solid #222; background-color: #111; 
                border-radius: 3px; text-align: center; height: 12px; 
            }}
            QProgressBar::chunk {{ background-color: #00FFFF; }}
            .SectionFrame {{ 
                background-color: #121212; border: 1px solid #222; 
                border-radius: 8px; padding: 15px; 
            }}
            .Title {{ font-size: 20px; font-weight: bold; color: #FFFFFF; font-family: 'Space Grotesk', sans-serif; }}
            .SubTitle {{ font-size: 12px; color: #AAAAAA; text-transform: uppercase; letter-spacing: 1px; }}
            
            /* High-Contrast Popups for HP Screens */
            QMessageBox {{ background-color: #121212; }}
            QMessageBox QLabel {{ color: #FFFFFF; font-weight: bold; font-size: 14px; }}
            QMessageBox QPushButton {{ min-width: 100px; background-color: #00FFFF; color: black; }}

            /* Tactical Switch (Checkbox/Toggle simulation) */
            QCheckBox {{ color: #E0E0E0; spacing: 10px; font-size: 13px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; background-color: #1A1A1A; border: 1px solid #333; border-radius: 3px; }}
            QCheckBox::indicator:checked {{ background-color: #00FFFF; }}

            /* Stealth Scrollbar CSS */
            QScrollBar:vertical {{
                border: none;
                background: #0A0A0A;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #333333;
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #00FFFF;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # --- SECTION: HEADER ---
        header_label = QLabel("GREEN ROOM")
        header_label.setProperty("class", "Title")
        self.root_layout.addWidget(header_label)
        
        desc_label = QLabel("Validate your setup before entering the stealth interview environment.")
        desc_label.setWordWrap(True)
        self.root_layout.addWidget(desc_label)

        # --- SECTION A: AUDIO MATRIX ---
        audio_frame = QFrame()
        audio_frame.setProperty("class", "SectionFrame")
        audio_layout = QVBoxLayout(audio_frame)
        audio_layout.addWidget(QLabel("AUDIO MATRIX")).setProperty("class", "SubTitle")

        # Interviewer Selection
        audio_layout.addWidget(QLabel("Interviewer Source (System Output):"))
        self.itv_combo = QComboBox()
        self.itv_combo.addItem("Searching WASAPI Loopback...", -1)
        audio_layout.addWidget(self.itv_combo)
        
        self.itv_meter = QProgressBar()
        self.itv_meter.setValue(0)
        audio_layout.addWidget(self.itv_meter)

        audio_layout.addSpacing(10)

        # Mic Selection
        audio_layout.addWidget(QLabel("My Microphone (Standard Input):"))
        self.mic_combo = QComboBox()
        self.mic_combo.addItem("Searching Microphones...", -1)
        audio_layout.addWidget(self.mic_combo)
        
        self.mic_meter = QProgressBar()
        self.mic_meter.setValue(0)
        audio_layout.addWidget(self.mic_meter)
        self.root_layout.addWidget(audio_frame)

        # --- SECTION B: AI HEALTH ---
        ai_frame = QFrame()
        ai_frame.setProperty("class", "SectionFrame")
        ai_layout = QVBoxLayout(ai_frame)
        ai_layout.addWidget(QLabel("AI CONNECTIVITY")).setProperty("class", "SubTitle")
        
        ai_h_layout = QHBoxLayout()
        self.status_led = QLabel()
        self.status_led.setFixedSize(12, 12)
        self.status_led.setStyleSheet("background-color: #555555; border-radius: 6px;")
        
        self.latency_label = QLabel("Latency: UNKNOWN")
        self.test_api_btn = QPushButton("TEST CONNECTION")
        self.test_api_btn.setFixedWidth(180)
        self.test_api_btn.clicked.connect(self.test_api_latency)
        
        ai_h_layout.addWidget(self.status_led)
        ai_h_layout.addSpacing(10)
        ai_h_layout.addWidget(self.latency_label)
        ai_h_layout.addStretch()
        ai_h_layout.addWidget(self.test_api_btn)
        ai_layout.addLayout(ai_h_layout)
        self.root_layout.addWidget(ai_frame)

        # --- SECTION C: TACTICAL SETTINGS (MIGRATED FROM DASHBOARD) ---
        settings_frame = QFrame()
        settings_frame.setProperty("class", "SectionFrame")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("TACTICAL SETTINGS")).setProperty("class", "SubTitle")
        
        # Model Selection
        settings_layout.addWidget(QLabel("Active AI Model:"))
        self.model_selector = QComboBox()
        # Populate with models from session or defaults
        default_models = ["gemini-3-flash-preview", "gemini-1.5-flash", "gemini-1.5-pro"]
        active_model_name = self.session_data.get("active_model", {}).get("name", "gemini-3-flash-preview")
        
        for m_name in default_models:
            self.model_selector.addItem(m_name)
            if m_name == active_model_name:
                self.model_selector.setCurrentText(m_name)
        
        settings_layout.addWidget(self.model_selector)
        
        # Stealth Toggle
        from PyQt6.QtWidgets import QCheckBox
        self.stealth_toggle = QCheckBox("Enable Stealth Overlay (Screen Protection)")
        self.stealth_toggle.setChecked(not self.session_data.get("disable_stealth", False))
        settings_layout.addWidget(self.stealth_toggle)
        
        self.root_layout.addWidget(settings_frame)

        # --- SECTION D: CONTEXT PREVIEW ---
        context_frame = QFrame()
        context_frame.setProperty("class", "SectionFrame")
        context_layout = QVBoxLayout(context_frame)
        context_layout.addWidget(QLabel("SESSION CONTEXT")).setProperty("class", "SubTitle")
        
        self.context_scroll = QScrollArea()
        self.context_scroll.setWidgetResizable(True)
        self.context_scroll.setFixedHeight(120)
        self.context_scroll.setStyleSheet("background-color: #0A0A0A; border: none;")
        
        context_content = QWidget()
        context_content_layout = QVBoxLayout(context_content)
        
        self.project_label = QLabel("Project: N/A")
        self.resume_label = QLabel("Resume: 0 chars loaded.")
        self.jd_label = QLabel("JD: 0 chars loaded.")
        
        context_content_layout.addWidget(self.project_label)
        context_content_layout.addWidget(self.resume_label)
        context_content_layout.addWidget(self.jd_label)
        context_content_layout.addStretch()
        
        self.context_scroll.setWidget(context_content)
        context_layout.addWidget(self.context_scroll)
        self.root_layout.addWidget(context_frame)
        
        # --- FOOTER ---
        self.start_btn = QPushButton("START INTERVIEW")
        self.start_btn.setFixedHeight(55)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.finalize_and_start)
        self.root_layout.addWidget(self.start_btn)
        
        # Stretch at bottom for flexible layout
        self.root_layout.addStretch()

        # Watchdog Timer
        self.watchdog = QTimer()
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(lambda: self.on_latency_fail("TIMEOUT"))
        
        # Initial context refresh (Now safe as all labels and buttons are defined)
        self.refresh_context()

        # Init hardware meters
        self.meter_timer = QTimer()
        self.meter_timer.timeout.connect(self.update_meters)
        self.meter_timer.start(50) # 20fps for smooth visual
        
        # Populate Dropdowns and Load Settings
        self.populate_devices()
        self.load_saved_settings()
        
        # Connect change events
        self.itv_combo.currentIndexChanged.connect(self.on_device_selection_changed)
        self.mic_combo.currentIndexChanged.connect(self.on_device_selection_changed)
        self.model_selector.currentTextChanged.connect(self.on_model_changed)
        
        # Immediate start of monitoring (Initial devices)
        self.on_device_selection_changed()

    def populate_devices(self):
        self.itv_combo.clear()
        self.mic_combo.clear()
        
        for dev in self.devices["loopback"]:
            self.itv_combo.addItem(dev["name"], dev["id"])
            
        for dev in self.devices["mics"]:
            self.mic_combo.addItem(dev["name"], dev["id"])
            
        if self.itv_combo.count() == 0 or self.mic_combo.count() == 0:
            self.show_permission_dialog()
            
        if self.itv_combo.count() == 0:
            self.itv_combo.addItem("No Loopback (Check WASAPI Settings)", -1)
        if self.mic_combo.count() == 0:
            self.mic_combo.addItem("No Microphone Found", -1)

    def show_permission_dialog(self):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Hardware Access Restricted")
        msg.setText("CareerCaster cannot access your WASAPI Loopback or Microphone.")
        msg.setInformativeText("Ensure that 'Stereo Mix' or 'Loopback' is enabled in Windows Sound Settings.")
        
        fix_btn = msg.addButton("Auto-Fix (Open Settings)", QMessageBox.ButtonRole.ActionRole)
        msg.addButton(QMessageBox.StandardButton.Ok)
        
        msg.exec()
        
        if msg.clickedButton() == fix_btn:
            os.system("start ms-settings:sound")

    def load_saved_settings(self):
        path = get_settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    settings = json.load(f)
                    itv_id = settings.get("interviewer_device_id")
                    mic_id = settings.get("mic_device_id")
                    
                    # Search and select
                    for i in range(self.itv_combo.count()):
                        if self.itv_combo.itemData(i) == itv_id:
                            self.itv_combo.setCurrentIndex(i)
                            break
                    for i in range(self.mic_combo.count()):
                        if self.mic_combo.itemData(i) == mic_id:
                            self.mic_combo.setCurrentIndex(i)
                            break
            except Exception as e:
                LOGGER.error(f"Failed to load settings: {e}")

    def on_model_changed(self, model_name):
        """Updates the active model in the session data real-time."""
        if 'active_model' not in self.session_data:
            self.session_data['active_model'] = {}
        self.session_data['active_model']['name'] = model_name
        LOGGER.info(f"Tactical Switch: AI Model updated to {model_name}")

    def on_device_selection_changed(self):
        # Stop current capture
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
        
        # Debounced validation of signal
        if self.audio_engine.interviewer_level > 5 or self.audio_engine.user_level > 5:
             self.validate_all()

    def update_status_led(self, state):
        """Changes LED color and label color based on network health."""
        colors = {
            'STABLE': '#00FF7F',  # Spring Green
            'SLOW': '#FFD700',    # Gold
            'OFFLINE': '#FF4500', # Orange Red
            'UNKNOWN': '#555555'  # Gray
        }
        color = colors.get(state, '#555555')
        self.status_led.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
        self.latency_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def test_api_latency(self):
        if not genai:
            self.latency_label.setText("SDK Missing")
            return
            
        api_key = self.session_data.get("api_key")
        if not api_key:
            self.latency_label.setText("No API Key")
            return
            
        self.latency_label.setText("Testing...")
        self.update_status_led('UNKNOWN')
        self.test_api_btn.setEnabled(False)
        
        # Start Watchdog (10 seconds)
        self.watchdog.start(10000)
        
        # Async Ping to prevent UI freeze
        import threading
        def _ping_logic():
            start = time.time()
            try:
                client = genai.Client(api_key=api_key)
                client.models.generate_content(
                    model="gemini-3-flash-preview",
                    contents="ping"
                )
                self.api_latency = int((time.time() - start) * 1000)
                QTimer.singleShot(0, lambda: self.on_latency_success())
            except Exception as e:
                QTimer.singleShot(0, lambda: self.on_latency_fail(str(e)))

        threading.Thread(target=_ping_logic, daemon=True).start()

    def on_latency_success(self):
        self.watchdog.stop()
        self.latency_label.setText(f"Latency: {self.api_latency}ms")
        
        if self.api_latency < 800:
            self.update_status_led('STABLE')
        elif self.api_latency < 2500:
            self.update_status_led('SLOW')
        else:
            self.update_status_led('OFFLINE')
            
        self.test_api_btn.setEnabled(True)
        self.validate_all()

    def on_latency_fail(self, error):
        self.watchdog.stop()
        self.api_latency = -1
        self.latency_label.setText(f"Error: {error[:20]}")
        self.update_status_led('OFFLINE')
        self.test_api_btn.setEnabled(True)
        self.validate_all()

    def validate_all(self):
        # Defensive check to prevent crash if UI is not fully painted or diagnostic heartbeat triggers early
        if not hasattr(self, 'start_btn') or self.start_btn is None:
            return

        # Conditions for enabling START
        has_itv = self.itv_combo.currentData() != -1
        has_mic = self.mic_combo.currentData() != -1
        has_api = self.api_latency != -1
        
        # Bonus: Ensure resume/jd context is present
        has_context = len(self.session_data.get("resume_data", "")) > 100
        
        ready = has_itv and has_mic and has_api and has_context
        self.start_btn.setEnabled(ready)

    def finalize_and_start(self):
        # Save settings for next session
        settings_path = get_settings_path()
        settings = {
            "interviewer_device_id": self.itv_combo.currentData(),
            "mic_device_id": self.mic_combo.currentData()
        }
        with open(settings_path, "w") as f:
            json.dump(settings, f)
            
        # Stop audio testing
        self.audio_engine.stop_capture()
        self.meter_timer.stop()
        
        # Signal ready to start with hardware IDs
        self.ready_to_start.emit(settings)

    def refresh_context(self):
        """Updates UI labels with the latest session data counts and confirms identity."""
        project = self.session_data.get("project", "N/A")
        jd_text = self.session_data.get("job_description", "")
        cv_text = self.session_data.get("resume_data", "")
        
        # Identity Handshake
        candidate_name = self.session_data.get("candidate_name") or self.session_data.get("user_name")
        if candidate_name:
            self.setWindowTitle(f"CareerCaster Pro | {candidate_name}")
        else:
            self.setWindowTitle("CareerCaster Pro")
        
        self.project_label.setText(f"<b>Project:</b> {project}")
        self.resume_label.setText(f"<b>Resume:</b> {len(cv_text)} chars loaded.")
        self.jd_label.setText(f"<b>JD:</b> {len(jd_text)} chars loaded.")
        
        # Log for diagnostics
        LOGGER.info(f"GreenRoom Context Refreshed: Project={project}, CV={len(cv_text)}, JD={len(jd_text)}")
        self.validate_all()
