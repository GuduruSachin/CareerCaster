import sys
import winreg
import os

def register_protocol():
    protocol_name = "careercaster"
    # Get the path to the current python executable and the main.py script
    python_exe = sys.executable
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
    
    # Command to run: python.exe main.py "%1"
    command = f'"{python_exe}" "{script_path}" "%1"'

    try:
        # Create the protocol key
        key_path = rf"Software\Classes\{protocol_name}"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f"URL:{protocol_name} Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        # Create the shell open command key
        command_key_path = rf"{key_path}\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, command_key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, command)

        print(f"Successfully registered {protocol_name}:// protocol.")
        print(f"Command: {command}")
    except Exception as e:
        print(f"Failed to register protocol: {e}")

if __name__ == "__main__":
    register_protocol()
