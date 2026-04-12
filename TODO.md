# CareerCaster TODO 📝

## Phase 1: Foundation (Completed)
- [x] Monorepo structure setup.
- [x] Custom URI Protocol registration (`careercaster://`).
- [x] Streamlit Web Dashboard with PDF parsing.
- [x] PyQt6 Stealth Overlay with Windows API capture exclusion.
- [x] Session persistence via JSON.

## Phase 2: AI Intelligence (In Progress)
- [x] Integrate initial AI "Deep Analysis" (Resume vs. JD).
- [x] Integrate real-time audio transcription (WASAPI Loopback).
- [x] Implement Advanced Interview Reasoning (Categorized hints, Context Tags).
- [ ] Implement Gemini 3.1 Pro for advanced interview reasoning.

## Phase 3: Distribution & UX
- [x] Implement AES-256 local encryption for session data.
- [x] Implement Path Normalization for EXE/Script compatibility.
- [x] Implement a local "Session Manager" (Switcher) in the Agent.
- [x] Create PyInstaller specification (`.spec`) for Windows distribution.
- [x] Create `USER_GUIDE.md` for end-user instructions.
- [ ] macOS/Linux support (without Windows-specific stealth API).

## Technical Debt
- [ ] Refactor path resolution to use absolute project root.
- [ ] Implement robust error handling for registry access.
- [ ] Add unit tests for PDF parsing and URI handling.
