#!/usr/bin/env pythonw
# Note: Save this file as .pyw or run with pythonw.exe to hide the CMD window on Windows.

import sys
import os
import json
import urllib.parse
import ctypes
import threading
import time

# --- Path Fix for Monorepo ---
# Add the project root to sys.path so 'core' can be found
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from google import genai
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QSystemTrayIcon, QMenu, QScrollArea, QSizeGrip)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread, QTimer, QRect
from PyQt6.QtGui import QColor, QIcon, QAction, QFont, QPainter, QPixmap

# Import modularized audio logic
from core.audio_processor import AudioProcessor
from core.security import SecurityManager
from core.paths import get_sessions_dir

# --- Windows API Constants ---
WDA_EXCLUDEFROMCAPTURE = 0x00000011

class AudioCaptureThread(QThread):
    new_hint = pyqtSignal(str)
    status_update = pyqtSignal(str, str) # status_text, color

    def __init__(self, api_key, context_tags, active_model=None):
        super().__init__()
        self.api_key = api_key
        self.context_tags = context_tags
        self.active_model = active_model or {"name": "gemini-1.5-flash-latest", "sdk": "New (google-genai)", "version": "v1"}
        self.is_running = True
        self.is_muted = False
        self.processor = AudioProcessor()
        
        # Initialize new google-genai client forcing v1beta endpoint as requested
        self.client = genai.Client(
            api_key=self.api_key,
            http_options={'api_version': 'v1beta'}
        )

    def run(self):
        device_index = self.processor.find_wasapi_loopback_device()
        if device_index is None:
            self.status_update.emit("● NO AUDIO", "#FF5555")
            return

        self.status_update.emit("● LISTENING", "#00FF00")
        
        p = self.processor.pa
        try:
            stream = p.open(
                format=self.processor.format,
                channels=self.processor.channels,
                rate=self.processor.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.processor.chunk_size
            )
        except Exception as e:
            print(f"Stream Open Error: {e}")
            self.status_update.emit("● AUDIO ERROR", "#FF5555")
            return

        audio_buffer = []
        # 4 seconds of audio at 16kHz
        buffers_per_chunk = int((self.processor.rate * 4) / self.processor.chunk_size)

        try:
            while self.is_running:
                try:
                    data = stream.read(self.processor.chunk_size, exception_on_overflow=False)
                except Exception:
                    continue
                
                if not self.is_muted:
                    audio_buffer.append(data)
                    
                    if len(audio_buffer) >= buffers_per_chunk:
                        # Process the chunk
                        raw_pcm = b"".join(audio_buffer)
                        # Sliding window: keep last 1 second
                        overlap_buffers = int(self.processor.rate / self.processor.chunk_size)
                        audio_buffer = audio_buffer[-overlap_buffers:]
                        
                        # Send to Gemini
                        self.process_audio_chunk(raw_pcm)
                else:
                    audio_buffer = [] # Clear buffer while muted
                    time.sleep(0.1)
        finally:
            stream.stop_stream()
            stream.close()
            self.processor.close()

    def process_audio_chunk(self, raw_pcm):
        try:
            base64_audio = self.processor.pcm_to_base64_wav(raw_pcm)
            
            prompt = f"""
            You are an interview assistant. Listen to this 4-second audio clip.
            Context Tags: {json.dumps(self.context_tags)}
            
            If you hear a question or key moment, provide a categorized hint.
            Categories:
            [TECHNICAL]: For hard skills/architecture.
            [BEHAVIORAL]: For soft skills/STAR method.
            [URGENT]: For immediate corrections or "Red Flags".
            
            Format: [CATEGORY] Your concise hint here.
            If irrelevant, return an empty string.
            """
            
            # Using New SDK exclusively
            response = self.client.models.generate_content(
                model=self.active_model["name"],
                contents=[
                    prompt,
                    genai.types.Part.from_bytes(
                        data=self.processor.pcm_to_wav_bytes(raw_pcm),
                        mime_type='audio/wav'
                    )
                ]
            )
            hint = response.text.strip()
            
            if hint:
                self.new_hint.emit(hint)
        except Exception as e:
            print(f"AI Processing Error: {e}")

    def stop(self):
        self.is_running = False
        self.wait()

class StealthOverlay(QWidget):
    def __init__(self, session_id, data):
        super().__init__()
        self.session_id = session_id
        self.data = data
        self.old_pos = None
        self.hint_stack = [] # List of (text, timestamp)
        self.audio_thread = None
        
        self.init_ui()
        self.apply_stealth_mode()
        self.start_audio_thread()
        
        # Temporal Decay Timer
        self.decay_timer = QTimer(self)
        self.decay_timer.timeout.connect(self.decay_hints)
        self.decay_timer.start(5000) # Every 5 seconds

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main Container with Rounded Corners and Alpha 0.8
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet("""
            #MainContainer {
                background-color: rgba(20, 20, 20, 204); /* Alpha 0.8 (204/255) */
                border: 1px solid #444;
                border-radius: 15px;
            }
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 10, 12, 12)
        
        # Header Bar
        header_layout = QHBoxLayout()
        
        # Drag Handle
        self.handle = QLabel("⠿") 
        self.handle.setStyleSheet("color: #666; font-size: 18px; font-weight: bold;")
        self.handle.setCursor(Qt.CursorShape.SizeAllCursor)
        
        # Status
        self.status_indicator = QLabel("● INITIALIZING")
        self.status_indicator.setStyleSheet("color: #FFAA00; font-size: 10px; font-weight: bold; font-family: 'Segoe UI', 'Roboto';")
        
        # Control Buttons
        self.screenshot_btn = QPushButton("📸")
        self.screenshot_btn.setFixedSize(28, 28)
        self.screenshot_btn.setStyleSheet("background: transparent; border: none; font-size: 16px;")
        self.screenshot_btn.setToolTip("Take Screenshot")
        self.screenshot_btn.clicked.connect(self.take_screenshot)

        self.mute_btn = QPushButton("🎤")
        self.mute_btn.setFixedSize(28, 28)
        self.mute_btn.setStyleSheet("background: transparent; border: none; font-size: 16px;")
        self.mute_btn.clicked.connect(self.toggle_mute)
        
        self.close_btn = QPushButton("❌")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("background: transparent; color: #FF5555; font-size: 14px; border: none; font-weight: bold;")
        self.close_btn.setToolTip("Kill Interview Process")
        self.close_btn.clicked.connect(self.kill_process)
        
        header_layout.addWidget(self.handle)
        header_layout.addSpacing(10)
        header_layout.addWidget(self.status_indicator)
        header_layout.addStretch()
        header_layout.addWidget(self.screenshot_btn)
        header_layout.addWidget(self.mute_btn)
        header_layout.addWidget(self.close_btn)
        layout.addLayout(header_layout)
        
        # AI Battle Plan
        self.plan_label = QLabel("AI BATTLE PLAN")
        self.plan_label.setStyleSheet("color: #00AAFF; font-size: 10px; font-weight: bold; letter-spacing: 1px; font-family: 'Segoe UI', 'Roboto';")
        layout.addWidget(self.plan_label)
        
        self.plan_display = QLabel(self.data.get("analysis", "No analysis found."))
        self.plan_display.setWordWrap(True)
        self.plan_display.setStyleSheet("color: #BBB; font-size: 12px; padding-bottom: 5px; font-family: 'Segoe UI', 'Roboto';")
        
        plan_scroll = QScrollArea()
        plan_scroll.setWidgetResizable(True)
        plan_scroll.setWidget(self.plan_display)
        plan_scroll.setFixedHeight(70)
        plan_scroll.setStyleSheet("background: transparent; border: none;")
        plan_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(plan_scroll)
        
        layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine, styleSheet="background-color: #333;"))
        
        # Live Feed
        self.live_label = QLabel("LIVE FEED")
        self.live_label.setStyleSheet("color: #FF4444; font-size: 10px; font-weight: bold; letter-spacing: 1px; font-family: 'Segoe UI', 'Roboto';")
        layout.addWidget(self.live_label)
        
        self.live_display = QLabel("Listening for interview questions...")
        self.live_display.setWordWrap(True)
        self.live_display.setTextFormat(Qt.TextFormat.RichText)
        self.live_display.setStyleSheet("color: #FFF; font-size: 13px; font-weight: 500; font-family: 'Segoe UI', 'Roboto';")
        
        live_scroll = QScrollArea()
        live_scroll.setWidgetResizable(True)
        live_scroll.setWidget(self.live_display)
        live_scroll.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(live_scroll)

        # Resize Grip
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setFixedSize(16, 16)
        self.sizegrip.setStyleSheet("background: transparent;")
        
        self.resize(360, 400)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 380, 50)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sizegrip.move(self.width() - self.sizegrip.width(), self.height() - self.sizegrip.height())

    def take_screenshot(self):
        """Captures only the overlay window and saves it to /screenshots."""
        try:
            screenshots_dir = os.path.join(PROJECT_ROOT, "screenshots")
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
            
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = f"CareerCaster_{timestamp}.png"
            filepath = os.path.join(screenshots_dir, filename)
            
            # Capture the widget
            pixmap = self.grab()
            pixmap.save(filepath, "PNG")
            
            self.update_status("● SCREENSHOT SAVED", "#00AAFF")
            QTimer.singleShot(2000, lambda: self.update_status("● LISTENING", "#00FF00"))
            print(f"Screenshot saved: {filepath}")
        except Exception as e:
            print(f"Screenshot Error: {e}")

    def kill_process(self):
        """Gracefully kills the interview process and deletes the session file."""
        try:
            self.audio_thread.stop()
            sessions_dir = get_sessions_dir()
            session_path = os.path.join(sessions_dir, f"{self.session_id}.cc")
            if os.path.exists(session_path):
                os.remove(session_path)
            print(f"Session {self.session_id} cleared.")
        except Exception as e:
            print(f"Error killing process: {e}")
        QApplication.quit()

    def start_audio_thread(self):
        if self.audio_thread:
            self.audio_thread.stop()
            
        self.audio_thread = AudioCaptureThread(
            self.data.get("api_key"),
            self.data.get("context_tags", {}),
            self.data.get("active_model")
        )
        self.audio_thread.new_hint.connect(self.update_live_feed)
        self.audio_thread.status_update.connect(self.update_status)
        self.audio_thread.start()

    def show_session_menu(self):
        """Shows a menu with the 5 most recent sessions."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #222;
                color: #EEE;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #444;
            }
        """)
        
        sessions_dir = get_sessions_dir()
        files = [f for f in os.listdir(sessions_dir) if f.endswith('.cc')]
        # Sort by modification time (most recent first)
        files.sort(key=lambda x: os.path.getmtime(os.path.join(sessions_dir, x)), reverse=True)
        
        for f in files[:5]:
            session_id = f.replace('.cc', '')
            action = QAction(f"Session: {session_id[:8]}...", self)
            action.triggered.connect(lambda checked, sid=session_id: self.load_session(sid))
            menu.addAction(action)
            
        if not files:
            menu.addAction("No sessions found")
            
        menu.exec(self.session_btn.mapToGlobal(QPoint(0, self.session_btn.height())))

    def load_session(self, session_id):
        """Hot-swaps the current session."""
        try:
            sessions_dir = get_sessions_dir()
            session_path = os.path.join(sessions_dir, f"{session_id}.cc")
            
            security = SecurityManager()
            with open(session_path, 'rb') as f:
                encrypted_data = f.read()
                decrypted_json = security.decrypt_data(encrypted_data)
                session_data = json.loads(decrypted_json)
            
            self.session_id = session_id
            self.data = session_data
            
            # Update UI
            self.plan_display.setText(self.data.get("analysis", "No analysis found."))
            self.hint_stack = []
            self.live_display.setText("Session switched. Listening...")
            
            # Restart Audio Thread
            self.start_audio_thread()
            print(f"Switched to session: {session_id}")
            
        except Exception as e:
            print(f"Error switching session: {e}")

    def update_live_feed(self, text):
        # Rule of Three
        self.hint_stack.insert(0, (text, time.time()))
        if len(self.hint_stack) > 3:
            self.hint_stack.pop()
        
        self.render_hints()

    def render_hints(self):
        html = ""
        for text, ts in self.hint_stack:
            color = "#FFFFFF"
            weight = "normal"
            
            if "[TECHNICAL]" in text:
                color = "#00AAFF"
            elif "[BEHAVIORAL]" in text:
                color = "#00FF00"
            elif "[URGENT]" in text:
                color = "#FF5555"
                weight = "bold"
            
            # Temporal Decay: Fade out if older than 30s
            age = time.time() - ts
            opacity = 1.0
            if age > 30:
                opacity = max(0.3, 1.0 - (age - 30) / 15.0)
            
            html += f"<div style='color: {color}; font-weight: {weight}; margin-bottom: 8px; opacity: {opacity};'>➤ {text}</div>"
        
        self.live_display.setText(html)

    def decay_hints(self):
        # Remove hints older than 45 seconds
        now = time.time()
        self.hint_stack = [h for h in self.hint_stack if now - h[1] < 45]
        self.render_hints()

    def update_status(self, text, color):
        self.status_indicator.setText(text)
        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: bold; font-family: 'Consolas';")

    def toggle_mute(self):
        self.audio_thread.is_muted = not self.audio_thread.is_muted
        if self.audio_thread.is_muted:
            self.mute_btn.setText("🔇")
            self.update_status("● MUTED", "#888888")
            self.live_label.setText("LIVE FEED (PAUSED)")
        else:
            self.mute_btn.setText("🎤")
            self.update_status("● LISTENING", "#00FF00")
            self.live_label.setText("LIVE FEED")

    def apply_stealth_mode(self):
        if sys.platform == "win32":
            try:
                hwnd = self.winId().__int__()
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            except Exception as e:
                print(f"Stealth Mode Error: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def closeEvent(self, event):
        self.audio_thread.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    url_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    parsed_url = urllib.parse.urlparse(url_arg)
    params = urllib.parse.parse_qs(parsed_url.query)
    session_id = params.get('session_id', [None])[0]
    
    if not session_id:
        sys.exit(1)
        
    sessions_dir = get_sessions_dir()
    session_path = os.path.join(sessions_dir, f"{session_id}.cc")
    
    try:
        if not os.path.exists(session_path):
            raise FileNotFoundError(f"Session data not found at: {session_path}")
            
        security = SecurityManager()
        with open(session_path, 'rb') as f:
            encrypted_data = f.read()
            decrypted_json = security.decrypt_data(encrypted_data)
            session_data = json.loads(decrypted_json)
            
        overlay = StealthOverlay(session_id, session_data)
        overlay.show()
        
        tray_icon = QSystemTrayIcon(app)
        tray_icon.setIcon(app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon))
        
        tray_menu = QMenu()
        restore_action = QAction("Restore Overlay", tray_menu)
        restore_action.triggered.connect(lambda: (overlay.show(), overlay.raise_(), overlay.activateWindow()))
        tray_menu.addAction(restore_action)
        
        tray_menu.addSeparator()
        
        exit_action = QAction("Exit CareerCaster", tray_menu)
        exit_action.triggered.connect(app.quit)
        tray_menu.addAction(exit_action)
        
        tray_icon.setContextMenu(tray_menu)
        tray_icon.setToolTip("CareerCaster Stealth Agent")
        tray_icon.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
