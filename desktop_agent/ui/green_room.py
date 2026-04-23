import json
import os
import time
import logging
import threading
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QComboBox, QPushButton, QProgressBar, 
                             QFrame, QScrollArea, QSizePolicy, QCheckBox)
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
        
        # AI Logic Sync
        self.api_key = get_master_api_key()
        self.active_model_name = self.session_data.get("active_model", {}).get("name", "gemini-3-flash-preview")
        
        # Hardware Setup
        self.scanner = AudioScanner()
        self.audio_engine = AudioCaptureEngine()
        self.devices = self.scanner.get_wasapi_devices()
        
        # State
        self.api_latency = -1
        self.available_models = []
        
        # UI Root - Scroll Area Implementation
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("MainScrollArea")
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: #0A0A0A; }")
        
        self.root_widget = QWidget()
        self.root_widget.setMinimumHeight(750)
        self.root_layout = QVBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(30, 40, 30, 40)
        self.root_layout.setSpacing(25)
        
        self.scroll_area.setWidget(self.root_widget)
        self.setCentralWidget(self.scroll_area)

        # 1. UI ATOM INITIALIZATION
        self.setup_stylesheet()
        self.init_ui_sections()
        
        # Initial context refresh
        self.refresh_context()

        # Init hardware meters
        self.meter_timer = QTimer()
        self.meter_timer.timeout.connect(self.update_meters)
        self.meter_timer.start(50)
        
        # Populate and Load
        self.populate_devices()
        self.load_saved_settings()
        
        # V1.7 AUTO-DISCOVERY: Run on background thread
        threading.Thread(target=self.discover_ai_models, daemon=True).start()
        
        # Connect change events
        self.itv_combo.currentIndexChanged.connect(self.on_device_selection_changed)
        self.mic_combo.currentIndexChanged.connect(self.on_device_selection_changed)
        self.model_selector.currentTextChanged.connect(self.on_model_changed)
        self.on_device_selection_changed()

    def setup_stylesheet(self):
        self.setStyleSheet(f"""
            QMainWindow, QScrollArea#MainScrollArea, QWidget#MainScrollArea > QWidget {{ 
                background-color: #0A0A0A; 
            }}
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
            
            /* Tactical Switch */
            QCheckBox {{ color: #E0E0E0; spacing: 10px; font-size: 13px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; background-color: #1A1A1A; border: 1px solid #333; border-radius: 3px; }}
            QCheckBox::indicator:checked {{ background-color: #00FFFF; }}

            /* Stealth Scrollbar */
            QScrollBar:vertical {{ border: none; background: #0A0A0A; width: 10px; }}
            QScrollBar::handle:vertical {{ background: #333333; min-height: 20px; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: #00FFFF; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)

    def init_ui_sections(self):
        # HEADER
        header = QLabel("COMMAND CENTER v1.7")
        header.setProperty("class", "Title")
        self.root_layout.addWidget(header)
        
        # --- AUDIO MATRIX ---
        audio_frame = QFrame()
        audio_frame.setProperty("class", "SectionFrame")
        audio_layout = QVBoxLayout(audio_frame)
        audio_layout.addWidget(QLabel("AUDIO MATRIX")).setProperty("class", "SubTitle")
        
        audio_layout.addWidget(QLabel("Interviewer (WASAPI Loopback):"))
        self.itv_combo = QComboBox()
        audio_layout.addWidget(self.itv_combo)
        self.itv_meter = QProgressBar()
        audio_layout.addWidget(self.itv_meter)
        
        audio_layout.addSpacing(10)
        audio_layout.addWidget(QLabel("Mic (Standard Input):"))
        self.mic_combo = QComboBox()
        audio_layout.addWidget(self.mic_combo)
        self.mic_meter = QProgressBar()
        audio_layout.addWidget(self.mic_meter)
        self.root_layout.addWidget(audio_frame)

        # --- TACTICAL SETTINGS ---
        settings_frame = QFrame()
        settings_frame.setProperty("class", "SectionFrame")
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.addWidget(QLabel("TACTICAL SETTINGS")).setProperty("class", "SubTitle")
        
        settings_layout.addWidget(QLabel("Active AI Model:"))
        self.model_selector = QComboBox()
        self.model_selector.addItem("Discovering AI Engines...", -1)
        self.model_selector.setEnabled(False)
        settings_layout.addWidget(self.model_selector)
        
        self.stealth_toggle = QCheckBox("Enable Stealth Overlay (Screen Masking)")
        self.stealth_toggle.setChecked(not self.session_data.get("disable_stealth", False))
        settings_layout.addWidget(self.stealth_toggle)
        
        self.root_layout.addWidget(settings_frame)

        # --- AI HEALTH ---
        ai_frame = QFrame()
        ai_frame.setProperty("class", "SectionFrame")
        ai_layout = QHBoxLayout(ai_frame)
        self.status_led = QLabel()
        self.status_led.setFixedSize(12, 12)
        self.status_led.setStyleSheet("background-color: #555555; border-radius: 6px;")
        self.latency_label = QLabel("AI STATUS: INITIALIZING...")
        ai_layout.addWidget(self.status_led)
        ai_layout.addWidget(self.latency_label)
        ai_layout.addStretch()
        self.root_layout.addWidget(ai_frame)

        # --- FOOTER ---
        self.start_btn = QPushButton("ENGAGE INTERVIEW")
        self.start_btn.setFixedHeight(55)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.finalize_and_start)
        self.root_layout.addWidget(self.start_btn)
        self.root_layout.addStretch()

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
            
        self.status_led.setStyleSheet("background-color: #00FF7F; border-radius: 6px;")
        self.latency_label.setText(f"AI STATUS: SECURE ({self.api_latency}ms)")
        self.validate_all()

    def on_ai_fail(self, err):
        self.status_led.setStyleSheet("background-color: #FF4500; border-radius: 6px;")
        self.latency_label.setText(f"AI STATUS: OFFLINE ({err[:25]})")
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
        if not hasattr(self, 'start_btn') or self.start_btn is None: return
        has_itv = self.itv_combo.currentData() != -1
        has_mic = self.mic_combo.currentData() != -1
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
        name = self.session_data.get("candidate_name") or self.session_data.get("user_name", "Candidate")
        self.setWindowTitle(f"CareerCaster Pro | {name}")
        self.validate_all()
