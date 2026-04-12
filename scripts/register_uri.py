import winreg
import sys
import os

def register_uri_protocol():
    """
    Registers the 'careercaster://' URI protocol in the Windows Registry.
    This allows the Web Hub to launch the Desktop Agent.
    """
    # Path to the Python executable and the main.py script
    python_exe = sys.executable
    agent_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "desktop_agent", "main.py"))
    
    if not os.path.exists(agent_script):
        print(f"Error: Could not find agent script at {agent_script}")
        return

    protocol_name = "careercaster"
    # Command to run: python.exe main.py "%1"
    launch_command = f'"{python_exe}" "{agent_script}" "%1"'

    try:
        # Create the registry keys
        key_path = rf"Software\Classes\{protocol_name}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "URL:CareerCaster Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{key_path}\shell\open\command") as key:
            winreg.SetValue(key, "", winreg.REG_SZ, launch_command)
            
        print(f"Successfully registered '{protocol_name}://' protocol.")
        print(f"Command: {launch_command}")
    except Exception as e:
        print(f"Failed to register protocol: {e}")
        print("Try running this script as Administrator.")

if __name__ == "__main__":
    register_uri_protocol()
