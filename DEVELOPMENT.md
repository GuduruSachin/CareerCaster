# CareerCaster Development & Telemetry 🛠️

## Development Environment
CareerCaster is a hybrid application requiring both a web server (Streamlit) and a local desktop environment (PyQt6).

### 1. Project Structure
- `/web_hub`: Streamlit dashboard.
- `/desktop_agent`: PyQt6 overlay.
- `/core`: Shared logic (Security, Audio, Paths).
- `/logs`: API telemetry and diagnostics.

## API Telemetry & Performance
To ensure production stability and monitor API costs, CareerCaster implements a robust telemetry system.

### 1. Telemetry Log (`logs/api_performance.log`)
Every interaction with the Gemini API is recorded in a structured, single-line format for easy parsing and auditing.
- **Format**: `[TIMESTAMP] [REQUEST] (Persona: X, Context: Y chars) [RESPONSE] (Latency: Z.ZZs, S: "...") [STATUS] (SUCCESS/ERROR)`
- **Privacy**: Full prompt text is never logged. Only character counts and truncated response previews are stored to maintain session security.

### 2. Log Rotation
To prevent the application from consuming excessive disk space, the telemetry system uses a `RotatingFileHandler`.
- **Max Size**: 2MB per file.
- **Backup Count**: 5 historical logs are kept.
- **Cleanup**: The entire `logs/` directory is wiped during a **Nuclear Kill-Switch** event or a graceful session close.

### 3. Interpreting Latency Warnings
The system automatically monitors the Round-Trip Time (RTT) for every AI request.
- **Warning Threshold**: > 3.0 seconds.
- **Log Flag**: `[WARNING: HIGH_LATENCY]`
- **Actionable Insights**:
    - **High Latency + Success**: Usually indicates network congestion or high load on the Gemini API.
    - **High Latency + Error**: May indicate a timeout or a complex prompt that exceeded the model's processing window.
    - **Low Latency + Success**: Ideal performance (typically < 1.5s).

## Build & Distribution
We use **PyInstaller** to package the agent for Windows.
- **Spec File**: `main.spec`
- **Key Flags**:
    - `console=False`: Hides the CMD window for stealth.
    - `icon='assets/logo.ico'`: Sets the application and taskbar branding.
    - `datas`: Bundles the `assets/` and `core/` directories into the binary.

## Testing the Workflow
1. Start the Web Hub: `streamlit run web_hub/app.py`
2. Prepare a session and click "START INTERVIEW".
3. Monitor `logs/api_performance.log` in real-time to verify the VAD-to-API pipeline.
