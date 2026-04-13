# CareerCaster 🚀

CareerCaster is a hybrid Python application designed to provide a real-time, stealthy AI interview assistant. It bridges a modern Web Dashboard with a local Desktop Agent using a custom URI protocol.

## Project Structure

- **/web_hub**: Streamlit-based dashboard for uploading resumes and job descriptions.
- **/desktop_agent**: PyQt6-based stealth overlay that displays AI-generated hints.
- **/sessions**: Shared directory for persisting session data between the web and desktop components.
- **/core**: Shared logic and utilities.

## Setup Instructions

### 1. Prerequisites
- Python 3.13.5
- Windows OS (for Stealth Overlay functionality)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Register Custom Protocol
Run the setup script to register the `careercaster://` URI scheme on your Windows machine:
```bash
python desktop_agent/protocol_setup.py
```

### 4. Run the Web Dashboard
```bash
streamlit run web_hub/app.py
```

## How it Works
1. **Upload**: Paste your JD and upload your Resume PDF in the Web Hub.
2. **Prepare**: Click "Save & Prepare" to generate a unique session ID and persist data.
3. **Launch**: Click "START INTERVIEW". This launches the Desktop Agent in **Detached Mode** (no CMD window).
4. **Chat UI**: A modern, resizable, semi-transparent chat interface appears. It displays interviewer questions and AI advice in distinct bubbles.
5. **STAR System**: AI responses are broken into Situation, Task, Action, and Result. Use the **Right Arrow** to reveal segments one by one for natural pacing.
6. **Persona Toggle**: Press **Ctrl+T** to switch between 'Strategic Leadership' and 'Deep Systems' modes instantly.
7. **Preview Mode**: Toggle "Preview Mode" in the dashboard to test hardware and VAD logic without incurring AI costs.
8. **Controls**: Use the header bar to take screenshots (📸), mute (🎤), or gracefully close the session (❌).
9. **Safety**: Press **Ctrl+Shift+K** (Kill-Switch) at any time to instantly wipe all data and clear the clipboard.

## Security & Stealth
- **Capture Exclusion**: Uses `WDA_EXCLUDEFROMCAPTURE` to ensure the overlay is invisible to Zoom, Teams, and OBS.
- **Hardware-Locked Encryption**: Session data is encrypted with AES-256, keyed to your machine's unique hardware UUID.
- **Nuclear Kill-Switch**: Press **Ctrl+Shift+K** to instantly terminate all threads, wipe all session/log files, and clear the Windows Clipboard.
- **API Telemetry**: High-precision logging in `logs/api_performance.log` tracks latency and request status with a 2MB rotating buffer.
