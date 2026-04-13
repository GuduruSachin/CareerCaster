import os
import sys

def get_base_path():
    """
    Returns the base path for resources.
    Uses sys._MEIPASS when frozen (PyInstaller) to access bundled assets.
    Falls back to the project root in development.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    
    # In development, this file is in core/, so the root is one level up
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_exe_dir():
    """
    Returns the directory where the EXE (or script) is located.
    This is used for persistent data like sessions.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return get_base_path()

def get_sessions_dir():
    """
    Returns the path to the sessions directory.
    Ensures that both Web Hub and Agent use the same physical directory.
    """
    if getattr(sys, 'frozen', False):
        # Running as EXE
        base = os.path.dirname(sys.executable)
    else:
        # Running as Script - Use the project root (one level up from core/)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    sessions_dir = os.path.join(base, "sessions")
    
    if not os.path.exists(sessions_dir):
        os.makedirs(sessions_dir, exist_ok=True)
                
    return sessions_dir

def get_assets_dir():
    """
    Returns the path to the assets directory.
    Assets are bundled inside the EXE, so we use the base path (sys._MEIPASS).
    """
    return os.path.join(get_base_path(), "assets")

def get_logs_dir():
    """
    Returns the path to the logs directory.
    """
    root = get_exe_dir()
    logs_dir = os.path.join(root, "logs")
    if not os.path.exists(logs_dir):
        try:
            os.makedirs(logs_dir)
        except:
            pass
    return logs_dir

def secure_cleanup():
    """
    Deletes all files in the sessions directory and clears clipboard for security.
    """
    try:
        # Clear Clipboard
        if sys.platform == 'win32':
            os.system('cmd /c "echo off | clip"')
        
        sessions_dir = get_sessions_dir()
        if os.path.exists(sessions_dir):
            for filename in os.listdir(sessions_dir):
                file_path = os.path.join(sessions_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")
            
        # Delete Log Files
        logs_dir = get_logs_dir()
        if os.path.exists(logs_dir):
            for filename in os.listdir(logs_dir):
                file_path = os.path.join(logs_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except:
                    pass
                    
        print("Secure Cleanup: All session files, logs deleted and clipboard cleared.")
    except Exception as e:
        print(f"Secure Cleanup Error: {e}")
