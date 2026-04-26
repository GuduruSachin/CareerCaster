import streamlit as st
import uuid
import json
import os
import sys
import subprocess
import time

# --- Path Fix for Monorepo ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pypdf import PdfReader
from core.security import SecurityManager
from core.paths import get_sessions_dir
from core.credentials import get_master_api_key

# --- Configuration & Safety ---
SESSIONS_DIR = get_sessions_dir()

def terminate_existing_agent():
    """Checks for existing CareerCaster.exe processes and terminates them."""
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "CareerCaster.exe", "/T"], 
                           capture_output=True, check=False)
            print("Pre-flight: Existing CareerCaster processes terminated.")
        except Exception as e:
            print(f"Pre-flight Error: {e}")

# --- Streamlit UI Setup ---
st.set_page_config(page_title="CareerCaster Dashboard", page_icon="💼")

# --- Session State Initialization ---
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""
if "session_id" not in st.session_state:
    st.session_state.session_id = None

# --- Design Preview Loader ---
if st.sidebar.checkbox("🎨 Show UI Design Preview", False):
    st.subheader("Design Preview: CareerCaster v1.8 Specialist Interface")
    try:
        with open(os.path.join(PROJECT_ROOT, "design_preview", "index.html"), "r", encoding="utf-8") as f:
            html_content = f.read()
            st.components.v1.html(html_content, height=850, scrolling=True)
            st.stop()
    except Exception as e:
        st.error(f"Could not load design preview: {e}")

# --- Design Preview Loader (Mandatory for Review) ---
# try:
#     with open(os.path.join(PROJECT_ROOT, "design_preview", "index.html"), "r", encoding="utf-8") as f:
#         html_content = f.read()
#         st.components.v1.html(html_content, height=950, scrolling=True)
#         st.info("💡 Note: This is an interactive design mockup of the Specialist Python UI. Local system connection features are active in the desktop agent.")
#         st.divider()
# except Exception as e:
#     st.error(f"Could not load design preview: {e}")

st.title("💼 CareerCaster: Web Hub v1.8")

# --- Sidebar: Simplified Account Status ---
with st.sidebar:
    st.header("👤 Account Status")
    api_key = get_master_api_key()
    if api_key and api_key != "YOUR_ENTERPRISE_API_KEY_HERE":
        st.success("AI STATUS: SECURE CONNECTION ✅")
    else:
        st.warning("AI STATUS: PENDING CONFIGURATION")
    
    st.divider()
    st.info("The Web Hub is now for Data Input only. AI Settings have moved to the Green Room co-pilot.")

# --- Main UI Components ---
st.subheader("📄 Step 1: Upload Data")

resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

if resume_file:
    if resume_file.size > 3 * 1024 * 1024:
        st.error("File too large! Max 3MB.")
        resume_file = None
    else:
        # Extract text once
        if not st.session_state.resume_text or st.session_state.get("last_uploaded") != resume_file.name:
            try:
                # Important: Fix the PdfReader import as it might be 'pypdf' now
                try:
                    from pypdf import PdfReader
                except ImportError:
                    from PyPDF2 import PdfReader
                    
                reader = PdfReader(resume_file)
                text = "".join([page.extract_text() or "" for page in reader.pages])
                st.session_state.resume_text = text.strip()
                st.session_state.last_uploaded = resume_file.name
            except Exception as e:
                st.error(f"Error reading PDF: {e}")

jd_text = st.text_area("Paste Job Description (JD)", height=300, placeholder="Paste the full job description here...")

# --- Operation: The Clean Launch ---
can_prepare = st.session_state.resume_text and jd_text

st.divider()
if st.button("🚀 Launch Interview Copilot", disabled=not can_prepare, type="primary", use_container_width=True):
    try:
        with st.spinner("Encrypting & Handshaking..."):
            session_id = str(uuid.uuid4())
            st.session_state.session_id = session_id
            
            # Prepare normalization data
            session_data = {
                "api_key": api_key,
                "resume_text": st.session_state.resume_text,
                "jd_text": jd_text,
                "candidate_name": "Candidate",
                "target_role": "Target Role",
                "session_id": session_id,
            }
            
            security = SecurityManager()
            encrypted_data = security.encrypt_data(json.dumps(session_data))
            
            # Save to sessions folder
            file_path = os.path.join(SESSIONS_DIR, f"{session_id}.cc")
            with open(file_path, "wb") as f:
                f.write(encrypted_data)
            
            # Sync to EXE dist folder as well (Silent)
            exe_sessions_dir = os.path.join(PROJECT_ROOT, "dist", "CareerCaster", "sessions")
            if os.path.exists(os.path.dirname(exe_sessions_dir)):
                os.makedirs(exe_sessions_dir, exist_ok=True)
                with open(os.path.join(exe_sessions_dir, f"{session_id}.cc"), "wb") as f:
                    f.write(encrypted_data)

            # --- v1.7.1 RESOLVE [WinError 87] & HARDEN LAUNCH SEQUENCE ---
            abs_session_path = os.path.normpath(os.path.abspath(file_path))
            
            # --- USER RECOVERY COMMAND ---
            st.info("💡 **Manual Recovery Command**\nIf the desktop app fails to open, copy and run this in your terminal:")
            project_base = "C:\\Users\\hp\\source\\repos\\CareerCaster"
            exe_cmd_path = f"{project_base}\\dist\\CareerCaster\\CareerCaster.exe"
            session_cmd_path = f"{project_base}\\sessions\\{session_id}.cc"
            st.code(f'"{exe_cmd_path}" "{session_cmd_path}"', language="bash")

            if not os.path.exists(abs_session_path):
                st.error("FATAL: Session file failed to write to disk.")
                st.stop()

            try:
                terminate_existing_agent()
                
                exe_path = os.path.normpath(os.path.join(PROJECT_ROOT, "dist", "CareerCaster", "CareerCaster.exe"))
                agent_path = os.path.normpath(os.path.join(PROJECT_ROOT, "desktop_agent", "main.py"))
                
                # Windows Flag Fix: Use ONLY CREATE_NEW_CONSOLE (0x10) to avoid Param 87 mismatch
                launch_flags = 0x00000010 if sys.platform == "win32" else 0
                
                if os.path.exists(exe_path):
                    launch_cmd = [exe_path, abs_session_path]
                    st.info(f"Auto-Launching CareerCaster Pro (EXE)...")
                    print(f"Bridgeing to EXE: {launch_cmd}")
                    subprocess.Popen(
                        launch_cmd, 
                        creationflags=launch_flags, 
                        shell=False,
                        close_fds=True
                    )
                else:
                    # In Dev mode, use the start command to ensure Environment inheritance (GEMINI_API_KEY)
                    if sys.platform == "win32":
                        # v1.7.7: Fix path quoting for spaces in PROJECT_ROOT or session paths
                        # Using "" title dummy and nested quotes for cmd /c
                        launch_cmd = f'start "" /b cmd /c ""{sys.executable}" "{agent_path}" "{abs_session_path}""'
                        st.warning("EXE not found. Auto-Launching via Shell Context (Debug Mode)...")
                        print(f"Launching Agent Shell: {launch_cmd}")
                        subprocess.Popen(launch_cmd, shell=True, env=os.environ.copy())
                    else:
                        launch_cmd = [sys.executable, agent_path, abs_session_path]
                        st.warning("EXE not found. Auto-Launching via Python...")
                        print(f"Launching Agent: {launch_cmd}")
                        subprocess.Popen(launch_cmd, close_fds=True, env=os.environ.copy())
                
                st.balloons()
                st.success("Interview Copilot Handshaked & Launched!")
            except Exception as launch_err:
                st.error(f"Launch Bridge Failed: {launch_err}")
                print(f"ERROR: Failed to launch command: {launch_cmd}")
            
    except Exception as e:
        st.error(f"SaaS Bridge Fatal: {e}")

st.caption("CareerCaster v1.7 | Full Architectural Cleanup")
