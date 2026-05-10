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
            background-color: #1A1A1A;
            border-radius: 8px;
            border: 1px solid #2A2A2A;
            border-left: 4px solid {border_color};
            margin-bottom: 5px;
        }}
    """

CONTENT_LABEL_STYLE = """
    QLabel {
        color: #F0F0F0; 
        font-size: 16px; 
        font-family: 'Segoe UI', sans-serif; 
        line-height: 1.6; 
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
