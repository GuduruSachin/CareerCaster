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

def get_bubble_style(border_color, is_caution=False):
    # Dark modern backgrounds, slight tint for caution
    bg_color = "rgba(45, 25, 5, 0.8)" if is_caution else "rgba(25, 25, 25, 0.75)"
    return f"""
        QFrame {{
            background-color: {bg_color};
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-left: 4px solid {border_color};
            margin-bottom: 6px;
        }}
    """

CONTENT_LABEL_STYLE = """
    QLabel {
        color: #E8E8E8; 
        font-size: 15px; 
        font-family: 'Segoe UI', system-ui, sans-serif; 
        line-height: 1.5; 
        background: transparent; 
        border: none;
    }
"""

STATUS_BAR_STYLE = "background-color: #0A0A0A; border-top: 1px solid #1A1A1A;"
READY_STYLE = "color: #00E676; font-family: 'Consolas', monospace; font-size: 10px;"
THINKING_STYLE = "color: #FFB042; font-family: 'Consolas', monospace; font-size: 10px;"
ERROR_STYLE = "color: #FF5252; font-family: 'Consolas', monospace; font-size: 10px;"
AI_LABEL_STYLE = "color: #00D4FF; font-size: 10px; font-weight: bold; font-family: 'Segoe UI';"
HEADER_TITLE_STYLE = "color: #FFFFFF; font-weight: bold; font-size: 14px; font-family: 'Segoe UI';"
HEADER_SESSION_STYLE = "color: #888888; font-size: 11px; font-family: 'Segoe UI';"
