# CareerCaster Architecture 🏗️

## System Overview
CareerCaster operates as a **Hybrid Bridge** application. It leverages the accessibility of a web interface with the low-level system control of a desktop application.

## The Web-to-Desktop Handshake
1. **Data Ingestion**: The Streamlit Web Hub (`web_hub/app.py`) collects user data (Resume, JD, API Key).
2. **AI Deep Analysis**: The Web Hub calls Gemini 1.5 Flash to generate a "Battle Plan" based on the Resume and JD.
3. **Persistence**: Data and the AI Analysis are serialized into a JSON file in the `/sessions` directory, keyed by a unique UUID.
4. **Trigger**: The Web Hub uses `subprocess.Popen` with `DETACHED_PROCESS` flags to launch the agent directly, with a fallback to the `careercaster://` protocol.
5. **Agent Activation**: The Desktop Agent (`desktop_agent/main.py`) initializes using only the modern `google-genai` SDK.

## Security Mechanism: AES-256 Encryption
To protect sensitive user data (Resume, JD, API Keys) at rest, CareerCaster implements a local security layer:

- **Library**: `cryptography.fernet` (AES-256 in CBC mode with HMAC).
- **Key Derivation**: 
    - **Password**: Derived from the machine's unique Hardware ID (UUID via `wmic`).
    - **KDF**: `PBKDF2HMAC` with SHA256 and a fixed salt.
- **Persistence**: Session files are stored with a `.cc` extension in an encrypted binary format. This ensures that even if the files are stolen, they cannot be decrypted on a different machine.

## Path Normalization & Distribution
To ensure the application runs correctly as both a Python script and a bundled Windows EXE, a dedicated path resolution utility (`core/paths.py`) is used:
- **Frozen State Detection**: Uses `sys.frozen` to identify if the app is running as a PyInstaller bundle.
- **Dynamic Root Discovery**:
    - **EXE Mode**: Root is the directory containing the executable.
    - **Script Mode**: Root is the project base directory.
- **Session Persistence**: Prioritizes a local `sessions/` folder but can fallback to `%APPDATA%` if the installation directory is read-only.

## Stealth Mechanism: Ghost Overlay
To ensure the assistant remains invisible during screen-sharing (Zoom/Teams/OBS), the agent utilizes the Windows User32 API:

- **Function**: `SetWindowDisplayAffinity`
- **Flag**: `WDA_EXCLUDEFROMCAPTURE (0x00000011)`
- **Effect**: The window is rendered by the GPU for the local user but is skipped by the Desktop Window Manager (DWM) during capture/composition for external streams.

## Real-Time Audio Pipeline
1. **Capture**: `PyAudio` captures system output via **Windows WASAPI Loopback**.
2. **Auto-Detection**: The system automatically detects the best sample rate (16kHz, 44.1kHz, or 48kHz) to ensure hardware compatibility.
3. **Chunking**: Audio is buffered into 4-second chunks with a 1-second sliding window overlap for context.
4. **Advanced Reasoning**: 
    - **Voice Focus**: AI is instructed to ignore the interviewee and focus exclusively on the interviewer's voice.
    - **Brevity**: AI answers are strictly limited to under 20 words for instant readability.
    - **Formatting**: Technical keywords are automatically **BOLDED**.
5. **Processing**: Chunks are processed exclusively using the `google-genai` SDK on the `v1beta` endpoint using the **Gemini 3.1 Flash-Lite** model for ultra-low latency.
6. **UI Update**: 
    - **Dual-Bubble Chat**: Interviewer questions (Left/Gray) and AI Advice (Right/Blue) are displayed in a scrollable chat interface.
    - **Auto-Scroll**: The chat automatically scrolls to the bottom as new messages arrive.
    - **Graceful Shutdown**: The agent ensures all threads are joined and resources released before exiting.

## Data Flow Diagram
```text
[User] -> [Streamlit Web Hub] -> [JSON File (sessions/)]
               |
               v
       [Custom URI Trigger] -> [Windows Registry]
                                     |
                                     v
                            [PyQt6 Desktop Agent] <- [JSON File]
                                     |
                                     v
                            [Stealth Ghost Overlay]
```

## Security Considerations
- **API Keys**: Stored locally in encrypted `.cc` session files.
- **Session Cleanup**: The session file is automatically deleted when the ❌ Close button is clicked in the overlay.
- **Registry**: Custom protocol requires write access to `HKEY_CURRENT_USER`.
