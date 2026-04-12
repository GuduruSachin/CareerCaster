import streamlit as st
import uuid
import json
import os
import sys
import webbrowser
import subprocess

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

# --- Configuration & Safety ---
# Automatically create the sessions/ directory if it does not exist
SESSIONS_DIR = get_sessions_dir()

# --- Streamlit UI Setup ---
st.set_page_config(page_title="CareerCaster Dashboard", page_icon="💼")

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

# --- Sidebar: API Configuration ---
with st.sidebar:
    st.header("🔑 Configuration")
    api_key = st.text_input("Gemini API Key", type="password", help="Enter your Google Gemini API Key")
    
    if st.button("Verify Connection", use_container_width=True):
        if not api_key:
            st.error("Please enter an API Key first.")
        else:
            with st.spinner("Scanning available models..."):
                test_models = [
                    {"name": "gemini-3-flash-preview", "gen": 3},
                    {"name": "gemini-3.1-flash-lite-preview", "gen": 3},
                    {"name": "gemini-2.0-flash-exp", "gen": 2},
                    {"name": "gemini-2.5-flash", "gen": 2},
                    {"name": "gemini-1.5-flash", "gen": 1},
                    {"name": "gemini-1.5-flash-8b", "gen": 1},
                    {"name": "gemini-1.5-pro-002", "gen": 1},
                ]
                
                results = []
                test_prompt = "Hello, respond with 'OK'."
                
                for m in test_models:
                    model_name = m["name"]
                    sdk_to_use = "New (google-genai)"
                    
                    for version in ["v1", "v1beta"]:
                        start_time = time.time()
                        try:
                            client = genai.Client(api_key=api_key, http_options={'api_version': version})
                            client.models.generate_content(model=model_name, contents=test_prompt)
                            
                            latency = round(time.time() - start_time, 3)
                            results.append({
                                "name": model_name,
                                "sdk": sdk_to_use,
                                "version": version,
                                "status": "Success",
                                "latency": latency
                            })
                            break
                        except Exception as e:
                            err_msg = str(e)
                            res_status = "404" if "404" in err_msg else ("403" if "403" in err_msg else "Error")
                            if version == "v1beta" or res_status != "404":
                                results.append({
                                    "name": model_name,
                                    "sdk": sdk_to_use,
                                    "version": version,
                                    "status": res_status,
                                    "latency": round(time.time() - start_time, 3)
                                })
                
                st.session_state.scan_results = results
                success_models = [r for r in results if r["status"] == "Success"]
                if success_models:
                    st.session_state.api_verified = True
                    success_models.sort(key=lambda x: x["latency"])
                    st.session_state.active_model = success_models[0]
                    st.success(f"Verified! Fastest: {success_models[0]['name']}")
                else:
                    st.session_state.api_verified = False
                    st.error("Verification failed. Check API Key.")

    # Dynamic Advanced Settings
    if st.session_state.api_verified:
        success_models = [r for r in st.session_state.scan_results if r["status"] == "Success"]
        success_models.sort(key=lambda x: x["latency"])
        model_options = [f"{m['name']} ({m['latency']}s)" for m in success_models]
        
        with st.expander("⚙️ Advanced Settings"):
            selected_option = st.selectbox("Active Model", options=model_options, index=0)
            selected_index = model_options.index(selected_option)
            st.session_state.active_model = success_models[selected_index]
            
            preview_mode = st.toggle("Preview Mode (No AI Costs)", value=True, help="Skips Gemini API calls in the agent. Useful for testing hardware.")

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

        if st.session_state.resume_text:
            if st.button("🔍 Review Extracted Text"):
                show_text_dialog(st.session_state.resume_text)

# Job Description Text Area
jd_text = st.text_area("Paste Job Description (JD)", height=250, placeholder="Paste the full job description here...")

# --- Handshake Logic ---
can_prepare = st.session_state.api_verified and resume_file and jd_text

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
            "session_id": session_id,
            "analysis": analysis,
            "context_tags": context_tags,
            "active_model": best_model,
            "preview_mode": preview_mode
        }
        
        security = SecurityManager()
        encrypted_data = security.encrypt_data(json.dumps(session_data))
        
        file_path = os.path.join(SESSIONS_DIR, f"{session_id}.cc")
        with open(file_path, "wb") as f:
            f.write(encrypted_data)
        
        st.session_state.saved = True
        st.success(f"Session {session_id} prepared and ENCRYPTED!")
        
    except Exception as e:
        st.error(f"Error preparing session: {e}")

# --- Trigger Mechanism ---
# Only active/visible after the session JSON has been successfully saved
if st.session_state.saved and st.session_state.session_id:
    st.markdown("---")
    st.subheader("🚀 Step 2: Launch Protocol")
    
    if st.button("🔥 START INTERVIEW", type="primary"):
        session_id = st.session_state.session_id
        uri = f"careercaster://start?session_id={session_id}"
        
        # Detached Desktop Launch
        agent_path = os.path.join(PROJECT_ROOT, "desktop_agent", "main.py")
        python_exe = sys.executable.replace("python.exe", "pythonw.exe")
        
        try:
            # Creation flags for detached process on Windows
            creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen([python_exe, agent_path, uri], creationflags=creation_flags)
            st.success("Stealth Agent launched in detached mode!")
        except Exception as e:
            st.error(f"Failed to launch agent directly: {e}")
            st.info("Attempting fallback to protocol handler...")
            webbrowser.open(uri)
        
        st.balloons()

# --- Footer ---
st.markdown("---")
st.caption("CareerCaster v1.0 | Hybrid Python Application")
