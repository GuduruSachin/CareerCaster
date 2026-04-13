# CareerCaster User Guide 💼

Welcome to **CareerCaster**, your stealth AI interview assistant.

## 🚀 Quick Start
1.  **Web Hub**: Open the Streamlit dashboard, upload your resume and the job description.
2.  **Handshake**: Click "Save & Prepare" to generate your encrypted session.
3.  **Launch**: Click "START INTERVIEW" to trigger the Desktop Agent. It will launch in detached mode (no CMD window).
4.  **Chat Interface**: 
    - **Interviewer (Left)**: Transcribed questions in gray bubbles.
    - **AI Advisor (Right)**: STAR-segmented advice. Use the **Right Arrow** to reveal segments one by one.
    - **Persona Toggle**: Press **Ctrl+T** to switch between 'Strategic' and 'Deep Systems' modes.
    - **Follow-up Predictor**: View the 'Pro-Tip' box for likely interviewer follow-ups.
    - **Auto-Scroll**: The chat automatically scrolls to the latest message.
    - **Battle Plan**: Click "Show Battle Plan" at the bottom to view your initial analysis.
    - **Move**: Drag the "⠿" handle.
    - **Resize**: Drag the bottom-right corner.
    - **Screenshot**: Click 📸 to save a capture to the `/screenshots` folder.
    - **Mute**: Click 🎤 to pause AI processing.
    - **Close**: Click ❌ to end the session gracefully.
    - **Nuclear Kill-Switch**: Press **Ctrl+Shift+K** for an instant emergency wipe.

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
- The health indicator (small circle) should be **Green**. If it turns **Red**, it means no audio has been detected for 10 seconds.
- CareerCaster automatically detects your hardware's sample rate. If you see "● AUDIO ERROR", try restarting the agent.

## 📂 Session Management
- Sessions are managed via the Web Hub. Each "Save & Prepare" action creates a fresh encrypted session for the agent.
