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
    Sessions should be relative to the EXE to persist across runs.
    """
    root = get_exe_dir()
    sessions_dir = os.path.join(root, "sessions")
    
    if not os.path.exists(sessions_dir):
        try:
            os.makedirs(sessions_dir)
        except Exception as e:
            # Fallback to user's AppData if local directory is read-only
            appdata = os.getenv('APPDATA')
            if appdata:
                sessions_dir = os.path.join(appdata, "CareerCaster", "sessions")
                if not os.path.exists(sessions_dir):
                    os.makedirs(sessions_dir)
            else:
                raise e
                
    return sessions_dir

def get_assets_dir():
    """
    Returns the path to the assets directory.
    Assets are bundled inside the EXE, so we use the base path (sys._MEIPASS).
    """
    return os.path.join(get_base_path(), "assets")

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
            print("Secure Cleanup: All session files deleted and clipboard cleared.")
    except Exception as e:
        print(f"Secure Cleanup Error: {e}")
