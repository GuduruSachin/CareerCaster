import sys
import urllib.parse
import json
import os
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class StealthOverlay(QWidget):
    def __init__(self, session_id):
        super().__init__()
        self.session_id = session_id
        self.init_ui()
        self.load_session_data()

    def init_ui(self):
        # Stealth settings: Frameless, Always on Top, Translucent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout()
        self.label = QLabel(f"CareerCaster Active\nSession: {self.session_id}\nWaiting for hints...")
        self.label.setStyleSheet("color: #00FF00; font-size: 14px; font-weight: bold; background-color: rgba(0, 0, 0, 150); padding: 10px; border-radius: 5px;")
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        # Position at the bottom right
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 300, screen.height() - 200)
        self.show()

    def load_session_data(self):
        # In a real app, this would pull from a shared local folder or a local API
        # For this demo, we just acknowledge the session_id
        session_path = os.path.join(os.path.expanduser("~"), ".careercaster", f"session_{self.session_id}.json")
        if os.path.exists(session_path):
            with open(session_path, 'r') as f:
                data = json.load(f)
                self.label.setText(f"CareerCaster: {data.get('candidate_name', 'User')}\nInterviewing for: {data.get('job_title', 'Role')}\n\nHint: Be prepared to discuss your React experience.")

def main():
    app = QApplication(sys.argv)
    
    # Parse the deep link URL: careercaster://start?id=123
    url_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    parsed_url = urllib.parse.urlparse(url_arg)
    params = urllib.parse.parse_qs(parsed_url.query)
    
    session_id = params.get('id', ['unknown'])[0]
    
    overlay = StealthOverlay(session_id)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
