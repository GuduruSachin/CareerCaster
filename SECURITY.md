# CareerCaster Security 🛡️

## Stealth Implementation: Ghost Overlay
CareerCaster is designed to be completely invisible to screen-sharing and recording software. This is achieved through a low-level integration with the Windows Desktop Window Manager (DWM).

### 1. Capture Exclusion API
The Desktop Agent utilizes the `SetWindowDisplayAffinity` function from the Windows User32 library.
- **Implementation**: `ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)`
- **Mechanism**: The `WDA_EXCLUDEFROMCAPTURE` flag instructs the DWM to omit the window's content from any "composition" that isn't the primary display output.
- **Effect**: You can see the overlay on your monitor, but anyone viewing your screen via Zoom, Microsoft Teams, Google Meet, or OBS will see only the background behind the overlay.

## Data Protection: Hardware-Locked Encryption
To ensure that session data (including API keys and resumes) cannot be used if stolen, CareerCaster implements machine-specific encryption.

### 1. BIOS UUID Hardware-Locking
The encryption key is not stored on disk. Instead, it is derived dynamically at runtime using the machine's unique hardware signature.
- **Hardware ID**: The system retrieves the BIOS UUID using the command `wmic csproduct get uuid`.
- **Key Derivation**: We use `PBKDF2HMAC` with SHA256, 100,000 iterations, and a fixed salt to derive a 32-byte key from the hardware ID.
- **Encryption Standard**: AES-256 (via the `cryptography.fernet` library).
- **Result**: A `.cc` session file created on "Machine A" is cryptographically impossible to decrypt on "Machine B."

## Emergency Protocols: Nuclear Kill-Switch
CareerCaster includes a high-priority emergency handler designed for instant data sanitization.

### 1. The Kill-Switch (Ctrl+Shift+K)
When the global hotkey `Ctrl+Shift+K` is detected, the following sequence is executed immediately:
1. **Thread Termination**: The audio capture and AI processing threads are forcefully terminated.
2. **File Wipe**: Every file in the `sessions/` and `logs/` directories is permanently deleted.
3. **Clipboard Sanitization**: The Windows Clipboard is cleared using `cmd /c "echo off | clip"` to remove any sensitive technical snippets or AI advice.
4. **Process Exit**: The application performs an `os._exit(0)` to bypass standard cleanup and shut down instantly.

## Privacy Policy
- **Zero Cloud Storage**: CareerCaster does not upload your audio, resume, or job descriptions to any central server. All processing happens locally or via direct, encrypted calls to the Gemini API.
- **Local Logs**: API telemetry is stored in a rotating 2MB local buffer and is wiped during any secure cleanup or kill-switch event.
