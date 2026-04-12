#!/usr/bin/env pythonw
# Note: Save this file as .pyw or run with pythonw.exe to hide the CMD window on Windows.

import sys
import os
import json
import urllib.parse
import ctypes
import threading
import time
import io

# --- Path Fix for Monorepo & PyInstaller ---
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        return os.path.join(sys._MEIPASS, relative_path)
    
    # In development, resources are relative to the project root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, ".."))
    return os.path.join(project_root, relative_path)

# Add the correct root to sys.path so 'core' can be found
if hasattr(sys, '_MEIPASS'):
    bundle_root = sys._MEIPASS
else:
    bundle_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

from google import genai
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QSystemTrayIcon, QMenu, QScrollArea, QSizeGrip, QSizePolicy)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread, QTimer, QRect
from PyQt6.QtGui import QColor, QIcon, QAction, QFont, QPainter, QPixmap

# Import modularized audio logic
from core.audio_processor import AudioProcessor
from core.security import SecurityManager
from core.paths import get_sessions_dir
from core.logger import log_api_transaction

# --- Windows API Constants ---
WDA_EXCLUDEFROMCAPTURE = 0x00000011

class AudioCaptureThread(QThread):
    new_chat_message = pyqtSignal(str, str) # role, text
    status_update = pyqtSignal(str, str) # status_text, color

    def __init__(self, api_key, context_tags, active_model=None, preview_mode=False):
        super().__init__()
        self.api_key = api_key
        self.context_tags = context_tags
        self.preview_mode = preview_mode
        # Use gemini-3.1-flash-lite-preview as requested for instant results
        self.active_model = {"name": "gemini-3.1-flash-lite-preview", "sdk": "New (google-genai)", "version": "v1beta"}
        self.is_running = True
        self.is_muted = False
        
        # VAD Parameters
        self.THRESHOLD = 0.02 # RMS Sensitivity (tweakable)
        self.SILENCE_LIMIT_MS = 800 # Trigger after 800ms of silence
        self.MIN_SPEECH_MS = 200 # Ignore very short noises
        
        # 30ms frames for VAD precision
        self.processor = AudioProcessor(chunk_size=480) 
        self.stream = None
        
        # Initialize new google-genai client forcing v1beta endpoint
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
            # Re-calculate chunk size for 30ms based on detected rate
            frame_duration_ms = 30
            chunk_size = int(self.processor.rate * (frame_duration_ms / 1000.0))
            
            self.stream = p.open(
                format=self.processor.format,
                channels=self.processor.channels,
                rate=self.processor.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk_size
            )
        except Exception as e:
            print(f"Stream Open Error: {e}")
            self.status_update.emit("● AUDIO ERROR", "#FF5555")
            return

        speech_buffer = io.BytesIO()
        silence_counter_ms = 0
        speech_counter_ms = 0
        is_recording = False

        try:
            while self.is_running:
                try:
                    if self.stream and self.stream.is_active():
                        data = self.stream.read(chunk_size, exception_on_overflow=False)
                    else:
                        break
                except Exception:
                    continue
                
                if not self.is_muted:
                    rms = self.processor.calculate_rms(data)
                    
                    if rms > self.THRESHOLD:
                        # Speech detected
                        if not is_recording:
                            is_recording = True
                            print("VAD: Speech Started")
                        
                        speech_buffer.write(data)
                        speech_counter_ms += frame_duration_ms
                        silence_counter_ms = 0 # Reset silence
                    else:
                        # Silence detected
                        if is_recording:
                            speech_buffer.write(data) # Keep some silence for context
                            silence_counter_ms += frame_duration_ms
                            
                            # Trigger processing if silence exceeds limit
                            if silence_counter_ms >= self.SILENCE_LIMIT_MS:
                                if speech_counter_ms >= self.MIN_SPEECH_MS:
                                    print(f"VAD: Triggering AI after {speech_counter_ms}ms speech")
                                    self.status_update.emit("● THINKING...", "#FFAA00")
                                    
                                    # Get full audio and process
                                    full_audio = speech_buffer.getvalue()
                                    self.process_audio_chunk(full_audio)
                                    
                                    self.status_update.emit("● LISTENING", "#00FF00")
                                
                                # Reset for next question
                                speech_buffer.close()
                                speech_buffer = io.BytesIO()
                                silence_counter_ms = 0
                                speech_counter_ms = 0
                                is_recording = False
                        else:
                            # Still idle
                            pass
                else:
                    # Muted: Clear everything
                    if is_recording:
                        speech_buffer.close()
                        speech_buffer = io.BytesIO()
                        silence_counter_ms = 0
                        speech_counter_ms = 0
                        is_recording = False
                    time.sleep(0.1)
        finally:
            if speech_buffer:
                speech_buffer.close()
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
            self.processor.close()

    def process_audio_chunk(self, raw_pcm):
        try:
            prompt = self.processor.get_ai_prompt(self.context_tags)
            
            if self.preview_mode:
                # Preview Mode: No API Cost
                print("VAD: Preview Mode ON - Skipping API call")
                self.new_chat_message.emit("interviewer", "[Audio Detected - Preview Mode]")
                log_api_transaction(
                    model_used=self.active_model["name"],
                    prompt_length=len(prompt),
                    response_text="[PREVIEW_ONLY]",
                    status="PREVIEW_ONLY"
                )
                return

            response = self.client.models.generate_content(
                model=self.active_model["name"],
                contents=[
                    prompt,
                    genai.types.Part.from_bytes(
                        data=self.processor.pcm_to_wav_bytes(raw_pcm),
                        mime_type='audio/wav'
                    )
                ],
                config=genai.types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json"
                )
            )
            
            res_text = response.text.strip()
            if res_text:
                try:
                    data = json.loads(res_text)
                    q = data.get("question")
                    a = data.get("answer")
                    if q:
                        self.new_chat_message.emit("interviewer", q)
                    if a:
                        self.new_chat_message.emit("advisor", a)
                    
                    log_api_transaction(
                        model_used=self.active_model["name"],
                        prompt_length=len(prompt),
                        response_text=res_text,
                        status="SUCCESS"
                    )
                except json.JSONDecodeError:
                    log_api_transaction(
                        model_used=self.active_model["name"],
                        prompt_length=len(prompt),
                        response_text=res_text,
                        status="PARSE_ERROR"
                    )
                    
        except Exception as e:
            err_msg = str(e)
            print(f"AI Processing Error: {err_msg}")
            log_api_transaction(
                model_used=self.active_model["name"],
                prompt_length=len(prompt) if 'prompt' in locals() else 0,
                response_text="",
                status="ERROR",
                error_details=err_msg
            )

    def stop(self):
        self.is_running = False
        self.wait()

class ChatBubble(QFrame):
    def __init__(self, text, role):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.MarkdownText)
        
        if role == "interviewer":
            self.label.setStyleSheet("""
                background-color: #333;
                color: #DDD;
                border-radius: 10px;
                padding: 8px;
                font-size: 12px;
            """)
            self.layout.addWidget(self.label)
            self.layout.addStretch()
        else:
            self.label.setStyleSheet("""
                background-color: #004488;
                color: #FFF;
                border-radius: 10px;
                padding: 8px;
                font-size: 13px;
                font-weight: 500;
            """)
            self.layout.addStretch()
            self.layout.addWidget(self.label)

class StealthOverlay(QWidget):
    def __init__(self, session_id, data):
        super().__init__()
        self.session_id = session_id
        self.data = data
        self.old_pos = None
        self.audio_thread = None
        
        self.init_ui()
        self.apply_stealth_mode()
        self.start_audio_thread()

    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Set Window Icon
        icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.container = QFrame(self)
        self.container.setObjectName("MainContainer")
        
        # Cyan visual cue for Preview Mode
        border_color = "#00FFFF" if self.data.get("preview_mode") else "#333"
        
        self.container.setStyleSheet(f"""
            #MainContainer {{
                background-color: rgba(15, 15, 15, 230);
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
        """)
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(10, 8, 10, 10)
        
        # Header
        header = QHBoxLayout()
        self.handle = QLabel("⠿") 
        self.handle.setStyleSheet("color: #555; font-size: 16px;")
        self.handle.setCursor(Qt.CursorShape.SizeAllCursor)
        
        self.status_indicator = QLabel("● INITIALIZING")
        self.status_indicator.setStyleSheet("color: #FFAA00; font-size: 9px; font-weight: bold;")
        
        self.screenshot_btn = QPushButton("📸")
        self.screenshot_btn.setFixedSize(24, 24)
        self.screenshot_btn.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        self.screenshot_btn.clicked.connect(self.take_screenshot)

        self.mute_btn = QPushButton("🎤")
        self.mute_btn.setFixedSize(24, 24)
        self.mute_btn.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        self.mute_btn.clicked.connect(self.toggle_mute)
        
        self.close_btn = QPushButton("❌")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("background: transparent; color: #FF4444; border: none; font-weight: bold;")
        self.close_btn.clicked.connect(self.kill_process)
        
        header.addWidget(self.handle)
        header.addSpacing(8)
        header.addWidget(self.status_indicator)
        header.addStretch()
        header.addWidget(self.screenshot_btn)
        header.addWidget(self.mute_btn)
        header.addWidget(self.close_btn)
        layout.addLayout(header)
        
        # Chat Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.addStretch()
        
        self.scroll.setWidget(self.chat_container)
        layout.addWidget(self.scroll)
        
        # Battle Plan (Minimized)
        self.plan_btn = QPushButton("Show Battle Plan")
        self.plan_btn.setStyleSheet("color: #00AAFF; font-size: 10px; border: none; text-align: left;")
        self.plan_btn.clicked.connect(self.toggle_plan)
        layout.addWidget(self.plan_btn)
        
        self.plan_display = QLabel(self.data.get("analysis", ""))
        self.plan_display.setWordWrap(True)
        self.plan_display.setStyleSheet("color: #888; font-size: 11px; padding: 5px;")
        self.plan_display.setVisible(False)
        layout.addWidget(self.plan_display)

        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setFixedSize(16, 16)
        
        self.resize(340, 450)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 360, 60)

    def toggle_plan(self):
        is_visible = self.plan_display.isVisible()
        self.plan_display.setVisible(not is_visible)
        self.plan_btn.setText("Hide Battle Plan" if not is_visible else "Show Battle Plan")

    def add_message(self, role, text):
        bubble = ChatBubble(text, role)
        # Insert before the stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        
        # Auto-scroll
        QTimer.singleShot(100, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def kill_process(self):
        """Gracefully kills the interview process."""
        try:
            self.update_status("● SHUTTING DOWN", "#FF5555")
            if self.audio_thread:
                self.audio_thread.stop()
            
            sessions_dir = get_sessions_dir()
            session_path = os.path.join(sessions_dir, f"{self.session_id}.cc")
            if os.path.exists(session_path):
                os.remove(session_path)
        except Exception as e:
            print(f"Shutdown Error: {e}")
        finally:
            sys.exit(0)

    def start_audio_thread(self):
        if self.audio_thread:
            self.audio_thread.stop()
            
        self.audio_thread = AudioCaptureThread(
            self.data.get("api_key"),
            self.data.get("context_tags", {}),
            self.data.get("active_model"),
            self.data.get("preview_mode", False)
        )
        self.audio_thread.new_chat_message.connect(self.add_message)
        self.audio_thread.status_update.connect(self.update_status)
        self.audio_thread.start()

    def take_screenshot(self):
        """Captures only the overlay window and saves it to /screenshots."""
        try:
            screenshots_dir = os.path.join(bundle_root, "screenshots")
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

    def update_status(self, text, color):
        self.status_indicator.setText(text)
        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 9px; font-weight: bold; font-family: 'Consolas';")

    def toggle_mute(self):
        self.audio_thread.is_muted = not self.audio_thread.is_muted
        if self.audio_thread.is_muted:
            self.mute_btn.setText("🔇")
            self.update_status("● MUTED", "#888888")
        else:
            self.mute_btn.setText("🎤")
            self.update_status("● LISTENING", "#00FF00")

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
    # Windows Taskbar Branding
    if sys.platform == "win32":
        try:
            myappid = 'careercaster.stealth.agent.v1'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"Branding Error: {e}")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    # Set Application Icon
    icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
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
        icon_path = get_resource_path(os.path.join("assets", "logo.ico"))
        if os.path.exists(icon_path):
            tray_icon.setIcon(QIcon(icon_path))
        else:
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
