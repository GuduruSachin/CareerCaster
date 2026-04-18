# CareerCaster v1.1 - UI Styles Library
# Contains all QSS string constants to keep logic files clean.

MAIN_WINDOW_STYLE = """
    QMainWindow { 
        background-color: #121212; 
    }
    #header { 
        background-color: #1A1A1A; 
        border-bottom: 1px solid #333333; 
    }
    QScrollArea { 
        background-color: transparent; 
        border: none; 
    }
    QWidget#chat_container { 
        background-color: transparent; 
    }
    QScrollBar:vertical { 
        border: none; 
        background: transparent; 
        width: 6px; 
        margin: 0px; 
    }
    QScrollBar::handle:vertical { 
        background: #444444; 
        min-height: 20px; 
        border-radius: 3px; 
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { 
        border: none; 
        background: none; 
    }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { 
        background: none; 
    }
    QLineEdit { 
        background-color: #1A1A1A; 
        border: 1px solid #333333; 
        color: #FFFFFF; 
        padding: 8px; 
        border-radius: 4px; 
        font-family: 'Segoe UI';
        font-size: 12px;
    }
"""

def get_bubble_style(border_color):
    return f"""
        QFrame {{
            background-color: #1E1E1E;
            border-radius: 12px;
            border-left: 3px solid {border_color};
        }}
    """

CONTENT_LABEL_STYLE = """
    QLabel {
        color: #E0E0E0; 
        font-size: 13px; 
        font-family: 'Segoe UI'; 
        line-height: 150%; 
        background: transparent; 
        border: none;
    }
"""

STATUS_BAR_STYLE = "background-color: #0A0A0A; border-top: 1px solid #1A1A1A;"
READY_STYLE = "color: #00FF00; font-family: 'Consolas', monospace; font-size: 10px;"
THINKING_STYLE = "color: #FFAA00; font-family: 'Consolas', monospace; font-size: 10px;"
ERROR_STYLE = "color: #FF0000; font-family: 'Consolas', monospace; font-size: 10px;"
AI_LABEL_STYLE = "color: #00FFFF; font-size: 10px; font-weight: bold; font-family: 'Segoe UI';"
HEADER_TITLE_STYLE = "color: #FFFFFF; font-weight: bold; font-size: 14px; font-family: 'Segoe UI';"
HEADER_SESSION_STYLE = "color: #666666; font-size: 11px; font-family: 'Segoe UI';"
