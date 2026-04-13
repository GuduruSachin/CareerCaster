# CareerCaster TODO 📝

## Phase 1: Foundation (Completed)
- [x] Monorepo structure setup.
- [x] Custom URI Protocol registration (`careercaster://`).
- [x] Streamlit Web Dashboard with PDF parsing.
- [x] PyQt6 Stealth Overlay with Windows API capture exclusion.
- [x] Session persistence via JSON.

## Phase 2: AI Intelligence (Completed)
- [x] Integrate initial AI "Deep Analysis" (Resume vs. JD).
- [x] Integrate real-time audio transcription (WASAPI Loopback).
- [x] Implement Advanced Interview Reasoning (Categorized hints, Context Tags).
- [x] Implement Gemini 3.1 Pro for advanced interview reasoning.
- [x] Migrate exclusively to `google-genai` SDK and remove legacy SDK.

## Phase 3: Distribution & Deployment (Completed)
- [x] Implement AES-256 local encryption for session data.
- [x] Implement Path Normalization for EXE/Script compatibility.
- [x] Implement a local "Session Manager" (Switcher) in the Agent.
- [x] Create PyInstaller specification (`.spec`) for Windows distribution.
- [x] Create `USER_GUIDE.md` for end-user instructions.
- [x] Modernize Overlay UI (Resizable, Control Bar, Transparency).
- [x] Implement Detached Process Launch for CMD-less operation.
- [x] Implement Auto-Sample Rate Detection for audio hardware.
- [x] Icon Integration: Prepare `assets/logo.ico` for the window and taskbar.
- [x] Resource Bundling: Ensure all `.cc` session files and `logs/` are handled in a temporary user directory.
- [x] PyInstaller Build: Create the standalone `.exe` configuration.
- [ ] macOS/Linux support (without Windows-specific stealth API).

## Phase 4: Live Chat & Voice Focus (Completed)
- [x] Implement Dual-Bubble Chat UI (Interviewer vs. Advisor).
- [x] Implement Voice Focus (Ignore interviewee, focus on interviewer).
- [x] Implement Graceful Shutdown (Thread joining & resource cleanup).
- [x] Migrate to Gemini 3.1 Flash-Lite for ultra-low latency.
- [x] Implement Stealth Answer Logic (Brevity & Bold keywords).
- [x] Implement API Black Box Recorder (JSONL Logging).
- [x] Implement Preview Mode (Safety Gatekeeper).
- [x] Implement STAR Segmented UI with Right Arrow advancement.
- [x] Implement Follow-up Predictor (Pro-Tip box).
- [x] Implement Persona Toggle (Ctrl+T) with UI flash feedback.
- [x] Implement API Diagnostics & Telemetry (Rotating 2MB logs).
- [x] Implement Nuclear Kill-Switch (Ctrl+Shift+K) with clipboard/log wipe.
- [x] Implement Input Isolation (Active window check).

## Technical Debt
- [ ] Refactor path resolution to use absolute project root.
- [ ] Implement robust error handling for registry access.
- [ ] Add unit tests for PDF parsing and URI handling.
