# CareerCaster User Guide 💼

Welcome to **CareerCaster**, your stealth AI interview assistant.

## 🚀 Quick Start
1.  **Web Hub**: Open the Streamlit dashboard, upload your resume and the job description.
2.  **Handshake**: Click "Save & Prepare" to generate your encrypted session.
3.  **Launch**: Click "START INTERVIEW" to trigger the Desktop Agent.
4.  **Overlay**: The invisible overlay will appear. Use the "⠿" handle to move it.

## 🛡️ Security & Privacy
- **Stealth Mode**: The overlay is invisible to Zoom, Teams, OBS, and other screen-sharing software.
- **Encryption**: All session data is encrypted using AES-256 and locked to your specific machine.
- **Local Only**: No audio or resume data is stored on our servers; everything stays on your laptop.

## ⚠️ Windows Defender / Antivirus "False Positives"
Because CareerCaster uses low-level Windows APIs (for stealth and audio capture) and is packaged with PyInstaller, some antivirus software might flag it as "Unknown" or "Suspicious".

### How to Allowlist/Exclude CareerCaster:
1.  Open **Windows Security** (Start -> type "Windows Security").
2.  Go to **Virus & threat protection** -> **Manage settings**.
3.  Scroll down to **Exclusions** -> **Add or remove exclusions**.
4.  Click **Add an exclusion** -> **Folder**.
5.  Select the folder where you extracted `CareerCaster`.

## 🎤 Audio Troubleshooting
- Ensure your system audio is not muted.
- If the status shows "● NO AUDIO", check if your Windows WASAPI loopback device is enabled in Sound Settings.

## 📂 Session Management
- Use the 📂 icon in the overlay header to switch between your 5 most recent interview sessions without restarting.
