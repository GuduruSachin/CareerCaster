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
3. **Launch**: Click "START INTERVIEW". This triggers the `careercaster://` protocol.
4. **Overlay**: The Desktop Agent launches an invisible-to-screen-share overlay providing real-time hints.

## Security & Stealth
The Desktop Agent uses the Windows API `SetWindowDisplayAffinity` with `WDA_EXCLUDEFROMCAPTURE` to ensure the overlay is not visible to meeting software like Zoom, Teams, or OBS.
