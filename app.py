"""
Data Labeling Classroom App
============================
Instructor view  → main page   (?role=instructor or default)
Student view     → student page (?role=student)

Run:  streamlit run app.py
"""

import streamlit as st
import json
import os
import time
import base64
import io
import random
import string
from pathlib import Path
from PIL import Image
import qrcode
import qrcode.image.pil

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
STATE_FILE = "labeling_state.json"
UPLOADS_DIR = "uploaded_images"
DEFAULT_LABELS = ["Cat", "Dog", "Car", "Tree", "Person", "Building", "Food", "Other"]

os.makedirs(UPLOADS_DIR, exist_ok=True)

st.set_page_config(
    page_title="Data Labeling Classroom",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────
# SHARED STATE (JSON file = simple shared DB)
# ─────────────────────────────────────────────
def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return default_state()

def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def default_state() -> dict:
    return {
        "session_active": False,
        "current_image_index": 0,
        "images": [],           # list of filenames in UPLOADS_DIR
        "labels": DEFAULT_LABELS,
        "votes": {},            # {student_name: label}
        "timer_duration": 30,   # seconds
        "timer_start": None,    # epoch seconds or None
        "results_visible": False,
        "session_code": "",     # 4-char code students use
        "phase": "waiting",     # waiting | voting | results
    }

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def gen_code(n=4) -> str:
    return "".join(random.choices(string.ascii_uppercase, k=n))

def img_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def make_qr(url: str) -> str:
    """Return base64 PNG of QR code."""
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def time_left(state: dict) -> int:
    if state["timer_start"] is None:
        return state["timer_duration"]
    elapsed = time.time() - state["timer_start"]
    remaining = state["timer_duration"] - elapsed
    return max(0, int(remaining))

def count_votes(state: dict) -> dict:
    counts = {label: 0 for label in state["labels"]}
    for v in state["votes"].values():
        if v in counts:
            counts[v] += 1
    return counts

def bar_html(counts: dict) -> str:
    """Render a simple HTML bar chart."""
    total = sum(counts.values()) or 1
    max_count = max(counts.values()) if counts.values() else 1
    COLORS = [
        "#4C72B0","#DD8452","#55A868","#C44E52",
        "#8172B2","#937860","#DA8BC3","#8C8C8C",
    ]
    rows = ""
    for i, (label, count) in enumerate(counts.items()):
        pct = count / total * 100
        bar_w = count / max(max_count, 1) * 100
        color = COLORS[i % len(COLORS)]
        rows += f"""
        <tr>
          <td style="padding:6px 12px 6px 0;font-weight:600;white-space:nowrap;
                     color:#e0e0e0;font-size:1.05rem;">{label}</td>
          <td style="width:100%;padding:4px 0;">
            <div style="background:#333;border-radius:6px;overflow:hidden;height:32px;">
              <div style="width:{bar_w:.1f}%;background:{color};height:100%;
                          border-radius:6px;transition:width 0.6s ease;
                          display:flex;align-items:center;padding-left:8px;">
                <span style="color:#fff;font-weight:700;font-size:0.9rem;">
                  {count} ({pct:.0f}%)
                </span>
              </div>
            </div>
          </td>
        </tr>"""
    return f"""
    <table style="width:100%;border-collapse:collapse;">
      <tbody>{rows}</tbody>
    </table>"""

# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] {
    background: #0f1117;
    color: #e0e0e0;
  }
  .big-timer {
    font-size: 5rem;
    font-weight: 900;
    text-align: center;
    letter-spacing: 4px;
  }
  .timer-ok   { color: #4CAF50; }
  .timer-warn { color: #FF9800; }
  .timer-crit { color: #f44336; }
  .phase-badge {
    display:inline-block;
    padding: 4px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .badge-waiting { background:#444; color:#aaa; }
  .badge-voting  { background:#1565C0; color:#fff; }
  .badge-results { background:#2E7D32; color:#fff; }
  .card {
    background: #1e2130;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
  }
  .student-card {
    max-width: 560px;
    margin: 40px auto;
    background: #1e2130;
    border-radius: 16px;
    padding: 32px;
  }
  div[data-testid="stSelectbox"] label,
  div[data-testid="stTextInput"] label {
    color: #ccc !important;
    font-size: 1rem !important;
  }
  .stButton > button {
    border-radius: 8px;
    font-weight: 700;
  }
  h1,h2,h3 { color: #e8eaf6; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ROLE DETECTION  (query param  ?role=student)
# ─────────────────────────────────────────────
params = st.query_params
role = params.get("role", "instructor")

# ─────────────────────────────────────────────
# ══════════════════════════════════════════════
#  STUDENT VIEW
# ══════════════════════════════════════════════
# ─────────────────────────────────────────────
if role == "student":
    state = load_state()

    st.markdown("<h2 style='text-align:center;'>🏷️ Data Labeling Challenge</h2>", unsafe_allow_html=True)

    if not state["session_active"]:
        st.info("⏳ No active session yet. Ask your instructor to start one!")
        st.stop()

    # ── Session code check ──
    if "student_verified" not in st.session_state:
        st.session_state.student_verified = False
    if "student_name" not in st.session_state:
        st.session_state.student_name = ""

    if not st.session_state.student_verified:
        with st.container():
            st.markdown("<div class='student-card'>", unsafe_allow_html=True)
            st.markdown("### Enter Session Details")
            name = st.text_input("Your name or alias", placeholder="e.g. Alex")
            code = st.text_input("Session code (4 letters shown by instructor)",
                                 max_chars=4, placeholder="ABCD")
            if st.button("Join Session", use_container_width=True, type="primary"):
                if not name.strip():
                    st.error("Please enter your name.")
                elif code.upper() != state["session_code"]:
                    st.error("Wrong session code. Try again.")
                else:
                    st.session_state.student_verified = True
                    st.session_state.student_name = name.strip()
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # ── Student is in the session ──
    student_name = st.session_state.student_name
    state = load_state()   # fresh read

    phase = state["phase"]
    tl = time_left(state)

    # Timer display
    if phase == "voting":
        cls = "timer-ok" if tl > 15 else ("timer-warn" if tl > 5 else "timer-crit")
        st.markdown(f"<div class='big-timer {cls}'>{tl:02d}s</div>", unsafe_allow_html=True)

    # Phase badges
    badge_map = {
        "waiting": ("badge-waiting", "⏳ Waiting"),
        "voting":  ("badge-voting",  "🗳️ Vote Now!"),
        "results": ("badge-results", "✅ Results"),
    }
    bc, bl = badge_map.get(phase, ("badge-waiting",""))
    st.markdown(f"<div style='text-align:center;margin-bottom:16px;'>"
                f"<span class='phase-badge {bc}'>{bl}</span></div>",
                unsafe_allow_html=True)

    # ── Show current image ──
    images = state.get("images", [])
    idx = state.get("current_image_index", 0)
    if images and idx < len(images):
        img_path = os.path.join(UPLOADS_DIR, images[idx])
        if os.path.exists(img_path):
            col1, col2, col3 = st.columns([1,3,1])
            with col2:
                st.image(img_path, use_container_width=True,
                         caption=f"Image {idx+1} of {len(images)}")

    # ── Voting controls ──
    if phase == "voting" and tl > 0:
        already_voted = student_name in state["votes"]
        with st.container():
            st.markdown("### Your Label")
            label_choice = st.selectbox(
                "Select the label that best describes this image:",
                state["labels"],
                key="label_sel"
            )
            if already_voted:
                st.success(f"✅ You labelled this as **{state['votes'][student_name]}**. "
                           "You can change it before the timer ends.")
            if st.button("Submit Label", type="primary", use_container_width=True):
                # reload and write vote
                fresh = load_state()
                if fresh["phase"] == "voting" and time_left(fresh) > 0:
                    fresh["votes"][student_name] = label_choice
                    save_state(fresh)
                    st.success(f"✅ Labelled as **{label_choice}**!")
                    st.rerun()
                else:
                    st.warning("Voting has ended.")
    elif phase == "voting" and tl == 0:
        st.warning("⏰ Time's up! Waiting for results...")
    elif phase == "results":
        st.markdown("### Results")
        counts = count_votes(state)
        st.markdown(bar_html(counts), unsafe_allow_html=True)
        total = sum(counts.values())
        st.caption(f"{total} response(s) collected")
        if student_name in state["votes"]:
            st.info(f"Your answer: **{state['votes'][student_name]}**")
    else:
        st.info("Waiting for the instructor to start voting...")

    # Auto-refresh every 2 seconds during voting / waiting
    if phase in ("voting", "waiting"):
        time.sleep(2)
        st.rerun()

    st.stop()   # Don't render instructor UI below

# ─────────────────────────────────────────────
# ══════════════════════════════════════════════
#  INSTRUCTOR VIEW
# ══════════════════════════════════════════════
# ─────────────────────────────────────────────
state = load_state()

# ── Header ──
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
  <span style="font-size:2rem;">🏷️</span>
  <h1 style="margin:0;">Data Labeling Classroom Tool</h1>
</div>
<p style="color:#9e9e9e;margin-top:0;">
  Instructor dashboard — students join via QR code or URL
</p>
<hr style="border-color:#333;"/>
""", unsafe_allow_html=True)

tab_setup, tab_session, tab_results = st.tabs(["⚙️ Setup", "🎯 Session Control", "📊 Results"])

# ─────────────────────────────────────────────
# TAB 1 — SETUP
# ─────────────────────────────────────────────
with tab_setup:
    col_img, col_cfg = st.columns([1, 1], gap="large")

    with col_img:
        st.markdown("### 📂 Upload Images")
        uploaded = st.file_uploader(
            "Upload one or more images (JPG, PNG, WEBP)",
            type=["jpg","jpeg","png","webp","gif"],
            accept_multiple_files=True,
        )
        if uploaded:
            saved = []
            for f in uploaded:
                dst = os.path.join(UPLOADS_DIR, f.name)
                with open(dst, "wb") as out:
                    out.write(f.read())
                saved.append(f.name)
            state["images"] = saved
            state["current_image_index"] = 0
            save_state(state)
            st.success(f"✅ {len(saved)} image(s) saved.")

        current_imgs = state.get("images", [])
        if current_imgs:
            st.markdown(f"**{len(current_imgs)} image(s) loaded:**")
            thumb_cols = st.columns(min(4, len(current_imgs)))
            for i, fn in enumerate(current_imgs[:8]):
                p = os.path.join(UPLOADS_DIR, fn)
                if os.path.exists(p):
                    with thumb_cols[i % 4]:
                        st.image(p, caption=fn[:20], use_container_width=True)
            if len(current_imgs) > 8:
                st.caption(f"...and {len(current_imgs)-8} more")

    with col_cfg:
        st.markdown("### 🏷️ Label Configuration")
        labels_raw = st.text_area(
            "Labels (one per line)",
            value="\n".join(state.get("labels", DEFAULT_LABELS)),
            height=180,
        )
        new_labels = [l.strip() for l in labels_raw.strip().splitlines() if l.strip()]

        st.markdown("### ⏱️ Timer Settings")
        timer_dur = st.slider(
            "Voting duration (seconds)", 10, 300,
            value=state.get("timer_duration", 30), step=5
        )

        if st.button("💾 Save Configuration", type="primary", use_container_width=True):
            state["labels"] = new_labels
            state["timer_duration"] = timer_dur
            save_state(state)
            st.success("Configuration saved!")

# ─────────────────────────────────────────────
# TAB 2 — SESSION CONTROL
# ─────────────────────────────────────────────
with tab_session:
    state = load_state()  # fresh

    col_ctrl, col_qr = st.columns([1.6, 1], gap="large")

    with col_qr:
        st.markdown("### 📱 Student Access")
        # Build student URL
        try:
            base_url = st.get_option("browser.serverAddress") or "localhost"
            port     = st.get_option("browser.serverPort") or 8501
            student_url = f"http://{base_url}:{port}/?role=student"
        except Exception:
            student_url = "http://localhost:8501/?role=student"

        # Allow manual URL override
        custom_url = st.text_input(
            "Public URL (edit if deploying to Streamlit Cloud)",
            value=student_url,
        )
        if custom_url:
            student_url = custom_url

        qr_b64 = make_qr(student_url)
        st.markdown(
            f"<div style='text-align:center;background:#fff;padding:12px;"
            f"border-radius:12px;display:inline-block;'>"
            f"<img src='data:image/png;base64,{qr_b64}' width='200'/></div>",
            unsafe_allow_html=True,
        )
        st.code(student_url, language=None)
        st.markdown(f"**Session Code:** "
                    f"<span style='font-size:2rem;font-weight:900;letter-spacing:6px;"
                    f"color:#7986CB;'>{state.get('session_code','----')}</span>",
                    unsafe_allow_html=True)

    with col_ctrl:
        st.markdown("### 🎮 Session Control")
        phase = state.get("phase","waiting")
        badge_map = {
            "waiting": ("badge-waiting", "⏳ Waiting"),
            "voting":  ("badge-voting",  "🗳️ Voting in Progress"),
            "results": ("badge-results", "✅ Showing Results"),
        }
        bc, bl = badge_map.get(phase, ("badge-waiting",""))
        st.markdown(f"<span class='phase-badge {bc}'>{bl}</span>", unsafe_allow_html=True)

        images = state.get("images",[])
        idx    = state.get("current_image_index", 0)

        st.markdown("---")
        # Image selector
        if images:
            new_idx = st.select_slider(
                "Current Image",
                options=list(range(len(images))),
                value=min(idx, len(images)-1),
                format_func=lambda i: f"Image {i+1}: {images[i]}",
            )
            if new_idx != idx:
                state["current_image_index"] = new_idx
                state["votes"] = {}
                state["phase"] = "waiting"
                state["timer_start"] = None
                state["results_visible"] = False
                save_state(state)
                st.rerun()

            img_path = os.path.join(UPLOADS_DIR, images[idx])
            if os.path.exists(img_path):
                st.image(img_path, caption=f"Image {idx+1} of {len(images)}",
                         use_container_width=True)
        else:
            st.warning("⚠️ No images loaded. Go to the Setup tab first.")

        st.markdown("---")
        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("▶️ Start Voting", use_container_width=True, type="primary",
                         disabled=(phase == "voting" or not images)):
                state["phase"] = "voting"
                state["timer_start"] = time.time()
                state["votes"] = {}
                state["results_visible"] = False
                if not state.get("session_active"):
                    state["session_active"] = True
                    state["session_code"] = gen_code()
                save_state(state)
                st.rerun()

        with c2:
            if st.button("⏹ End & Show Results", use_container_width=True,
                         disabled=(phase == "results")):
                state["phase"] = "results"
                state["results_visible"] = True
                state["timer_start"] = None
                save_state(state)
                st.rerun()

        with c3:
            if st.button("⏭ Next Image", use_container_width=True,
                         disabled=(not images or idx >= len(images)-1)):
                state["current_image_index"] = idx + 1
                state["votes"] = {}
                state["phase"] = "waiting"
                state["timer_start"] = None
                state["results_visible"] = False
                save_state(state)
                st.rerun()

        st.markdown("---")
        if st.button("🔄 New Session (reset everything)", use_container_width=True):
            new = default_state()
            new["images"] = state["images"]
            new["labels"] = state["labels"]
            new["timer_duration"] = state["timer_duration"]
            new["session_active"] = True
            new["session_code"] = gen_code()
            save_state(new)
            st.rerun()

        # ── Live timer display ──
        if phase == "voting":
            tl = time_left(state)
            cls = "timer-ok" if tl > 15 else ("timer-warn" if tl > 5 else "timer-crit")
            st.markdown(f"<div class='big-timer {cls}'>{tl:02d}s</div>",
                        unsafe_allow_html=True)
            votes_in = len(state.get("votes", {}))
            st.caption(f"Responses received: {votes_in}")
            if tl == 0:
                state["phase"] = "results"
                state["results_visible"] = True
                save_state(state)
                st.rerun()
            else:
                time.sleep(1)
                st.rerun()

# ─────────────────────────────────────────────
# TAB 3 — RESULTS
# ─────────────────────────────────────────────
with tab_results:
    state = load_state()
    phase = state.get("phase","waiting")

    if phase == "results" or state.get("results_visible"):
        counts = count_votes(state)
        total  = sum(counts.values())

        images = state.get("images",[])
        idx    = state.get("current_image_index",0)
        if images and idx < len(images):
            img_path = os.path.join(UPLOADS_DIR, images[idx])
            if os.path.exists(img_path):
                col_img2, col_chart = st.columns([1,2], gap="large")
                with col_img2:
                    st.image(img_path, caption=f"Image {idx+1}", use_container_width=True)
                with col_chart:
                    st.markdown(f"### Label Distribution  ({total} response(s))")
                    st.markdown(bar_html(counts), unsafe_allow_html=True)
                    # Show individual responses
                    with st.expander("👤 Individual Responses"):
                        if state["votes"]:
                            for name, label in sorted(state["votes"].items()):
                                st.markdown(f"- **{name}**: {label}")
                        else:
                            st.write("No votes yet.")
            else:
                st.markdown(bar_html(counts), unsafe_allow_html=True)

        # Key insight for class discussion
        if total > 0:
            top_label = max(counts, key=counts.get)
            agreement = counts[top_label] / total * 100
            st.markdown("---")
            st.markdown("### 💡 Discussion Point")
            if agreement > 80:
                msg = (f"**High agreement!** {agreement:.0f}% of students chose "
                       f"**{top_label}**. But is that the 'correct' label? "
                       f"What assumptions did people make?")
                st.success(msg)
            elif agreement > 50:
                msg = (f"**Moderate agreement.** The most common label was "
                       f"**{top_label}** ({agreement:.0f}%). What caused the split?")
                st.info(msg)
            else:
                msg = (f"**High disagreement!** Labels were spread across "
                       f"{sum(1 for v in counts.values() if v>0)} categories. "
                       f"This illustrates the core challenge of data labeling — "
                       f"ambiguity leads to inconsistency in training data.")
                st.warning(msg)
    else:
        st.info("Results will appear here after voting ends. "
                "Use the **Session Control** tab to start a round.")
