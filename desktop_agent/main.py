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
import multiprocessing

# --- Path Fix for Monorepo & PyInstaller ---
# Add the correct root to sys.path so 'core' can be found
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    bundle_root = sys._MEIPASS
else:
    bundle_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

import ctypes
from ctypes import wintypes
from google import genai
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QSystemTrayIcon, QMenu, QScrollArea, QSizeGrip, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread, QTimer, QRect
from PyQt6.QtGui import QColor, QIcon, QAction, QFont, QPainter, QPixmap

# Import modularized audio logic
from core.audio_processor import AudioProcessor, log_api_telemetry
from core.security import SecurityManager
from core.paths import get_sessions_dir, get_assets_dir, secure_cleanup

# --- Windows API Constants ---
WDA_EXCLUDEFROMCAPTURE = 0x00000011
WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
HOTKEY_ID = 1

# Win32 Window Styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000

# Global Instance Protection: Prevents Garbage Collector from deleting windows
_PERSISTENT_WINDOWS = []

# NUCLEAR PERSISTENCE: Global scope anchoring
app = None
overlay = None

class AudioCaptureThread(QThread):
    new_chat_message = pyqtSignal(str, str) # role, text
    new_prediction = pyqtSignal(str) # prediction text
    stream_chunk = pyqtSignal(str, str) # role, chunk
    status_update = pyqtSignal(str, str) # status_text, color
    audio_health_signal = pyqtSignal(bool) # True = Healthy, False = Silent

    def __init__(self, session_data):
        super().__init__()
        print("AudioThread: __init__ started", flush=True)
        self.session_data = session_data
        self.api_key = session_data.get("api_key")
        self.preview_mode = session_data.get("preview_mode", False)
        self.active_model = session_data.get("active_model")
        self.persona = "Strategic Leadership"
        self.is_ai_streaming = False
        
        # Fallback if model not provided
        if not self.active_model:
            self.active_model = {"name": "gemini-1.5-flash", "sdk": "New (google-genai)", "version": "v1beta"}
            
        self.is_running = True
        self.is_muted = False
        
        # VAD Parameters
        self.THRESHOLD = 0.015 # Slightly more sensitive
        self.SILENCE_LIMIT_MS = 600 # Trigger after 600ms of silence (faster)
        self.MIN_SPEECH_MS = 150 # Ignore very short noises
        
        # Delay processor init to run() to avoid UI hang
        self.processor = None
        self.stream = None
        
        # Initialize new google-genai client forcing v1beta endpoint
        print("AudioThread: Initializing Gemini Client...", flush=True)
        self.client = genai.Client(
            api_key=self.api_key,
            http_options={'api_version': 'v1beta'}
        )
        print("AudioThread: Gemini Client initialized.", flush=True)
        print("AudioThread: __init__ complete", flush=True)

    def run(self):
        # Initialize processor here to avoid blocking UI thread during startup
        self.processor = AudioProcessor(chunk_size=480)
        
        device_index = self.processor.find_wasapi_loopback_device()
        if device_index is None:
            self.status_update.emit("● NO AUDIO", "#FF5555")
            return

        self.status_update.emit("● LISTENING", "#00FF00")
        
        # Audio Health Tracking
        last_audio_time = time.time()
        health_check_interval = 1.0 # Check every second
        last_health_check = time.time()
        
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
                        raise Exception("Stream inactive")
                except Exception as e:
                    print(f"Audio Stream Error: {e}. Attempting recovery...")
                    self.status_update.emit("● RECONNECTING", "#FFAA00")
                    if self.processor.recover_stream():
                        try:
                            device_index = self.processor.find_wasapi_loopback_device()
                            chunk_size = int(self.processor.rate * (frame_duration_ms / 1000.0))
                            self.stream = self.processor.pa.open(
                                format=self.processor.format,
                                channels=self.processor.channels,
                                rate=self.processor.rate,
                                input=True,
                                input_device_index=device_index,
                                frames_per_buffer=chunk_size
                            )
                            self.status_update.emit("● LISTENING", "#00FF00")
                            continue
                        except:
                            pass
                    time.sleep(2)
                    continue
                
                if not self.is_muted:
                    rms = self.processor.calculate_rms(data)
                    
                    # Update last audio time if volume detected
                    if rms > 0.001: # Small threshold for "real" audio
                        last_audio_time = time.time()
                    
                    # Periodic Health Signal
                    if time.time() - last_health_check >= health_check_interval:
                        # Stay Green if audio detected OR AI is streaming
                        is_healthy = (time.time() - last_audio_time) < 10.0 or self.is_ai_streaming
                        self.audio_health_signal.emit(is_healthy)
                        last_health_check = time.time()

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
                                    
                                    # Get full audio and process in background to avoid blocking VAD loop
                                    full_audio = speech_buffer.getvalue()
                                    threading.Thread(target=self.process_audio_chunk, args=(full_audio,), daemon=True).start()
                                    
                                    # Reset for next question IMMEDIATELY
                                    speech_buffer.close()
                                    speech_buffer = io.BytesIO()
                                    silence_counter_ms = 0
                                    speech_counter_ms = 0
                                    is_recording = False
                                    
                                    # Briefly show thinking, then return to listening state in the loop
                                    self.status_update.emit("● THINKING...", "#FFAA00")
                                    QTimer.singleShot(2000, lambda: self.status_update.emit("● LISTENING", "#00FF00"))
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
            self.is_ai_streaming = True
            prompt = self.processor.get_ai_prompt(self.session_data, persona=self.persona)
            start_time = time.time()
            
            if self.preview_mode:
                # Preview Mode: No API Cost
                print("VAD: Preview Mode ON - Skipping API call")
                self.new_chat_message.emit("interviewer", "[Audio Detected - Preview Mode]")
                self.is_ai_streaming = False
                return

            # Use streaming for near-instant feedback
            response_stream = self.client.models.generate_content_stream(
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
            
            full_response = ""
            current_role = "advisor" # Default to advisor for streaming chunks
            
            # Simple state machine to extract content from JSON stream
            # We'll stream the 'S' field as it's the primary answer/situation
            in_s_field = False
            s_buffer = ""
            
            for chunk in response_stream:
                text_chunk = chunk.text
                full_response += text_chunk
                
                if '"S":' in full_response and not in_s_field:
                    in_s_field = True
                    start_idx = full_response.find('"S":') + 5
                    if len(full_response) > start_idx:
                        new_content = full_response[start_idx:].strip(' "')
                        if new_content:
                            self.stream_chunk.emit("advisor", new_content)
                            s_buffer = new_content
                elif in_s_field:
                    if '"' in text_chunk:
                        end_part = text_chunk.split('"')[0]
                        self.stream_chunk.emit("advisor", end_part)
                        in_s_field = False
                    else:
                        self.stream_chunk.emit("advisor", text_chunk)
            
            # Final parse to ensure accuracy
            try:
                data = json.loads(full_response)
                s = data.get("S", "")
                t = data.get("T", "")
                a = data.get("A", "")
                r = data.get("R", "")
                p = data.get("ProTip", "")
                
                # Reconstruct for the UI if it's a STAR response
                if t or a or r:
                    formatted_answer = f"[S]: {s}\n[T]: {t}\n[A]: {a}\n[R]: {r}"
                else:
                    formatted_answer = s

                if formatted_answer:
                    # Clear the streamed buffer and send the full structured message
                    # The UI will handle segmented display if manual_advancement is on
                    self.new_chat_message.emit("advisor", formatted_answer)
                
                if p:
                    self.new_prediction.emit(p)
                
                latency = time.time() - start_time
                log_api_telemetry(
                    persona=self.persona,
                    char_count=len(prompt),
                    latency=latency,
                    response_s=s,
                    status="SUCCESS"
                )
            except json.JSONDecodeError:
                # Fallback if JSON was malformed but we got some text
                if full_response:
                    self.new_chat_message.emit("advisor", full_response)
                
                latency = time.time() - start_time
                log_api_telemetry(
                    persona=self.persona,
                    char_count=len(prompt),
                    latency=latency,
                    response_s=full_response[:50],
                    status="PARSE_ERROR"
                )
            finally:
                self.is_ai_streaming = False
                    
        except Exception as e:
            self.is_ai_streaming = False
            err_msg = str(e)
            print(f"AI Processing Error: {err_msg}")
            
            latency = time.time() - (start_time if 'start_time' in locals() else time.time())
            log_api_telemetry(
                persona=self.persona,
                char_count=len(prompt) if 'prompt' in locals() else 0,
                latency=latency,
                response_s="N/A",
                status=f"ERROR: {err_msg[:50]}"
            )

    def stop(self):
        self.is_running = False
        self.wait()

import re

def highlight_keywords(text):
    """Bolds technical terms for better readability."""
    keywords = [
        'API', 'Architecture', 'Python', 'Scaling', 'Microservices', 
        'Redis', 'SQL', 'NoSQL', 'Cloud', 'AWS', 'Azure', 'Docker', 
        'Kubernetes', 'Latency', 'VAD', 'STAR', 'Monolith', 'Distributed'
    ]
    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, keywords)) + r')\b', re.IGNORECASE)
    return pattern.sub(r'**\1**', text)

class ChatBubble(QFrame):
    def __init__(self, text, role, manual_advancement=False):
        super().__init__()
        self.role = role
        self.full_text = text
        self.manual_advancement = manual_advancement
        self.segments = []
        self.current_segment_idx = 0
        self.is_final = False
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # Segmented logic for STAR answers
        if manual_advancement and role == "advisor" and "[S]:" in text:
            # Split by STAR markers
            self.segments = re.split(r'(\[S\]:|\[T\]:|\[A\]:|\[R\]:)', text)
            # Reconstruct segments (re.split with capture group keeps delimiters)
            reconstructed = []
            for i in range(1, len(self.segments), 2):
                seg_content = self.segments[i+1].strip()
                if seg_content:
                    reconstructed.append(self.segments[i] + " " + seg_content)
            self.segments = reconstructed
            if self.segments:
                display_text = self.segments[0] + " *(Right Arrow to advance)*"
            else:
                display_text = text
        else:
            display_text = text

        self.label = QLabel(highlight_keywords(display_text))
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.MarkdownText)
        
        if role == "interviewer":
            self.label.setStyleSheet("""
                background-color: rgba(50, 50, 50, 150);
                color: #DDD;
                border-radius: 15px;
                padding: 10px;
                font-size: 10pt;
                border: 1px solid rgba(255, 255, 255, 0.05);
            """)
            self.layout.addWidget(self.label)
            self.layout.addStretch()
        else:
            self.label.setStyleSheet("""
                background-color: rgba(0, 80, 160, 150);
                color: #FFF;
                border-radius: 15px;
                padding: 12px;
                font-size: 10pt;
                font-weight: 500;
                line-height: 1.4;
                border: 1px solid rgba(255, 255, 255, 0.1);
            """)
            self.layout.addStretch()
            self.layout.addWidget(self.label)

    def append_text(self, new_text):
        """Appends text to the bubble in real-time."""
        self.full_text += new_text
        if not self.segments: # Only update label if not in segmented mode
            self.label.setText(highlight_keywords(self.full_text))

    def advance_segment(self):
        """Reveals the next STAR segment."""
        if self.segments and self.current_segment_idx < len(self.segments) - 1:
            self.current_segment_idx += 1
            current_display = " ".join(self.segments[:self.current_segment_idx + 1])
            if self.current_segment_idx < len(self.segments) - 1:
                current_display += " *(Right Arrow to advance)*"
            self.label.setText(highlight_keywords(current_display))
            return True
        return False

class PersonaFlashLabel(QLabel):
    def __init__(self, parent):
        print("PersonaFlash: __init__ started", flush=True)
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            background-color: rgba(0, 255, 255, 180);
            color: #000;
            font-size: 14pt;
            font-weight: bold;
            border-radius: 10px;
            padding: 20px;
        """)
        self.hide()
        
        self.fade_timer = QTimer()
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self.hide)
        print("PersonaFlash: __init__ complete", flush=True)

    def flash(self, text):
        self.setText(text)
        self.adjustSize()
        # Center in parent
        parent_rect = self.parent().rect()
        self.move(
            (parent_rect.width() - self.width()) // 2,
            (parent_rect.height() - self.height()) // 2
        )
        self.show()
        self.raise_()
        self.fade_timer.start(1500)

class StealthOverlay(QWidget):
    def __init__(self, session_id, data):
        super().__init__()
        print("Overlay: __init__ started", flush=True)
        self.session_id = session_id
        self.data = data
        self.old_pos = None
        self.audio_thread = None
        
        print("Overlay: Initializing UI...", flush=True)
        self.init_ui()
        
        # Move Stealth Mode to a timer to ensure window is fully realized
        if not self.data.get("disable_stealth", False):
            print("Overlay: Scheduling Stealth Mode...", flush=True)
            QTimer.singleShot(500, self.apply_stealth_mode)
        else:
            print("Overlay: Stealth Mode disabled by user.", flush=True)
        
        # DELAYED START: Move audio thread and hotkey to timers to ensure event loop is running
        print("Overlay: Scheduling Audio Thread start (2s)...", flush=True)
        QTimer.singleShot(2000, self.start_audio_thread)
        
        print("Overlay: Scheduling Global Hotkey (1s)...", flush=True)
        QTimer.singleShot(1000, self.register_global_hotkey)
        
        # Persona Flash Label
        print("Overlay: Creating Persona Flash Label...", flush=True)
        self.persona_flash = PersonaFlashLabel(self.container)
        print("Overlay: __init__ complete", flush=True)

    def register_global_hotkey(self):
        """Registers the Ctrl+Shift+K global hotkey using Windows API."""
        print("Hotkey: Starting registration...", flush=True)
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                # Define types for safety
                user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
                user32.RegisterHotKey.restype = wintypes.BOOL
                
                print("Hotkey: Getting winId...", flush=True)
                try:
                    hwnd_raw = self.winId()
                    print(f"Hotkey: Raw winId type: {type(hwnd_raw)}", flush=True)
                    hwnd = int(hwnd_raw)
                    print(f"Hotkey: HWND = {hwnd}", flush=True)
                except Exception as e_win:
                    print(f"Hotkey: CRITICAL ERROR getting winId: {e_win}", flush=True)
                    return
                
                # Register Ctrl+Shift+K (K = 0x4B)
                print(f"Hotkey: Calling RegisterHotKey(ID={HOTKEY_ID}, MOD={MOD_CONTROL | MOD_SHIFT}, KEY=0x4B)...", flush=True)
                result = user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, 0x4B)
                print(f"Hotkey: RegisterHotKey result = {result}", flush=True)
                
                if not result:
                    error_code = ctypes.windll.kernel32.GetLastError()
                    print(f"Warning: Failed to register global Kill-Switch hotkey. Error Code: {error_code}", flush=True)
                else:
                    print("Hotkey: Registered successfully.", flush=True)
            except Exception as e:
                print(f"Hotkey Registration Error: {e}", flush=True)
        else:
            print("Hotkey: Not on Windows, skipping.", flush=True)

    def nativeEvent(self, eventType, message):
        """Handles Windows native events, specifically the global hotkey."""
        if sys.platform == "win32" and eventType == "windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                print("!!! GLOBAL KILL-SWITCH ACTIVATED !!!")
                self.kill_process()
                return True, 0
        return super().nativeEvent(eventType, message)

    def apply_stealth_mode(self):
        """Hides the window from screen capture software (Zoom, Teams)."""
        print("Stealth Mode: Attempting to apply...", flush=True)
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                if not hasattr(user32, 'SetWindowDisplayAffinity'):
                    print("Stealth Mode: SetWindowDisplayAffinity not supported on this Windows version.", flush=True)
                    return
                
                # Define types for safety
                user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
                user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
                
                hwnd = int(self.winId())
                print(f"Stealth Mode: HWND = {hwnd}", flush=True)
                
                # WDA_EXCLUDEFROMCAPTURE = 0x11 (17)
                print(f"Stealth Mode: Calling SetWindowDisplayAffinity with {WDA_EXCLUDEFROMCAPTURE}...", flush=True)
                result = user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
                print(f"Stealth Mode: SetWindowDisplayAffinity result = {result}", flush=True)
                
                if not result:
                    error_code = ctypes.windll.kernel32.GetLastError()
                    print(f"Stealth Mode: Failed with error code {error_code}", flush=True)
                else:
                    print("Stealth Mode: Window excluded from screen capture.", flush=True)
            except Exception as e:
                print(f"Stealth Mode Error: {e}", flush=True)
        else:
            print("Stealth Mode: Not on Windows, skipping.", flush=True)

    def init_ui(self):
        print("Overlay: Initializing UI Layout (NUCLEAR PERSISTENCE MODE)...", flush=True)
        # NUCLEAR PERSISTENCE: Standard window with title bar and borders
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        # NUCLEAR PERSISTENCE: Disable all transparency/stealth attributes
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        
        # NUCLEAR PERSISTENCE: Solid Gray Background for visibility
        self.setStyleSheet("background-color: #222222; border: 2px solid #00AAFF;")
        
        # Set Window Icon
        icon_path = os.path.join(get_assets_dir(), "logo.ico")
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
                border-radius: 20px;
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
        self.handle.setStyleSheet("color: #555; font-size: 12pt;")
        self.handle.setCursor(Qt.CursorShape.SizeAllCursor)
        
        self.status_indicator = QLabel("● INITIALIZING")
        self.status_indicator.setStyleSheet("color: #FFAA00; font-size: 8pt; font-weight: bold;")
        
        # Thinking Animation Dots
        self.thinking_dots = QLabel("")
        self.thinking_dots.setStyleSheet("color: #00FFFF; font-size: 12pt; font-weight: bold;")
        self.thinking_timer = QTimer()
        self.thinking_timer.timeout.connect(self.animate_thinking)
        self.dot_count = 0
        
        self.audio_health_indicator = QLabel("●")
        self.audio_health_indicator.setFixedSize(10, 10)
        self.audio_health_indicator.setStyleSheet("color: #00FF00; font-size: 11pt;")
        self.audio_health_indicator.setToolTip("Audio Health (Green = Active, Red = Silent > 10s)")
        
        self.screenshot_btn = QPushButton("📸")
        self.screenshot_btn.setFixedSize(24, 24)
        self.screenshot_btn.setStyleSheet("background: transparent; border: none; font-size: 11pt;")
        self.screenshot_btn.clicked.connect(self.take_screenshot)

        self.mute_btn = QPushButton("🎤")
        self.mute_btn.setFixedSize(24, 24)
        self.mute_btn.setStyleSheet("background: transparent; border: none; font-size: 11pt;")
        self.mute_btn.clicked.connect(self.toggle_mute)
        
        self.close_btn = QPushButton("❌")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("background: transparent; color: #FF4444; border: none; font-weight: bold;")
        self.close_btn.clicked.connect(self.kill_process)
        
        header.addWidget(self.handle)
        header.addSpacing(8)
        header.addWidget(self.status_indicator)
        header.addSpacing(4)
        header.addWidget(self.thinking_dots)
        header.addSpacing(4)
        header.addWidget(self.audio_health_indicator)
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
        
        # Pro-Tip Box (Follow-up Predictor)
        self.pro_tip_container = QFrame()
        self.pro_tip_container.setStyleSheet("""
            background-color: rgba(0, 170, 255, 30);
            border: 1px solid rgba(0, 170, 255, 0.2);
            border-radius: 10px;
            margin-top: 5px;
        """)
        pro_tip_layout = QVBoxLayout(self.pro_tip_container)
        pro_tip_layout.setContentsMargins(8, 8, 8, 8)
        
        pro_tip_header = QLabel("💡 PRO-TIP: LIKELY FOLLOW-UP")
        pro_tip_header.setStyleSheet("color: #00AAFF; font-size: 7pt; font-weight: bold;")
        pro_tip_layout.addWidget(pro_tip_header)
        
        self.pro_tip_text = QLabel("Waiting for first answer...")
        self.pro_tip_text.setWordWrap(True)
        self.pro_tip_text.setStyleSheet("color: #AAA; font-size: 9pt; font-style: italic;")
        pro_tip_layout.addWidget(self.pro_tip_text)
        
        self.pro_tip_container.setVisible(False)
        layout.addWidget(self.pro_tip_container)

        # Battle Plan (Minimized)
        self.plan_btn = QPushButton("Show Battle Plan")
        self.plan_btn.setStyleSheet("color: #00AAFF; font-size: 8pt; border: none; text-align: left;")
        self.plan_btn.clicked.connect(self.toggle_plan)
        layout.addWidget(self.plan_btn)
        
        # Container for the plan to ensure visibility and formatting
        self.plan_container = QFrame()
        self.plan_container.setStyleSheet("background-color: rgba(30, 30, 30, 150); border-radius: 6px;")
        plan_layout = QVBoxLayout(self.plan_container)
        plan_layout.setContentsMargins(5, 5, 5, 5)
        
        plan_title = QLabel("STRATEGIC BATTLE PLAN")
        plan_title.setStyleSheet("color: #00FFFF; font-size: 8pt; font-weight: bold; margin-bottom: 2px;")
        plan_layout.addWidget(plan_title)
        
        analysis_text = self.data.get("analysis", "No analysis available for this session.")
        self.plan_display = QLabel(analysis_text)
        self.plan_display.setWordWrap(True)
        self.plan_display.setTextFormat(Qt.TextFormat.MarkdownText)
        self.plan_display.setStyleSheet("color: #CCC; font-size: 9pt;")
        plan_layout.addWidget(self.plan_display)
        
        self.plan_container.setVisible(False)
        layout.addWidget(self.plan_container)

        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setFixedSize(16, 16)
        
        # Force a reliable default size and position
        self.resize(400, 550)
        screen = QApplication.primaryScreen().geometry()
        if screen.width() == 0 or screen.height() == 0:
            print("Warning: Screen geometry detected as 0x0. Forcing fallback center.", flush=True)
            self.move(100, 100)
        else:
            self.move(screen.width() - 420, 60)
            
        print(f"Overlay: Window Geometry is {self.geometry()}", flush=True)

    def toggle_plan(self):
        is_visible = self.plan_container.isVisible()
        self.plan_container.setVisible(not is_visible)
        self.plan_btn.setText("Hide Battle Plan" if not is_visible else "Show Battle Plan")

    def add_message(self, role, text):
        manual_adv = self.data.get("manual_advancement", False)
        bubble = ChatBubble(text, role, manual_advancement=manual_adv)
        
        # If it's a full structured message from the final parse, mark it
        if role == "advisor" and ("[S]:" in text or len(text) > 50):
            bubble.is_final = True
            
        # Insert before the stretch
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        
        # Auto-scroll
        QTimer.singleShot(100, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def kill_process(self):
        """Gracefully kills the interview process and wipes data."""
        try:
            self.update_status("● SHUTTING DOWN", "#FF5555")
            if self.audio_thread:
                self.audio_thread.stop()
            
            from core.paths import secure_cleanup
            secure_cleanup()
        except Exception as e:
            print(f"Shutdown Error: {e}")
        finally:
            os._exit(0)

    def start_audio_thread(self):
        print("Overlay: start_audio_thread() called.", flush=True)
        if self.audio_thread:
            print("Overlay: Stopping existing audio thread...", flush=True)
            self.audio_thread.stop()
            
        print("Overlay: Initializing AudioCaptureThread...", flush=True)
        self.audio_thread = AudioCaptureThread(self.data)
        self.audio_thread.new_chat_message.connect(self.add_message)
        self.audio_thread.new_prediction.connect(self.update_prediction)
        self.audio_thread.stream_chunk.connect(self.handle_stream_chunk)
        self.audio_thread.status_update.connect(self.update_status)
        self.audio_thread.audio_health_signal.connect(self.update_audio_health)
        
        print("Overlay: Starting AudioCaptureThread...", flush=True)
        self.audio_thread.start()
        print("Overlay: AudioCaptureThread started.", flush=True)

    def update_prediction(self, text):
        self.pro_tip_text.setText(text)
        self.pro_tip_container.setVisible(True)

    def handle_stream_chunk(self, role, chunk):
        # Find the last bubble of the same role if it exists and is the very last widget
        last_widget = self.chat_layout.itemAt(self.chat_layout.count() - 2).widget()
        if isinstance(last_widget, ChatBubble) and last_widget.role == role:
            # Only append if it's not a final structured message
            if not last_widget.is_final:
                last_widget.append_text(chunk)
        else:
            self.add_message(role, chunk)

    def update_audio_health(self, is_healthy):
        color = "#00FF00" if is_healthy else "#FF0000"
        self.audio_health_indicator.setStyleSheet(f"color: {color}; font-size: 11pt;")

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
        self.status_indicator.setStyleSheet(f"color: {color}; font-size: 8pt; font-weight: bold; font-family: 'Consolas';")
        
        if "THINKING" in text:
            self.thinking_timer.start(400)
        else:
            self.thinking_timer.stop()
            self.thinking_dots.setText("")

    def animate_thinking(self):
        self.dot_count = (self.dot_count + 1) % 4
        self.thinking_dots.setText("." * self.dot_count)

    def toggle_mute(self):
        self.audio_thread.is_muted = not self.audio_thread.is_muted
        if self.audio_thread.is_muted:
            self.mute_btn.setText("🔇")
            self.update_status("● MUTED", "#888888")
        else:
            self.mute_btn.setText("🎤")
            self.update_status("● LISTENING", "#00FF00")

    def toggle_persona(self):
        if self.audio_thread.persona == "Strategic Leadership":
            self.audio_thread.persona = "Deep Systems Implementation"
        else:
            self.audio_thread.persona = "Strategic Leadership"
        
        mode_text = f"MODE: {self.audio_thread.persona.upper()}"
        self.update_status(f"● PERSONA: {self.audio_thread.persona.upper()}", "#00FFFF")
        self.persona_flash.flash(mode_text)
        QTimer.singleShot(2000, lambda: self.update_status("● LISTENING", "#00FF00"))

    def keyPressEvent(self, event):
        # Input Isolation: Only respond if window is active
        if not self.isActiveWindow():
            return

        # Manual Advancement: Right Arrow only
        if event.key() == Qt.Key.Key_Right:
            # Find the last advisor bubble and try to advance it
            for i in range(self.chat_layout.count() - 1, -1, -1):
                item = self.chat_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), ChatBubble):
                    bubble = item.widget()
                    if bubble.role == "advisor" and bubble.advance_segment():
                        event.accept()
                        return
        
        # Persona Toggle: Ctrl+T
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_T:
            self.toggle_persona()
            event.accept()
            return

        super().keyPressEvent(event)

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
    global app, overlay
    # Critical for PyInstaller + Multiprocessing on Windows
    if sys.platform == "win32":
        multiprocessing.freeze_support()

    print(f"Startup: CareerCaster Agent starting. Args: {sys.argv}")
    try:

        # High-DPI Scaling Optimization
        if hasattr(Qt, 'HighDpiScaleFactorRoundingPolicy'):
            QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

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
        assets_dir = get_assets_dir()
        icon_path = os.path.join(assets_dir, "logo.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        # Handshake: Capture session_id or absolute path from arguments
        raw_arg = sys.argv[1] if len(sys.argv) > 1 else None
        session_id = None
        session_path = None
        
        if raw_arg:
            # Clean quotes added by shell/shlex
            raw_arg = raw_arg.strip("'\"")
            
            # Check if it's an absolute path to a .cc file
            is_path = raw_arg.lower().endswith(".cc") and (os.path.isabs(raw_arg) or (len(raw_arg) > 2 and raw_arg[1] == ":"))
            
            if is_path:
                # Absolute path passed directly
                session_path = os.path.abspath(raw_arg)
                session_id = os.path.basename(session_path).replace(".cc", "")
                print(f"Startup: Detected absolute session path: {session_path}", flush=True)
            elif "careercaster://" in raw_arg:
                # Parse URI: careercaster://start?session_id=UUID
                try:
                    parsed = urllib.parse.urlparse(raw_arg)
                    params = urllib.parse.parse_qs(parsed.query)
                    session_id = params.get("session_id", [None])[0]
                except Exception as e:
                    print(f"URI Parse Error: {e}")
            else:
                # Direct UUID
                session_id = raw_arg
        
        if not session_id and not session_path:
            print("Error: No session ID or path detected.")
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("CareerCaster Launch Error")
            msg.setInformativeText("No session ID detected. Please launch the agent from the Web Hub.")
            msg.setWindowTitle("Error")
            msg.exec()
            sys.exit(1)
            
        if not session_path:
            sessions_dir = get_sessions_dir()
            session_path = os.path.join(sessions_dir, f"{session_id}.cc")
            
        print(f"Startup: Looking for session at {session_path}")
    
        try:
            print(f"Startup: Initializing StealthOverlay for session {session_id}", flush=True)
            if not os.path.exists(session_path):
                error_msg = f"Session data not found.\n\nExpected at: {session_path}"
                raise FileNotFoundError(error_msg)
                
            print("Startup: Initializing SecurityManager...", flush=True)
            security = SecurityManager()
            print("Startup: SecurityManager initialized.", flush=True)
            
            with open(session_path, 'rb') as f:
                encrypted_data = f.read()
                print(f"Startup: Read {len(encrypted_data)} bytes of encrypted data.", flush=True)
                decrypted_json = security.decrypt_data(encrypted_data)
                print("Startup: Data decrypted successfully.", flush=True)
                session_data = json.loads(decrypted_json)
                print("Startup: Session data loaded.", flush=True)
                
            print("Startup: Creating StealthOverlay instance...", flush=True)
            overlay = StealthOverlay(session_id, session_data)
            _PERSISTENT_WINDOWS.append(overlay)
            
            # DIAGNOSTIC: Comment out manual Win32 style calls
            """
            if sys.platform == "win32":
                try:
                    hwnd = int(overlay.winId())
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
                    print("Startup: WS_EX_LAYERED style applied.", flush=True)
                except Exception as e:
                    print(f"Startup: Win32 Style Error: {e}", flush=True)
            """

            print("Startup: StealthOverlay instance created successfully.", flush=True)
            
            print("Startup: Calling overlay.show()...", flush=True)
            try:
                overlay.showNormal()
                overlay.show()
                print("Startup: overlay.show() returned.", flush=True)
                
                overlay.setWindowOpacity(0.95)
                print("Startup: Opacity set to 0.95", flush=True)
                
                overlay.raise_()
                print("Startup: overlay.raise_() called.", flush=True)
                
                overlay.activateWindow()
                print("Startup: overlay.activateWindow() called.", flush=True)
                
                overlay.repaint()
                print("Startup: overlay.repaint() called.", flush=True)
            except Exception as e_show:
                print(f"Startup: CRITICAL ERROR during overlay.show(): {e_show}", flush=True)
                raise e_show
            
            print(f"Startup: Final Geometry: {overlay.geometry()}", flush=True)
            print("Startup: Overlay visible.", flush=True)
            
            # NUCLEAR PERSISTENCE: Force native event processing
            print("Startup: Forcing native event processing...", flush=True)
            app.processEvents()
            print("AGENT_ALIVE_MARKER", flush=True)

            # Keep console open for debugging
            print("\n" + "="*50, flush=True)
            print("AGENT IS RUNNING IN STEALTH MODE", flush=True)
            print("Minimize this window, but do NOT close it.", flush=True)
            print("="*50 + "\n", flush=True)

            try:
                tray_icon = QSystemTrayIcon(app)
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
                print("Startup: Tray Icon initialized and shown.", flush=True)
            except Exception as e_tray:
                print(f"Startup: Warning - Tray Icon failed to initialize: {e_tray}", flush=True)
            
            print("Startup: Entering Event Loop...", flush=True)
            try:
                exit_code = app.exec()
                print(f"Startup: Event Loop Exited with code {exit_code}", flush=True)
                sys.exit(exit_code)
            except Exception as e:
                import traceback
                print("\n" + "!"*50, flush=True)
                print("CRITICAL: Event Loop Failed to Start!", flush=True)
                traceback.print_exc()
                print("!"*50 + "\n", flush=True)
                raise e
        except Exception as e:
            # Re-raise to be caught by the outer try-except
            raise e
    except Exception as e:
        # Global Error Resilience: Log to crash.log and startup_error.log
        import traceback
        log_path = os.path.join(os.getcwd(), "crash.log")
        startup_log_path = os.path.join(os.getcwd(), "startup_error.log")
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        error_details = f"\n[{timestamp}] CRASH DETECTED:\n{traceback.format_exc()}\n{'-' * 50}\n"
        
        try:
            with open(log_path, "a") as f:
                f.write(error_details)
            with open(startup_log_path, "a") as f:
                f.write(error_details)
        except:
            pass
        
        print(f"Critical Error: {e}")
        try:
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("CareerCaster Startup Error")
            msg.setInformativeText(str(e))
            msg.setWindowTitle("Error")
            msg.exec()
        except:
            pass
        raise e

if __name__ == "__main__":
    try:
        main()
    except (Exception, SystemExit):
        import traceback
        print("\n" + "="*50)
        print("CRASH DETECTED IN STARTUP SEQUENCE")
        print("="*50)
        traceback.print_exc()
        print("="*50)

# FINAL DIAGNOSTIC: Prevent CMD window from closing under any circumstances
print("\n" + "!"*50, flush=True)
print("DIAGNOSTIC: Script reached end of file.", flush=True)
print("If you see this, the process terminated unexpectedly.", flush=True)
print("!"*50 + "\n", flush=True)
try:
    input("DEBUG: Process reached end of file. Press Enter to close...")
except EOFError:
    pass
