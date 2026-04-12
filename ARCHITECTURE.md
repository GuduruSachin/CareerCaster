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

## Real-Time Audio Pipeline: VAD State Machine
CareerCaster uses a high-precision Voice Activity Detection (VAD) state machine to ensure natural, low-latency interactions:

1. **State: IDLE**: The system monitors 30ms audio frames. If RMS energy exceeds a configurable threshold, it transitions to RECORDING.
2. **State: RECORDING**: Audio frames are accumulated into a `BytesIO` buffer. If silence is detected, a counter begins.
3. **State: PROCESSING**: If silence persists for >800ms, the buffer is finalized and sent to the Gemini API. The system then returns to IDLE.

## Logging & Safety Layer
To protect users from unexpected costs and provide diagnostic transparency:
- **Black Box Recorder**: Every API call is logged to `logs/api_history.jsonl` with timestamps, latency, and status codes.
- **Preview Mode**: A safety gatekeeper that allows users to verify hardware and VAD triggers without calling the Gemini API.
- **Quota Tracking**: Explicitly captures 429 (Resource Exhausted) errors to help users manage their Free Tier limits.

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
