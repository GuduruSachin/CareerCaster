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

import google.generativeai as genai
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QSystemTrayIcon, QMenu, QScrollArea)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QColor, QIcon, QAction

# Import modularized audio logic
from core.audio_processor import AudioProcessor
from core.security import SecurityManager
from core.paths import get_sessions_dir

# --- Windows API Constants ---
WDA_EXCLUDEFROMCAPTURE = 0x00000011

class AudioCaptureThread(QThread):
    new_hint = pyqtSignal(str)
    status_update = pyqtSignal(str, str) # status_text, color

    def __init__(self, api_key, context_tags):
        super().__init__()
        self.api_key = api_key
        self.context_tags = context_tags
        self.is_running = True
        self.is_muted = False
        self.processor = AudioProcessor()
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')

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
            
            response = self.model.generate_content([
                prompt,
                {'mime_type': 'audio/wav', 'data': base64_audio}
            ])
            
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
        
        self.container = QFrame(self)
        self.container.setStyleSheet("""
            QFrame {
                background-color: rgba(20, 20, 20, 225);
                border: 1px solid #444;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 10, 12, 12)
        
        # Header
        header_layout = QHBoxLayout()
        self.handle = QLabel("⠿") 
        self.handle.setStyleSheet("color: #666; font-size: 18px;")
        self.handle.setCursor(Qt.CursorShape.SizeAllCursor)
        
        self.status_indicator = QLabel("● INITIALIZING")
        self.status_indicator.setStyleSheet("color: #FFAA00; font-size: 9px; font-weight: bold; font-family: 'Consolas';")
        
        # Session Switcher Button
        self.session_btn = QPushButton("📂")
        self.session_btn.setFixedSize(24, 24)
        self.session_btn.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        self.session_btn.setToolTip("Switch Session")
        self.session_btn.clicked.connect(self.show_session_menu)

        # Mute Toggle
        self.mute_btn = QPushButton("🎤")
        self.mute_btn.setFixedSize(24, 24)
        self.mute_btn.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        self.mute_btn.clicked.connect(self.toggle_mute)
        
        # Minimize Button
        self.min_btn = QPushButton("—")
        self.min_btn.setFixedSize(24, 24)
        self.min_btn.setStyleSheet("background: transparent; color: #888; font-size: 16px; border: none;")
        self.min_btn.clicked.connect(self.hide)

        self.close_btn = QPushButton("×")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("background: transparent; color: #888; font-size: 18px; border: none;")
        self.close_btn.clicked.connect(self.close)
        
        header_layout.addWidget(self.handle)
        header_layout.addStretch()
        header_layout.addWidget(self.session_btn)
        header_layout.addWidget(self.mute_btn)
        header_layout.addWidget(self.status_indicator)
        header_layout.addWidget(self.min_btn)
        header_layout.addWidget(self.close_btn)
        layout.addLayout(header_layout)
        
        # AI Battle Plan (Static)
        self.plan_label = QLabel("AI BATTLE PLAN")
        self.plan_label.setStyleSheet("color: #00AAFF; font-size: 9px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(self.plan_label)
        
        self.plan_display = QLabel(self.data.get("analysis", "No analysis found."))
        self.plan_display.setWordWrap(True)
        self.plan_display.setStyleSheet("color: #BBB; font-size: 11px; padding-bottom: 5px;")
        
        plan_scroll = QScrollArea()
        plan_scroll.setWidgetResizable(True)
        plan_scroll.setWidget(self.plan_display)
        plan_scroll.setFixedHeight(60)
        plan_scroll.setStyleSheet("background: transparent; border: none;")
        plan_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(plan_scroll)
        
        layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine, styleSheet="background-color: #333;"))
        
        # Live Feed (Dynamic)
        self.live_label = QLabel("LIVE FEED")
        self.live_label.setStyleSheet("color: #FF4444; font-size: 9px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(self.live_label)
        
        self.live_display = QLabel("Listening for interview questions...")
        self.live_display.setWordWrap(True)
        self.live_display.setTextFormat(Qt.TextFormat.RichText)
        self.live_display.setStyleSheet("color: #FFF; font-size: 12px; font-weight: 500;")
        
        live_scroll = QScrollArea()
        live_scroll.setWidgetResizable(True)
        live_scroll.setWidget(self.live_display)
        live_scroll.setFixedHeight(140)
        live_scroll.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(live_scroll)
        
        self.setFixedSize(340, 360)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 360, 50)

    def start_audio_thread(self):
        if self.audio_thread:
            self.audio_thread.stop()
            
        self.audio_thread = AudioCaptureThread(
            self.data.get("api_key"),
            self.data.get("context_tags", {})
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
