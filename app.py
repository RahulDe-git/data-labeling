"""
Data Labeling Classroom App
============================
Single-file Streamlit app. Uses st.session_state as the shared store.

Instructor: open the app normally
Student:    open ?role=student  (or scan QR code)

IMPORTANT FOR STREAMLIT CLOUD:
- State is stored in Streamlit's session_state, which is per-browser-session.
- To share state between instructor and students on the same server, we use
  a simple workaround: write a JSON file to the app's working directory.
  Streamlit Community Cloud DOES allow writes to the working directory at runtime
  (they are ephemeral — lost on restart, but fine for a class session).
"""

import streamlit as st
import json, os, time, base64, io, random, string
from PIL import Image
import qrcode

# ── Page config (must be first Streamlit call) ──────────────────────────────
st.set_page_config(
    page_title="Data Labeling Classroom",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ────────────────────────────────────────────────────────────────
STATE_FILE   = "labeling_state.json"
UPLOADS_DIR  = "uploaded_images"
DEFAULT_LABELS = ["Cat", "Dog", "Car", "Tree", "Person", "Building", "Food", "Other"]

os.makedirs(UPLOADS_DIR, exist_ok=True)

# ── Shared state helpers (JSON file as simple DB) ────────────────────────────
def default_state():
    return {
        "session_active": False,
        "session_code": "",
        "phase": "waiting",          # waiting | voting | results
        "images": [],                # list of saved filenames
        "labels": DEFAULT_LABELS,
        "timer_duration": 30,
        "timer_start": None,
        "current_image_index": 0,
        "votes": {},                 # {student_name: label}
        "results_visible": False,
    }

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return default_state()

def save_state(s):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except Exception as e:
        st.error(f"Could not save state: {e}")

# ── Utility functions ────────────────────────────────────────────────────────
def gen_code():
    return "".join(random.choices(string.ascii_uppercase, k=4))

def time_left(s):
    if s["timer_start"] is None:
        return s["timer_duration"]
    return max(0, int(s["timer_duration"] - (time.time() - s["timer_start"])))

def vote_counts(s):
    counts = {lbl: 0 for lbl in s["labels"]}
    for v in s["votes"].values():
        if v in counts:
            counts[v] += 1
    return counts

def make_qr_b64(url):
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def bar_chart_html(counts):
    total    = sum(counts.values()) or 1
    max_cnt  = max(counts.values()) if any(counts.values()) else 1
    COLORS   = ["#4C72B0","#DD8452","#55A868","#C44E52",
                 "#8172B2","#937860","#DA8BC3","#8C8C8C"]
    rows = ""
    for i, (lbl, cnt) in enumerate(counts.items()):
        pct   = cnt / total * 100
        bar_w = cnt / max_cnt * 100
        col   = COLORS[i % len(COLORS)]
        rows += f"""
        <tr>
          <td style="padding:5px 12px 5px 0;font-weight:600;white-space:nowrap;
                     color:#ddd;font-size:1rem;min-width:90px;">{lbl}</td>
          <td style="width:100%;padding:4px 0;">
            <div style="background:#2a2a3a;border-radius:6px;overflow:hidden;height:30px;">
              <div style="width:{bar_w:.1f}%;background:{col};height:100%;border-radius:6px;
                          display:flex;align-items:center;padding-left:8px;
                          transition:width 0.5s ease;">
                <span style="color:#fff;font-weight:700;font-size:0.85rem;white-space:nowrap;">
                  {cnt} &nbsp;({pct:.0f}%)
                </span>
              </div>
            </div>
          </td>
        </tr>"""
    return f"<table style='width:100%;border-collapse:collapse;'><tbody>{rows}</tbody></table>"

# ── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Dark background */
  [data-testid="stAppViewContainer"] { background:#0f1117; }
  [data-testid="stHeader"]           { background:#0f1117; }
  /* Big countdown */
  .big-timer { font-size:5rem; font-weight:900; text-align:center; letter-spacing:4px; }
  .tok   { color:#4CAF50; }
  .twarn { color:#FF9800; }
  .tcrit { color:#f44336; }
  /* Phase badge */
  .badge { display:inline-block; padding:4px 16px; border-radius:20px;
           font-size:0.8rem; font-weight:700; letter-spacing:1px; text-transform:uppercase; }
  .bwait { background:#444; color:#aaa; }
  .bvote { background:#1565C0; color:#fff; }
  .bres  { background:#2E7D32; color:#fff; }
  /* Cards */
  .card  { background:#1e2130; border-radius:12px; padding:20px 24px; margin-bottom:16px; }
  /* Student layout */
  .s-wrap { max-width:520px; margin:30px auto; }
  h1,h2,h3 { color:#e8eaf6 !important; }
  p, li, label { color:#ccc; }
  /* Tabs */
  button[data-baseweb="tab"] { color:#aaa !important; }
  button[data-baseweb="tab"][aria-selected="true"] { color:#fff !important; }
</style>
""", unsafe_allow_html=True)

# ── Role detection via query param ───────────────────────────────────────────
role = st.query_params.get("role", "instructor")

# ════════════════════════════════════════════════════════════════════════════
#  STUDENT VIEW
# ════════════════════════════════════════════════════════════════════════════
if role == "student":

    st.markdown("<div class='s-wrap'>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;'>🏷️ Data Labeling Challenge</h2>",
                unsafe_allow_html=True)

    # ── Local session-state init ──
    for k, v in [("verified", False), ("sname", ""), ("last_vote", "")]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Read shared state ──
    s = load_state()

    if not s["session_active"]:
        st.info("⏳ Waiting for the instructor to start a session…")
        time.sleep(3)
        st.rerun()

    # ── Login form ──
    if not st.session_state.verified:
        st.markdown("### Join Session")
        name = st.text_input("Your name or alias", placeholder="e.g. Alex")
        code = st.text_input("4-letter session code (shown by instructor)",
                             max_chars=4, placeholder="ABCD")
        if st.button("Join →", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Please enter your name.")
            elif code.upper().strip() != s["session_code"]:
                st.error("Wrong session code — check with your instructor.")
            else:
                st.session_state.verified = True
                st.session_state.sname    = name.strip()
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # ── Student is logged in ──
    sname = st.session_state.sname
    s = load_state()   # fresh read
    phase = s["phase"]
    tl    = time_left(s)

    # ── Phase badge ──
    badge = {"waiting":("bwait","⏳ Waiting"),
             "voting": ("bvote","🗳️ Vote Now!"),
             "results":("bres", "✅ Results")}
    bc, bl = badge.get(phase, ("bwait","…"))
    st.markdown(f"<p style='text-align:center;'><span class='badge {bc}'>{bl}</span></p>",
                unsafe_allow_html=True)

    # ── Timer ──
    if phase == "voting":
        cls = "tok" if tl > 15 else ("twarn" if tl > 5 else "tcrit")
        st.markdown(f"<div class='big-timer {cls}'>{tl:02d}s</div>", unsafe_allow_html=True)

    # ── Current image ──
    imgs = s.get("images", [])
    idx  = s.get("current_image_index", 0)
    if imgs and idx < len(imgs):
        p = os.path.join(UPLOADS_DIR, imgs[idx])
        if os.path.exists(p):
            st.image(p, use_container_width=True,
                     caption=f"Image {idx+1} of {len(imgs)}")

    # ── Voting ──
    if phase == "voting" and tl > 0:
        already = s["votes"].get(sname)
        chosen = st.selectbox(
            "Select the label that best describes this image:",
            s["labels"],
            index=s["labels"].index(already) if already in s["labels"] else 0,
        )
        if already:
            st.caption(f"✅ Current answer: **{already}** — you can still change it.")
        if st.button("Submit Label", type="primary", use_container_width=True):
            fresh = load_state()
            if fresh["phase"] == "voting" and time_left(fresh) > 0:
                fresh["votes"][sname] = chosen
                save_state(fresh)
                st.session_state.last_vote = chosen
                st.success(f"Submitted: **{chosen}**")
                st.rerun()
            else:
                st.warning("Voting has already ended.")
    elif phase == "voting" and tl == 0:
        st.warning("⏰ Time's up! Waiting for results…")
    elif phase == "results":
        st.markdown("### Results")
        counts = vote_counts(s)
        st.markdown(bar_chart_html(counts), unsafe_allow_html=True)
        total = sum(counts.values())
        st.caption(f"{total} response(s) total")
        if sname in s["votes"]:
            st.info(f"Your answer: **{s['votes'][sname]}**")
    elif phase == "waiting":
        st.info("Waiting for the instructor to open voting…")

    st.markdown("</div>", unsafe_allow_html=True)

    # Auto-refresh
    if phase in ("waiting", "voting"):
        time.sleep(2)
        st.rerun()

    st.stop()  # ← prevents any instructor code from rendering below


# ════════════════════════════════════════════════════════════════════════════
#  INSTRUCTOR VIEW
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
  <span style="font-size:2rem;">🏷️</span>
  <h1 style="margin:0;">Data Labeling Classroom</h1>
</div>
<p style="color:#777;margin-top:0;margin-bottom:16px;">Instructor Dashboard</p>
<hr style="border-color:#333;margin-bottom:0;"/>
""", unsafe_allow_html=True)

tab_setup, tab_ctrl, tab_results = st.tabs(["⚙️ Setup", "🎯 Session Control", "📊 Results"])

# ─── TAB 1 · SETUP ──────────────────────────────────────────────────────────
with tab_setup:
    s = load_state()
    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("### 📂 Upload Images")
        uploads = st.file_uploader(
            "JPG / PNG / WEBP — upload one or more images",
            type=["jpg","jpeg","png","webp"],
            accept_multiple_files=True,
        )
        if uploads:
            saved = []
            for f in uploads:
                dst = os.path.join(UPLOADS_DIR, f.name)
                with open(dst, "wb") as out:
                    out.write(f.read())
                saved.append(f.name)
            s["images"] = saved
            s["current_image_index"] = 0
            s["votes"] = {}
            s["phase"] = "waiting"
            save_state(s)
            st.success(f"✅ {len(saved)} image(s) uploaded.")

        imgs = s.get("images", [])
        if imgs:
            st.markdown(f"**{len(imgs)} image(s) loaded**")
            cols = st.columns(min(4, len(imgs)))
            for i, fn in enumerate(imgs[:8]):
                p = os.path.join(UPLOADS_DIR, fn)
                if os.path.exists(p):
                    with cols[i % 4]:
                        st.image(p, caption=fn[:18], use_container_width=True)
            if len(imgs) > 8:
                st.caption(f"…and {len(imgs)-8} more")

    with c2:
        st.markdown("### 🏷️ Labels")
        raw = st.text_area(
            "One label per line",
            value="\n".join(s.get("labels", DEFAULT_LABELS)),
            height=200,
        )
        new_labels = [l.strip() for l in raw.splitlines() if l.strip()]

        st.markdown("### ⏱️ Timer")
        dur = st.slider("Voting duration (seconds)", 10, 300,
                        value=s.get("timer_duration", 30), step=5)

        if st.button("💾 Save Configuration", type="primary", use_container_width=True):
            s["labels"]         = new_labels
            s["timer_duration"] = dur
            save_state(s)
            st.success("Saved!")

# ─── TAB 2 · SESSION CONTROL ─────────────────────────────────────────────────
with tab_ctrl:
    s = load_state()
    col_ctrl, col_qr = st.columns([1.6, 1], gap="large")

    # ── QR / student link ──
    with col_qr:
        st.markdown("### 📱 Student Access")

        # Detect deployed URL automatically, allow override
        default_url = "http://localhost:8501/?role=student"
        try:
            addr = st.get_option("browser.serverAddress") or "localhost"
            port = st.get_option("browser.serverPort") or 8501
            default_url = f"http://{addr}:{port}/?role=student"
        except Exception:
            pass

        student_url = st.text_input(
            "Student URL (update with your Streamlit Cloud URL)",
            value=default_url,
            key="student_url_input",
        )

        qr_b64 = make_qr_b64(student_url)
        st.markdown(
            f"<div style='background:#fff;padding:10px;border-radius:10px;"
            f"display:inline-block;margin-bottom:8px;'>"
            f"<img src='data:image/png;base64,{qr_b64}' width='190'/></div>",
            unsafe_allow_html=True,
        )
        st.code(student_url, language=None)

        code = s.get("session_code", "----")
        st.markdown(
            f"<p style='margin-top:8px;'>Session Code: "
            f"<span style='font-size:2.2rem;font-weight:900;letter-spacing:8px;"
            f"color:#7986CB;'>{code}</span></p>",
            unsafe_allow_html=True,
        )

    # ── Controls ──
    with col_ctrl:
        st.markdown("### 🎮 Controls")
        phase = s.get("phase", "waiting")
        badge = {"waiting":("bwait","⏳ Waiting"),
                 "voting": ("bvote","🗳️ Voting in Progress"),
                 "results":("bres", "✅ Showing Results")}
        bc, bl = badge.get(phase, ("bwait","…"))
        st.markdown(f"<span class='badge {bc}'>{bl}</span>", unsafe_allow_html=True)

        imgs = s.get("images", [])
        idx  = s.get("current_image_index", 0)
        st.markdown("---")

        if imgs:
            # Image picker
            new_idx = st.select_slider(
                "Current image",
                options=list(range(len(imgs))),
                value=min(idx, len(imgs)-1),
                format_func=lambda i: f"{i+1}: {imgs[i]}",
            )
            if new_idx != idx:
                s["current_image_index"] = new_idx
                s["votes"] = {}
                s["phase"] = "waiting"
                s["timer_start"] = None
                save_state(s)
                st.rerun()

            p = os.path.join(UPLOADS_DIR, imgs[idx])
            if os.path.exists(p):
                st.image(p, caption=f"Image {idx+1} / {len(imgs)}",
                         use_container_width=True)
        else:
            st.warning("No images loaded — go to Setup first.")

        st.markdown("---")
        b1, b2, b3 = st.columns(3)

        with b1:
            start_disabled = (phase == "voting") or (not imgs)
            if st.button("▶️ Start Voting", use_container_width=True,
                         type="primary", disabled=start_disabled):
                if not s.get("session_active"):
                    s["session_active"] = True
                    s["session_code"]   = gen_code()
                s["phase"]        = "voting"
                s["timer_start"]  = time.time()
                s["votes"]        = {}
                s["results_visible"] = False
                save_state(s)
                st.rerun()

        with b2:
            if st.button("⏹ End Voting", use_container_width=True,
                         disabled=(phase == "results")):
                s["phase"]           = "results"
                s["results_visible"] = True
                s["timer_start"]     = None
                save_state(s)
                st.rerun()

        with b3:
            if st.button("⏭ Next Image", use_container_width=True,
                         disabled=(not imgs or idx >= len(imgs)-1)):
                s["current_image_index"] = idx + 1
                s["votes"]     = {}
                s["phase"]     = "waiting"
                s["timer_start"] = None
                save_state(s)
                st.rerun()

        st.markdown("---")
        if st.button("🔄 New Session", use_container_width=True):
            ns = default_state()
            ns["images"]         = s["images"]
            ns["labels"]         = s["labels"]
            ns["timer_duration"] = s["timer_duration"]
            ns["session_active"] = True
            ns["session_code"]   = gen_code()
            save_state(ns)
            st.rerun()

        # ── Live countdown ──
        if phase == "voting":
            tl  = time_left(s)
            cls = "tok" if tl > 15 else ("twarn" if tl > 5 else "tcrit")
            st.markdown(f"<div class='big-timer {cls}'>{tl:02d}s</div>",
                        unsafe_allow_html=True)
            st.caption(f"Responses so far: {len(s.get('votes', {}))}")
            if tl == 0:
                s["phase"]           = "results"
                s["results_visible"] = True
                save_state(s)
                st.rerun()
            else:
                time.sleep(1)
                st.rerun()

# ─── TAB 3 · RESULTS ─────────────────────────────────────────────────────────
with tab_results:
    s = load_state()

    if s.get("results_visible") or s["phase"] == "results":
        counts = vote_counts(s)
        total  = sum(counts.values())

        imgs = s.get("images", [])
        idx  = s.get("current_image_index", 0)

        ri, rc = st.columns([1, 2], gap="large")
        with ri:
            if imgs and idx < len(imgs):
                p = os.path.join(UPLOADS_DIR, imgs[idx])
                if os.path.exists(p):
                    st.image(p, caption=f"Image {idx+1}", use_container_width=True)

        with rc:
            st.markdown(f"### Label Distribution — {total} response(s)")
            if total == 0:
                st.info("No votes were submitted.")
            else:
                st.markdown(bar_chart_html(counts), unsafe_allow_html=True)

            with st.expander("👤 Individual responses"):
                if s["votes"]:
                    for nm, lbl in sorted(s["votes"].items()):
                        st.markdown(f"- **{nm}**: {lbl}")
                else:
                    st.write("None yet.")

        # Discussion prompt
        if total > 0:
            top   = max(counts, key=counts.get)
            agree = counts[top] / total * 100
            st.markdown("---")
            st.markdown("### 💡 Discussion Prompt")
            if agree > 80:
                st.success(
                    f"**High agreement** — {agree:.0f}% chose **{top}**. "
                    "Is this the 'correct' label? What assumptions did students make? "
                    "Would a different label set change results?"
                )
            elif agree > 50:
                st.info(
                    f"**Moderate agreement** — top label was **{top}** ({agree:.0f}%). "
                    "What caused the split? Were the label definitions clear enough?"
                )
            else:
                n_cats = sum(1 for v in counts.values() if v > 0)
                st.warning(
                    f"**High disagreement** — votes spread across {n_cats} labels. "
                    "This is the core challenge of data labeling: without clear guidelines, "
                    "annotators diverge, introducing noise into training data."
                )
    else:
        st.info("Results will appear here once voting ends.")
