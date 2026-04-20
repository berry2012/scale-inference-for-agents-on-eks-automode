import os
import requests
import streamlit as st
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Health check server for K8s probes ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"healthy")
    def log_message(self, *args):
        pass

def start_health_server():
    HTTPServer(("0.0.0.0", 8081), HealthHandler).serve_forever()

Thread(target=start_health_server, daemon=True).start()

# --- Config ---
API_URL = os.getenv("API_URL", "http://SummitAssistant:8080")

QUICK_ACTIONS = {
    "📅 Schedule Meeting": "Schedule a meeting for tomorrow at 2 PM with alice@example.com and bob@example.com. The meeting is about Q1 planning.",
    "📝 Summarize Meeting": "Please summarize and save the following meeting notes: [paste your meeting notes here]",
    "🔍 Search Meetings": "Show me all meetings from the past week with alice@example.com",
    "📝 Summarize Highlights": "Please summarize all the session highlights: [paste your notes from the Summit sessions here]",    
}

WELCOME = (
    "Hello! I'm **SummitAssistant**, your AI-powered AWS Summit activity management assistant.\n\n"
    "I can help you with:\n"
    "- 📅 Schedule meetings in Google Calendar\n"
    "- 📝 Summarize and save meeting notes\n"
    "- 🔍 Search and retrieve past meetings\n\n"
    "- 📝 Summarize sessions highlights\n\n"    
    "How can I assist you today?"
)

# --- Page setup ---
st.set_page_config(page_title="SummitAssistant Chat", page_icon="💬", layout="centered")

# --- AWS Summit London Theme CSS ---
st.markdown("""
<style>
    /* Header gradient bar */
    .stApp > header {
        background: linear-gradient(123deg, #fa6f00, #e433ff 50%, #8575ff) !important;
    }

    /* Main title gradient text */
    .summit-header {
        background: linear-gradient(90deg, #fa6f00, #e433ff 50%, #8575ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #141f2e 0%, #1a2940 100%);
        border-right: 1px solid #2a3f5f;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: #fa6f00 !important;
    }

    /* Sidebar buttons - gradient border effect */
    section[data-testid="stSidebar"] button {
        background: #232f3e !important;
        color: #e8e8e8 !important;
        border: 1px solid #3a4f6f !important;
        transition: all 0.3s ease !important;
    }
    section[data-testid="stSidebar"] button:hover {
        border-color: #fa6f00 !important;
        box-shadow: 0 0 12px rgba(250, 111, 0, 0.3) !important;
    }

    /* Chat input styling */
    .stChatInput > div {
        border-color: #3a4f6f !important;
    }
    .stChatInput > div:focus-within {
        border-color: #fa6f00 !important;
        box-shadow: 0 0 8px rgba(250, 111, 0, 0.25) !important;
    }

    /* User chat bubble */
    .stChatMessage[data-testid="stChatMessage"]:has(.stMarkdown) {
        border-radius: 12px;
    }
    div[data-testid="stChatMessage"]:nth-of-type(even) {
        background: linear-gradient(135deg, #1a2940, #232f3e) !important;
    }

    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .status-connected {
        background: rgba(40, 167, 69, 0.15);
        color: #28a745;
        border: 1px solid rgba(40, 167, 69, 0.3);
    }
    .status-disconnected {
        background: rgba(220, 53, 69, 0.15);
        color: #dc3545;
        border: 1px solid rgba(220, 53, 69, 0.3);
    }

    /* Divider */
    .gradient-divider {
        height: 2px;
        background: linear-gradient(90deg, #fa6f00, #e433ff 50%, #8575ff);
        border: none;
        margin: 0.5rem 0 1rem 0;
        border-radius: 1px;
    }

    /* Links */
    a { color: #fa6f00 !important; }
    a:hover { color: #e433ff !important; }

    /* Spinner */
    .stSpinner > div > div {
        border-top-color: #fa6f00 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Connection status ---
@st.cache_data(ttl=30, show_spinner=False)
def check_health():
    try:
        r = requests.get(f"{API_URL}/health", timeout=5)
        return r.ok
    except Exception:
        return False

connected = check_health()

# --- Header ---
status_cls = "status-connected" if connected else "status-disconnected"
status_txt = "● Connected" if connected else "● Disconnected"
st.markdown('<p class="summit-header">💬 SummitAssistant</p>', unsafe_allow_html=True)
st.markdown('<div class="gradient-divider"></div>', unsafe_allow_html=True)
st.markdown(f'<span class="status-badge {status_cls}">{status_txt}</span>', unsafe_allow_html=True)

# --- Session state ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": WELCOME}]

# --- Render chat history ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Quick actions in sidebar ---
st.sidebar.markdown("## ⚡ Quick Actions")
for label, template in QUICK_ACTIONS.items():
    if st.sidebar.button(label, use_container_width=True):
        st.session_state["prefill"] = template
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("AWS London Summit 2026 · Scale Inference Demo  · AWS Village")

# --- Chat input ---
prefill = st.session_state.get("prefill", "")

if prefill:
    # Show editable text area with prefilled template
    user_input = st.text_area("✏️ Edit your message and click Send:", value=prefill, max_chars=2000, height=120, key="edit_area")
    col1, col2 = st.columns([1, 5])
    send = col1.button("🚀 Send", use_container_width=True)
    if col2.button("✕ Cancel", use_container_width=True):
        del st.session_state["prefill"]
        st.rerun()
    if send and user_input.strip():
        del st.session_state["prefill"]
    else:
        user_input = None
else:
    user_input = st.chat_input("Type your message here...", max_chars=2000)

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                r = requests.post(
                    f"{API_URL}/chat",
                    json={"message": user_input},
                    timeout=60,
                )
                r.raise_for_status()
                reply = r.json().get("response", "Sorry, I got an empty response.")
            except Exception as e:
                reply = f"I'm having trouble connecting to the server. Error: {e}"
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
