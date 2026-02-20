"""
AegisGraph Streamlit UI

Three-panel layout:
- Left: Chat interface with doc_id, patient_id, role, message inputs
- Right: Datadog dashboard iframe
- Admin tab: Security mode controls
"""

import streamlit as st
import requests
import os
import time
from typing import Optional

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DD_DASHBOARD_URL = os.getenv("DD_DASHBOARD_URL", "https://app.datadoghq.com/dashboard/your-dashboard-id")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_mode_check" not in st.session_state:
    st.session_state.last_mode_check = 0
if "current_mode" not in st.session_state:
    st.session_state.current_mode = "NORMAL"


def get_security_mode() -> str:
    """Poll the backend for current security mode."""
    try:
        response = requests.get(f"{BACKEND_URL}/mode", timeout=2)
        if response.status_code == 200:
            return response.json().get("mode", "NORMAL")
    except Exception:
        pass
    return st.session_state.current_mode


def set_security_mode(mode: str) -> bool:
    """Set the security mode via backend API."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/mode",
            json={"mode": mode},
            timeout=5
        )
        return response.status_code == 200
    except Exception:
        return False


def send_chat_request(doc_id: str, patient_id: str, role: str, message: str) -> dict:
    """Send chat request to backend."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={
                "doc_id": doc_id,
                "patient_id": patient_id,
                "role": role,
                "message": message,
                "user_id": doc_id,  # Using doc_id as user_id for simplicity
                "security_mode": st.session_state.current_mode
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "blocked": True,
                "reason_codes": [f"HTTP {response.status_code}"],
                "final_text": ""
            }
    except Exception as e:
        return {
            "blocked": True,
            "reason_codes": [f"Connection error: {str(e)}"],
            "final_text": ""
        }


# Page configuration
st.set_page_config(
    page_title="AegisGraph - HIPAA LLM Firewall",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Poll security mode every 5 seconds
current_time = time.time()
if current_time - st.session_state.last_mode_check > 5:
    st.session_state.current_mode = get_security_mode()
    st.session_state.last_mode_check = current_time

# STRICT_MODE banner
if st.session_state.current_mode == "STRICT_MODE":
    st.error("🚨 STRICT_MODE ENABLED")

# Main title
st.title("🛡️ AegisGraph")
st.caption("HIPAA-Aligned LLM Firewall")

# Create tabs
tab_chat, tab_admin = st.tabs(["💬 Chat", "⚙️ Admin"])

# Chat Tab
with tab_chat:
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("Clinical Chat")
        
        # Chat form
        with st.form("chat_form", clear_on_submit=False):
            doc_id = st.text_input("Doctor ID", value="D1", help="e.g., D1, D4")
            patient_id = st.text_input("Patient ID", value="P101", help="e.g., P101, P999")
            role = st.text_input("Role", value="Cardiology", help="e.g., Cardiology, ER")
            message = st.text_area("Message", height=100, placeholder="Enter your clinical query...")
            
            submitted = st.form_submit_button("Send", use_container_width=True)
            
            if submitted and message.strip():
                with st.spinner("Processing request..."):
                    result = send_chat_request(doc_id, patient_id, role, message)
                    
                    # Add to chat history
                    st.session_state.chat_history.append({
                        "doc_id": doc_id,
                        "patient_id": patient_id,
                        "role": role,
                        "message": message,
                        "result": result
                    })
        
        # Display chat history
        st.subheader("Chat History")
        
        if st.session_state.chat_history:
            for idx, entry in enumerate(reversed(st.session_state.chat_history)):
                with st.container():
                    st.markdown(f"**Request #{len(st.session_state.chat_history) - idx}**")
                    st.markdown(f"👨‍⚕️ **{entry['doc_id']}** ({entry['role']}) → 🏥 **{entry['patient_id']}**")
                    st.markdown(f"*Query:* {entry['message']}")
                    
                    result = entry["result"]
                    if result.get("blocked"):
                        st.error(f"❌ **Blocked**: {', '.join(result.get('reason_codes', ['Unknown reason']))}")
                    else:
                        st.success(f"✅ **Response**: {result.get('final_text', 'No response text')}")
                    
                    st.divider()
        else:
            st.info("No chat history yet. Submit a query to get started.")
    
    with col_right:
        st.subheader("Datadog Dashboard")
        
        # Embed Datadog dashboard
        st.components.v1.iframe(
            DD_DASHBOARD_URL,
            height=800,
            scrolling=True
        )

# Admin Tab
with tab_admin:
    st.subheader("Security Mode Control")
    
    st.markdown("""
    **Security Modes:**
    - **NORMAL**: Standard operation with full security pipeline
    - **STRICT_MODE**: Enhanced security with keyword auto-blocking
    - **LOCKDOWN**: All requests immediately refused
    """)
    
    # Display current mode
    st.info(f"Current Mode: **{st.session_state.current_mode}**")
    
    # Mode selection
    new_mode = st.radio(
        "Select Security Mode:",
        options=["NORMAL", "STRICT_MODE", "LOCKDOWN"],
        index=["NORMAL", "STRICT_MODE", "LOCKDOWN"].index(st.session_state.current_mode),
        horizontal=True
    )
    
    if st.button("Apply Mode Change", type="primary"):
        if new_mode != st.session_state.current_mode:
            with st.spinner(f"Setting mode to {new_mode}..."):
                if set_security_mode(new_mode):
                    st.session_state.current_mode = new_mode
                    st.success(f"✅ Security mode changed to **{new_mode}**")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to change security mode. Check backend connection.")
        else:
            st.info("Mode is already set to this value.")
    
    # System status
    st.divider()
    st.subheader("System Status")
    
    try:
        response = requests.get(f"{BACKEND_URL}/mode", timeout=2)
        if response.status_code == 200:
            st.success("✅ Backend connected")
        else:
            st.error("❌ Backend returned error")
    except Exception:
        st.error("❌ Backend not reachable")

# Auto-refresh for mode polling
st.markdown(
    """
    <script>
        setTimeout(function() {
            window.parent.location.reload();
        }, 5000);
    </script>
    """,
    unsafe_allow_html=True
)
