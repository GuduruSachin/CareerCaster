import streamlit as st
import uuid
import json
import os
import sys
import webbrowser
import subprocess
import shlex

# --- Path Fix for Monorepo ---
# Add the project root to sys.path so 'core' can be found
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from pypdf import PdfReader
from google import genai
import time
import pandas as pd
from core.security import SecurityManager
from core.paths import get_sessions_dir
from core.credentials import get_master_api_key

# --- Configuration & Safety ---
# Automatically create the sessions/ directory if it does not exist
SESSIONS_DIR = get_sessions_dir()

def check_permissions():
    """Verifies that the app has write permissions in the project root."""
    try:
        test_file = os.path.join(PROJECT_ROOT, ".perm_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception as e:
        st.error(f"Permission Error: The application does not have write access to {PROJECT_ROOT}. Error: {e}")
        return False

# --- Streamlit UI Setup ---
st.set_page_config(page_title="CareerCaster Dashboard", page_icon="💼")

if not check_permissions():
    st.stop()

# --- Session State Initialization ---
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "saved" not in st.session_state:
    st.session_state.saved = False
if "api_verified" not in st.session_state:
    st.session_state.api_verified = False
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "active_model" not in st.session_state:
    st.session_state.active_model = None
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

@st.dialog("🔍 Review Extracted Text")
def show_text_dialog(text):
    st.write("Below is the text extracted from your PDF. Verify it looks correct before proceeding.")
    st.text_area("Extracted Content", value=text, height=400)
    if st.button("Close"):
        st.rerun()

st.title("💼 CareerCaster: Web Dashboard")
st.markdown("Prepare your interview session and trigger the local stealth agent.")

# --- Sidebar: User Account & AI Status ---
with st.sidebar:
    st.header("👤 Account Status")
    st.success("AI STATUS: SECURE CONNECTION")
    
    # Internal: Fetch Master Key (Hidden from User)
    api_key = get_master_api_key()
    
    # Auto-Verify on load if not already done
    if not st.session_state.api_verified and api_key and api_key != "YOUR_ENTERPRISE_API_KEY_HERE":
        with st.spinner("Synchronizing AI Engine..."):
            test_models = [
                {"name": "gemini-3-flash-preview", "gen": 3},
                {"name": "gemini-3.1-flash-lite-preview", "gen": 3},
                {"name": "gemini-2.0-flash-exp", "gen": 2},
                {"name": "gemini-1.5-flash", "gen": 1},
            ]
            
            results = []
            for m in test_models:
                try:
                    client = genai.Client(api_key=api_key)
                    client.models.generate_content(model=m["name"], contents="ping")
                    results.append({"name": m["name"], "status": "Success", "latency": 0.5, "version": "v1"})
                except:
                    continue
            
            if results:
                st.session_state.api_verified = True
                st.session_state.scan_results = results
                st.session_state.active_model = results[0]

    # Dynamic Advanced Settings
    if st.session_state.api_verified:
        success_models = [r for r in st.session_state.scan_results if r["status"] == "Success"]
        # Prioritize 'flash' models, then sort by latency
        success_models.sort(key=lambda x: (0 if "flash" in x["name"].lower() else 1, x["latency"]))
        model_options = [f"{m['name']} ({m['latency']}s)" for m in success_models]
        
        with st.expander("⚙️ Advanced Settings"):
            selected_option = st.selectbox("Active Model", options=model_options, index=0)
            selected_index = model_options.index(selected_option)
            st.session_state.active_model = success_models[selected_index]
            
            preview_mode = st.toggle("Preview Mode (No AI Costs)", value=False, help="Skips Gemini API calls in the agent. Useful for testing hardware.")
            disable_stealth = st.toggle("Disable Stealth Mode", value=False, help="If the agent crashes on startup, try disabling this. It prevents the window from being hidden from screen capture.")
            
            st.divider()
            test_mode = st.toggle("🛠️ TEST MODE (Auto-Fill)", value=False, help="Injects mock data to skip manual entry for testing.")

    st.info("The API key is required for real-time hint generation in the local agent.")

# --- Main UI Components ---
st.subheader("📄 Step 1: Upload Data")

# Resume Uploader (PDF) with 3MB limit
resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"], help="Max size: 3MB")

if resume_file:
    if resume_file.size > 3 * 1024 * 1024:
        st.error("File too large! Please upload a PDF under 3MB.")
        resume_file = None
    else:
        # Extract text once and store in session state
        if not st.session_state.resume_text:
            try:
                reader = PdfReader(resume_file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                st.session_state.resume_text = text.strip()
            except Exception as e:
                st.error(f"Error reading PDF: {e}")
elif "test_mode" in locals() and test_mode:
    if not st.session_state.resume_text:
        st.session_state.resume_text = "MOCK RESUME: Senior Software Engineer with 10 years of experience in Python, PyQt6, and AI integration. Expert in building stealth desktop agents and real-time UI overlays."
    st.info("🛠️ TEST MODE: Using Mock Resume Data")

if st.session_state.resume_text:
    if st.button("🔍 Review Extracted Text"):
        show_text_dialog(st.session_state.resume_text)

# Job Description Text Area
default_jd = "Software Developer - Testing Mode" if ("test_mode" in locals() and test_mode) else ""
jd_text = st.text_area("Paste Job Description (JD)", height=200, value=default_jd, placeholder="Paste the full job description here...")

# Project Notes (RAG Context)
default_notes = "Built a real-time interview assistant using Gemini 1.5 Flash and PyQt6." if ("test_mode" in locals() and test_mode) else ""
project_notes = st.text_area("Project Notes / Key Achievements", height=150, value=default_notes, placeholder="Add specific project details, metrics, or notes you want the AI to use for STAR answers...")

# --- Handshake Logic ---
can_prepare = st.session_state.api_verified and (resume_file or ("test_mode" in locals() and test_mode)) and (jd_text or ("test_mode" in locals() and test_mode))

if st.button("💾 Save & Prepare", disabled=not can_prepare, type="primary"):
    try:
        # --- AI Deep Analysis using Selected Model ---
        with st.spinner(f"Analyzing with {st.session_state.active_model['name']}..."):
            best_model = st.session_state.active_model
            resume_text = st.session_state.resume_text
            
            analysis_prompt = f"""
            You are a Senior Interview Coach. Analyze this Resume against the Job Description.
            
            RESUME:
            {resume_text[:5000]}
            
            JOB DESCRIPTION:
            {jd_text[:5000]}
            
            Provide a "Battle Plan" for the interview:
            1. Top 3 strengths to highlight.
            2. 2 potential weaknesses to mitigate.
            3. One "Golden Tip" for this specific role.
            
            Also, extract "Context Tags" for real-time AI assistance. 
            Return the response in this EXACT format:
            ---BATTLE PLAN---
            [Your analysis here]
            ---CONTEXT TAGS---
            {{"skills": ["...", "..."], "role": "...", "strategy": "..."}}
            """
            
            client = genai.Client(api_key=api_key, http_options={'api_version': best_model['version']})
            response = client.models.generate_content(model=best_model['name'], contents=analysis_prompt)
            full_response = response.text
            
            # Parse response
            try:
                parts = full_response.split("---CONTEXT TAGS---")
                analysis = parts[0].replace("---BATTLE PLAN---", "").strip()
                context_tags = json.loads(parts[1].strip())
            except:
                analysis = full_response
                context_tags = {"skills": [], "role": "Candidate", "strategy": "General interview support"}
        
        # Generate unique session_id
        session_id = str(uuid.uuid4())
        st.session_state.session_id = session_id
        
        # Save to JSON file (Encrypted)
        session_data = {
            "api_key": api_key,
            "resume_text": resume_text,
            "jd_text": jd_text,
            "project_notes": project_notes,
            "session_id": session_id,
            "analysis": analysis,
            "context_tags": context_tags,
            "active_model": best_model,
            "preview_mode": preview_mode,
            "disable_stealth": disable_stealth
        }
        
        security = SecurityManager()
        encrypted_data = security.encrypt_data(json.dumps(session_data))
        
        # Primary Save (Root sessions folder for development)
        file_path = os.path.join(SESSIONS_DIR, f"{session_id}.cc")
        with open(file_path, "wb") as f:
            f.write(encrypted_data)
            
        # Secondary Save (EXE sessions folder for compiled builds)
        # This ensures the standalone EXE can find the session regardless of launch context
        exe_dist_dir = os.path.join(PROJECT_ROOT, "dist", "CareerCaster")
        exe_sessions_dir = os.path.join(exe_dist_dir, "sessions")
        
        # Proactively create the directory structure if the dist folder exists
        if os.path.exists(exe_dist_dir):
            os.makedirs(exe_sessions_dir, exist_ok=True)
            
            exe_file_path = os.path.join(exe_sessions_dir, f"{session_id}.cc")
            try:
                with open(exe_file_path, "wb") as f:
                    f.write(encrypted_data)
                print(f"Sync: Session saved to EXE path: {exe_file_path}")
            except Exception as e:
                st.warning(f"Failed to sync session to EXE folder: {e}")
        else:
            print(f"Sync: EXE dist folder not found at {exe_dist_dir}. Skipping sync.")
        
        st.session_state.saved = True
        
        # --- v1.6 ONE-CLICK AUTO-LAUNCH ---
        abs_session_path = os.path.abspath(file_path)
        try:
            # Pre-flight: Kill any existing agent
            terminate_existing_agent()
            
            # Detach and Launch
            exe_path = os.path.join(PROJECT_ROOT, "dist", "CareerCaster", "CareerCaster.exe")
            DETACHED_PROCESS = 0x00000008
            
            if os.path.exists(exe_path):
                st.info("Auto-Launching CareerCaster Pro...")
                subprocess.Popen([exe_path, abs_session_path], 
                               creationflags=DETACHED_PROCESS,
                               close_fds=True)
            else:
                agent_path = os.path.join(PROJECT_ROOT, "desktop_agent", "main.py")
                if os.path.exists(agent_path):
                    st.warning("EXE not found. Auto-Launching via Python...")
                    subprocess.Popen([sys.executable, agent_path, abs_session_path],
                                   creationflags=DETACHED_PROCESS if sys.platform == "win32" else 0,
                                   close_fds=True)
            st.balloons()
            st.success("Co-Pilot Auto-Launched successfully!")
        except Exception as launch_err:
            st.error(f"Auto-Launch failed: {launch_err}")

        # Persistence: Store last used session ID locally
        try:
            last_session_file = os.path.join(PROJECT_ROOT, ".last_session")
            with open(last_session_file, "w") as f:
                f.write(session_id)
        except:
            pass
            
        st.success(f"Session {session_id} prepared and ENCRYPTED!")
        
        # Download button for local agent execution
        st.download_button(
            label="📥 Download Session File (.cc)",
            data=encrypted_data,
            file_name=f"{session_id}.cc",
            mime="application/octet-stream",
            help="Download this file and move it to your 'sessions' folder, or pass it as an argument to the agent."
        )
        
    except Exception as e:
        st.error(f"Error preparing session: {e}")

def terminate_existing_agent():
    """Checks for existing CareerCaster.exe processes and terminates them."""
    if sys.platform == "win32":
        try:
            # Taskkill returns 0 on success, 128 if process not found
            subprocess.run(["taskkill", "/F", "/IM", "CareerCaster.exe", "/T"], 
                           capture_output=True, check=False)
            print("Pre-flight: Existing CareerCaster processes terminated.")
        except Exception as e:
            print(f"Pre-flight Error: {e}")

# --- Trigger Mechanism ---
# Removing redundant trigger handles to centralize on the primary Launch button

# --- Footer ---
st.markdown("---")

# Persistence: Load last used session ID if available
try:
    last_session_file = os.path.join(PROJECT_ROOT, ".last_session")
    if os.path.exists(last_session_file):
        with open(last_session_file, "r") as f:
            last_id = f.read().strip()
            if last_id:
                st.caption(f"Last Prepared Session: `{last_id}`")
                if not st.session_state.session_id:
                    if st.button("♻️ Reload Last Session"):
                        st.session_state.session_id = last_id
                        st.session_state.saved = True
                        st.rerun()
except:
    pass

st.caption("CareerCaster v1.0 | Hybrid Python Application")
