# CareerCaster Architecture 🏗️

## System Overview
CareerCaster operates as a **Hybrid Bridge** application. It leverages the accessibility of a web interface with the low-level system control of a desktop application.

## The Web-to-Desktop Handshake
1. **Data Ingestion**: The Streamlit Web Hub (`web_hub/app.py`) collects user data (Resume, JD, API Key).
2. **AI Deep Analysis**: The Web Hub calls Gemini 1.5 Flash to generate a "Battle Plan" based on the Resume and JD.
3. **Persistence**: Data and the AI Analysis are serialized into a JSON file in the `/sessions` directory, keyed by a unique UUID and encrypted as a `.cc` file.
4. **Trigger**: The Web Hub uses `subprocess.Popen` with `DETACHED_PROCESS` flags to launch the agent directly, passing the UUID as a handshake.
5. **Agent Activation**: The Desktop Agent (`desktop_agent/main.py`) initializes, decrypts the session, and prepares the WASAPI Loopback engine.

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
3. **State: PROCESSING**: If silence persists for >600ms, the buffer is finalized and sent to the Gemini API. The system then returns to IDLE.

## AI Reasoning: STAR & Predictor
The system uses a structured JSON schema to support the segmented UI:
- **Schema**: `{S, T, A, R, ProTip}` (Situation, Task, Action, Result, Follow-up Prediction).
- **Humanized Hooks**: The prompt forces the AI to use 5-8 word "technical hooks" instead of paragraphs, defeating AI cadence detectors.
- **Persona Toggle**: Ctrl+T shifts the system instructions between 'Strategic' and 'Deep Systems' focus.

## Logging & Telemetry
To protect users from unexpected costs and provide diagnostic transparency:
- **API Telemetry**: High-precision logging in `logs/api_performance.log` tracks latency and request status.
- **Rotating Buffer**: Uses a `RotatingFileHandler` (2MB max) to prevent log bloat.
- **Latency Warning**: Automatically flags requests taking >3s for performance auditing.
- **Preview Mode**: A safety gatekeeper that allows users to verify hardware and VAD triggers without calling the Gemini API.

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
- **Nuclear Kill-Switch**: Pressing **Ctrl+Shift+K** triggers an immediate data wipe (sessions and logs), clears the clipboard, and terminates all threads.
- **Session Cleanup**: The session file is automatically deleted when the ❌ Close button is clicked in the overlay.
- **Registry**: Custom protocol requires write access to `HKEY_CURRENT_USER`.
