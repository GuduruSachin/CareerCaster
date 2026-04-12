import os
import sys

def get_project_root():
    """
    Returns the root directory of the project.
    Handles both 'frozen' (PyInstaller EXE) and 'unfrozen' (Python script) states.
    """
    if getattr(sys, 'frozen', False):
        # Running as a bundled EXE
        # sys.executable is the path to the EXE
        return os.path.dirname(sys.executable)
    else:
        # Running as a script
        # This file is in core/, so the root is one level up
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_sessions_dir():
    """
    Returns the path to the sessions directory.
    Creates it if it doesn't exist.
    """
    root = get_project_root()
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
