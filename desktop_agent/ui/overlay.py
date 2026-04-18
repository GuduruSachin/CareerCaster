import re
import logging
from PyQt6.QtWidgets import (QMainWindow, QLabel, QVBoxLayout, QHBoxLayout, 
                             QWidget, QScrollArea, QFrame, QSizePolicy,
                             QGraphicsOpacityEffect, QLineEdit)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QMouseEvent, QResizeEvent

from .styles import (MAIN_WINDOW_STYLE, get_bubble_style, CONTENT_LABEL_STYLE, 
                     STATUS_BAR_STYLE, READY_STYLE, THINKING_STYLE, ERROR_STYLE, 
                     AI_LABEL_STYLE, HEADER_TITLE_STYLE, HEADER_SESSION_STYLE)
from core.ai_engine import AIWorker

LOGGER = logging.getLogger("CareerCaster")

class StealthOverlay(QMainWindow):
    """
    CareerCaster v1.1 - Modular Stealth Overlay.
    Handles static opacity, chat bubble injection, and input.
    """
    def __init__(self, session_data=None):
        super().__init__()
        
        self.session_data = session_data or {}
        self.api_key = self.session_data.get("api_key")
        
        # Dashboard Sync: Dynamic Session Properties
        active_model_info = self.session_data.get("active_model", {})
        self.model_name = active_model_info.get("name", "gemini-3-flash-preview")
        
        # State Management: Prioritize explicit session flags
        self.preview_mode_active = self.session_data.get("preview_mode", False)
        self.stealth_mode_active = self.session_data.get("stealth_mode", True)
        self.test_mode_active = self.session_data.get("test_mode", False)
        
        # UI Attributes & Performance Settings
        opacity = 0.85 if self.stealth_mode_active else 1.0
        self.setWindowOpacity(opacity)
        self.setMinimumSize(400, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        session_id = self.session_data.get("id", "DIAG-1.1")
        project_title = self.session_data.get("project", "CareerCaster Agent")
        
        self.drag_pos = QPoint()
        self.setWindowTitle(f"CareerCaster - {project_title}")
        self.resize(450, 600)

        # UI State for streaming
        self.current_response_bubble = None
        self.current_response_label = None
        self.current_response_text = ""
        self.ai_thread = None

        # Apply Global Theme
        self.setStyleSheet(MAIN_WINDOW_STYLE)

        # Main Root Container
        self.root_widget = QWidget()
        self.root_layout = QVBoxLayout(self.root_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        self.setCentralWidget(self.root_widget)

        # --- SECTION A: HEADER ---
        self.header = QFrame()
        self.header.setObjectName("header")
        self.header.setFixedHeight(60)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 0, 15, 0)

        self.title_label = QLabel(project_title)
        self.title_label.setStyleSheet(HEADER_TITLE_STYLE)
        
        self.session_label = QLabel(f"ID: {session_id}")
        self.session_label.setStyleSheet(HEADER_SESSION_STYLE)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.session_label)
        self.root_layout.addWidget(self.header)

        # --- SECTION B: MESSAGE HUB ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.chat_container = QWidget()
        self.chat_container.setObjectName("chat_container")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(20, 15, 20, 15)
        self.chat_layout.setSpacing(15)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.addStretch()
        
        self.scroll.setWidget(self.chat_container)
        self.root_layout.addWidget(self.scroll)
        self.scroll.verticalScrollBar().rangeChanged.connect(self.request_scroll_update)

        # --- SECTION C: MOCK INPUT ---
        self.input_frame = QFrame()
        self.input_frame.setFixedHeight(50)
        self.input_frame.setStyleSheet("background-color: #121212; border-top: 1px solid #1A1A1A;")
        input_layout = QHBoxLayout(self.input_frame)
        input_layout.setContentsMargins(15, 5, 15, 5)

        self.mock_input = QLineEdit()
        self.mock_input.setPlaceholderText("Mock Interview Input (Press Enter)...")
        self.mock_input.returnPressed.connect(self.start_ai_query)
        input_layout.addWidget(self.mock_input)

        self.root_layout.addWidget(self.input_frame)

        # --- SECTION D: STATUS BAR ---
        self.status_bar = QFrame()
        self.status_bar.setFixedHeight(35)
        self.status_bar.setStyleSheet(STATUS_BAR_STYLE)
        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(15, 0, 15, 0)

        self.status_label = QLabel("SYSTEM: READY")
        self.status_label.setStyleSheet(READY_STYLE)
        
        # Pulsing Heartbeat LED
        self.ai_indicator_container = QWidget()
        ai_indicator_layout = QHBoxLayout(self.ai_indicator_container)
        ai_indicator_layout.setContentsMargins(0, 0, 0, 0)
        ai_indicator_layout.setSpacing(5)

        self.ai_indicator_dot = QLabel("●")
        self.ai_indicator_dot.setStyleSheet("color: #00FFFF; font-size: 12px;")
        self.pulse_effect = QGraphicsOpacityEffect(self.ai_indicator_dot)
        self.ai_indicator_dot.setGraphicsEffect(self.pulse_effect)
        
        self.pulse_anim = QPropertyAnimation(self.pulse_effect, b"opacity")
        self.pulse_anim.setDuration(1000)
        self.pulse_anim.setStartValue(0.1); self.pulse_anim.setEndValue(1.0)
        self.pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.pulse_anim.setLoopCount(-1)
        self.pulse_anim.start()

        self.ai_label = QLabel("CONNECTION STABLE")
        self.ai_label.setStyleSheet(AI_LABEL_STYLE)

        ai_indicator_layout.addWidget(self.ai_indicator_dot)
        ai_indicator_layout.addWidget(self.ai_label)

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.ai_indicator_container)
        self.root_layout.addWidget(self.status_bar)

    def inject_message(self, text, sender="SYSTEM", is_new_stream=False):
        bubble = QFrame()
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(15, 10, 15, 10)
        bubble_layout.setSpacing(5)
        
        border_color = "#00FFFF" if sender == "ENGINE" else ("#FFAA00" if sender == "SYSTEM" else "#FFFFFF")
        bubble.setStyleSheet(get_bubble_style(border_color))
        
        header_label = QLabel(f"{sender}:")
        header_label.setStyleSheet(f"color: {border_color}; font-weight: bold; font-size: 10px; font-family: 'Segoe UI'; text-transform: uppercase;")
        bubble_layout.addWidget(header_label)

        content_label = QLabel(self._process_text(text))
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_label.setStyleSheet(CONTENT_LABEL_STYLE)
        bubble_layout.addWidget(content_label)
        
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        
        if is_new_stream:
            self.current_response_bubble = bubble
            self.current_response_label = content_label
            self.current_response_text = text
            
        return content_label

    def _process_text(self, text):
        processed = re.sub(r'`([^`]+)`', r'<span style="font-family: Consolas; background-color: #000000; color: #00FFFF; padding: 2px;">\1</span>', text)
        return processed

    def start_ai_query(self):
        query = self.mock_input.text().strip()
        if not query: return
        
        self.mock_input.clear()
        self.inject_message(query, sender="USER")
        
        # Requirement 1: Only mock if Preview Mode is explicitly True
        if self.preview_mode_active:
            self.inject_message("PREVIEW MODE: (AI Query Mocked) " + query, sender="SYSTEM")
            return

        # LIVE ENGINE TRIGGER
        # Verify API key before starting thread
        if not self.api_key:
            self.handle_ai_error("API Key missing. Please check dashboard session.")
            return

        # Prepare for streaming
        self.inject_message("", sender="ENGINE", is_new_stream=True)
        
        # Visual Confirmation: System moves to Amber Thinking state
        self.status_label.setText("SYSTEM: THINKING...")
        self.status_label.setStyleSheet(THINKING_STYLE)

        # Requirement 2: Hook up current model_name
        self.ai_thread = AIWorker(self.api_key, query, model_name=self.model_name)
        self.ai_thread.token_received.connect(self.update_live_response)
        self.ai_thread.finished.connect(self.ai_query_finished)
        self.ai_thread.error_occurred.connect(self.handle_ai_error)
        self.ai_thread.start()

    def update_live_response(self, token):
        self.current_response_text += token
        self.current_response_label.setText(self._process_text(self.current_response_text))
        self.do_scroll_to_bottom()

    def ai_query_finished(self):
        self.status_label.setText("SYSTEM: READY")
        self.status_label.setStyleSheet(READY_STYLE)

    def handle_ai_error(self, err):
        self.status_label.setText("SYSTEM: ERROR")
        self.status_label.setStyleSheet(ERROR_STYLE)
        self.inject_message(f"AI ERROR: {err}", sender="SYSTEM")

    def request_scroll_update(self, min_val=0, max_val=0):
        QTimer.singleShot(10, self.do_scroll_to_bottom)

    def do_scroll_to_bottom(self):
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        RESIZE_MARGIN = 5
        rect = self.rect()
        pos = event.position()
        if (pos.x() < RESIZE_MARGIN or pos.x() > rect.width() - RESIZE_MARGIN or
            pos.y() < RESIZE_MARGIN or pos.y() > rect.height() - RESIZE_MARGIN):
            event.ignore(); return
        if event.button() == Qt.MouseButton.LeftButton:
            if pos.y() < self.header.height():
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
            else:
                event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            if not self.drag_pos.isNull():
                self.move(event.globalPosition().toPoint() - self.drag_pos)
                event.accept()
