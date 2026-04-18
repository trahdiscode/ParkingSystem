import streamlit as st
import hashlib
import time as _time
from streamlit_autorefresh import st_autorefresh
import base64
import os
import firebase_admin
from firebase_admin import credentials, db

# ---------- LOGO ----------
@st.cache_data
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

logo_base64 = get_image_base64(os.path.join(os.path.dirname(__file__), "parking_logo_flat.png"))

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="ParkOS", layout="wide", page_icon="🅿️", initial_sidebar_state="collapsed")

# ---------- AUTO REFRESH ----------
st_autorefresh(interval=10000, key="refresh")

# ---------- FIREBASE INITIALIZATION ----------
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        cred_dict = st.secrets["firebase"]
        cred = credentials.Certificate(dict(cred_dict))
        firebase_admin.initialize_app(cred, {
            'databaseURL': st.secrets["firebase"]["databaseURL"]
        })
    return db

init_firebase()

# ---------- STYLESHEET ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg: #080A0F;
    --bg-grad: radial-gradient(ellipse 80% 60% at 50% -20%, rgba(99,102,241,0.15) 0%, transparent 70%);
    --surface: #0F1117;
    --surface-2: #161923;
    --surface-3: #1E2230;
    --border: rgba(255,255,255,0.06);
    --border-hover: rgba(255,255,255,0.12);
    --text-1: #F1F2F6;
    --text-2: #9397B0;
    --text-3: #4B5068;
    --accent: #6366F1;
    --accent-2: #818CF8;
    --accent-soft: rgba(99,102,241,0.1);
    --green: #10B981;
    --green-soft: rgba(16,185,129,0.08);
    --green-border: rgba(16,185,129,0.2);
    --red: #EF4444;
    --radius: 14px;
    --radius-sm: 8px;
    --font: 'Outfit', sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; }
html, body, .stApp { background: var(--bg)!important; font-family: var(--font); color: var(--text-1); }
.stApp::before { content: ''; position: fixed; inset: 0; background: var(--bg-grad); pointer-events: none; z-index: 0; }
.main.block-container { padding: 1.5rem 1.25rem 4rem!important; max-width: 900px!important; margin: 0 auto!important; position: relative; z-index: 1; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton, div[data-testid="stDecoration"] { display: none; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: var(--border-hover); border-radius: 9999px; }
</style>
""", unsafe_allow_html=True)

# ---------- SENSOR DATA ----------
@st.cache_data(ttl=10, show_spinner=False)
def fetch_sensor_data():
    try:
        ref = db.reference("sensors")
        data = ref.get()
        if data:
            return {slot_id: val.get("is_occupied", False) for slot_id, val in data.items()}
        return {}
    except Exception:
        return {}

# ---------- SIMULATION (Zone A & B) ----------
SENSOR_INTERVAL_MINUTES = 10

def _get_simulated_state():
    interval_seconds = SENSOR_INTERVAL_MINUTES * 60
    bucket = int(_time.time() // interval_seconds)

    def _is_occupied(hash_id):
        h = int(hashlib.md5(f"{bucket}-{hash_id}".encode()).hexdigest(), 16)
        return (h % 100) < 45

    zone_a = {f"A{r}{c}": _is_occupied(f"zA{r}{c}") for r in range(1, 4) for c in range(1, 5)}
    zone_b = {f"B{r}{c}": _is_occupied(f"zB{r}{c}") for r in range(1, 5) for c in range(1, 4)}
    return zone_a, zone_b

def get_zone_c(sensor_data):
    # Real data for C11, C12, C13
    c11 = sensor_data.get("C11", False)
    c12 = sensor_data.get("C12", False)
    c13 = sensor_data.get("C13", False)

    # Duplicate across all 9 slots
    return {
        "C11": c11, "C12": c12, "C13": c13,
        "C21": c11, "C22": c12, "C23": c13,
        "C31": c11, "C32": c12, "C33": c13,
    }

# ---------- DISPLAY HELPERS ----------
def _count(zone):
    total = len(zone)
    occ = sum(zone.values())
    return total - occ, occ, total

def _slot_html(slot_id, occupied, real=False):
    color = "#EF4444" if occupied else "#10B981"
    bg = "rgba(239,68,68,0.12)" if occupied else "rgba(16,185,129,0.10)"
    border = "rgba(239,68,68,0.35)" if occupied else "rgba(16,185,129,0.35)"
    icon = "🔴" if occupied else "🟢"
    label = slot_id[1:]
    badge = "<span style='font-size:0.45rem;color:#6366F1;'>●</span>" if real else ""
    return f"""<div style="
        background:{bg};
        border:1.5px solid {border};
        border-radius:8px;
        display:flex;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        gap:3px;
        padding:6px 4px;
        min-width:0;
    ">
        <span style="font-size:0.7rem;">{icon}</span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:0.6rem;font-weight:700;color:{color};">{label}{badge}</span>
    </div>"""

def _zone_card(zone_name, zone_dict, rows, cols, description, real_slots=None):
    real_slots = real_slots or []
    free, occ, total = _count(zone_dict)
    pct_free = int(free / total * 100) if total > 0 else 0
    bar_color = "#10B981" if pct_free > 40 else ("#F59E0B" if pct_free > 15 else "#EF4444")
    slots_html = ""
    for r in range(1, rows + 1):
        slots_html += f'<div style="display:grid;grid-template-columns:repeat({cols},1fr);gap:6px;margin-bottom:6px;">'
        for c in range(1, cols + 1):
            sid = f"{zone_name[-1]}{r}{c}"
            slots_html += _slot_html(sid, zone_dict.get(sid, False), real=(sid in real_slots))
        slots_html += "</div>"
    return f"""
    <div style="background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:1rem 1rem 0.875rem; flex:1; min-width:0;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.625rem;">
            <div>
                <div style="font-size:0.75rem;font-weight:800;color:var(--text-1);letter-spacing:-0.01em;">{zone_name}</div>
                <div style="font-size:0.6rem;color:var(--text-3);letter-spacing:0.05em;text-transform:uppercase;margin-top:1px;">{description}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:1rem;font-weight:700;color:{bar_color};">{free}<span style="font-size:0.65rem;color:var(--text-3);font-weight:400;">/{total}</span></div>
                <div style="font-size:0.58rem;color:var(--text-3);">free slots</div>
            </div>
        </div>
        <div style="height:3px;background:var(--surface-3);border-radius:99px;margin-bottom:0.75rem;">
            <div style="height:100%;width:{pct_free}%;background:{bar_color};border-radius:99px;"></div>
        </div>
        {slots_html}
        <div style="display:flex;gap:0.875rem;margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid var(--border);">
            <span style="font-size:0.62rem;color:#10B981;">🟢 Available ({free})</span>
            <span style="font-size:0.62rem;color:#EF4444;">🔴 Occupied ({occ})</span>
        </div>
    </div>
    """

def render_live_parking():
    sensor_data = fetch_sensor_data()
    zone_a, zone_b = _get_simulated_state()
    zone_c = get_zone_c(sensor_data)

    # 1. Extreme width ratio so the middle column takes over the screen
    col1, col2, col3 = st.columns([1, 2.8, 1])
    
    with col1:
        # 2. Wrap Zone A to shrink its height/width and push it down
        html_a = _zone_card("Zone A", zone_a, rows=3, cols=4, description="Block 3 × 4")
        st.markdown(f'<div style="zoom: 0.75; opacity: 0.65; margin-top: 3rem;">{html_a}</div>', unsafe_allow_html=True)
        
    with col2:
        # 3. Pop Zone C out slightly to make it dominant with a glowing shadow
        html_c = _zone_card("Zone C", zone_c, rows=3, cols=3, description="Live Sensor · 3 × 3", real_slots=["C11","C12","C13"])
        st.markdown(f'<div style="transform: scale(1.02); box-shadow: 0 10px 40px rgba(99,102,241,0.15); border-radius: 14px;">{html_c}</div>', unsafe_allow_html=True)
        
    with col3:
        # 4. Wrap Zone B to shrink it and push it down
        html_b = _zone_card("Zone B", zone_b, rows=4, cols=3, description="Block 4 × 3")
        st.markdown(f'<div style="zoom: 0.75; opacity: 0.65; margin-top: 3rem;">{html_b}</div>', unsafe_allow_html=True)


# ---------- HEADER ----------
st.markdown(f"""
<div style="display:flex; align-items:center; justify-content:center; gap:1rem; padding:0.25rem 0 1rem; margin-bottom:2rem; border-bottom:1px solid var(--border);">
    <img src="data:image/png;base64,{logo_base64}" style="width:56px; height:56px; object-fit:contain; filter:drop-shadow(0 4px 16px rgba(99,102,241,0.5)) brightness(1.1); flex-shrink:0;">
    <div>
        <div style="font-family:'Outfit',sans-serif; font-size:2.2rem; font-weight:800; color:var(--text-1); line-height:1; letter-spacing:-0.04em;">ParkOS</div>
        <div style="font-family:'Outfit',sans-serif; font-size:0.8rem; color:var(--text-3); font-weight:600; letter-spacing:0.1em; text-transform:uppercase; margin-top:4px;">Faculty Parking Portal</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------- SUMMARY STATS ----------
sensor_data = fetch_sensor_data()
zone_a, zone_b = _get_simulated_state()
zone_c = get_zone_c(sensor_data)
all_zones = {**zone_a, **zone_b, **zone_c}
total_slots = len(all_zones)
total_free = sum(1 for v in all_zones.values() if not v)
total_occ = total_slots - total_free

st.markdown(f"""
<div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.75rem; margin-bottom:1.5rem;">
    <div style="background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:1rem 1.25rem;">
        <div style="font-size:0.65rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--text-3); margin-bottom:0.35rem;">Total Slots</div>
        <div style="font-family:var(--font-mono); font-size:1.75rem; font-weight:600; color:var(--text-1);">{total_slots}</div>
    </div>
    <div style="background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:1rem 1.25rem;">
        <div style="font-size:0.65rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--text-3); margin-bottom:0.35rem;">Available</div>
        <div style="font-family:var(--font-mono); font-size:1.75rem; font-weight:600; color:#10B981;">{total_free}</div>
    </div>
    <div style="background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:1rem 1.25rem;">
        <div style="font-size:0.65rem; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--text-3); margin-bottom:0.35rem;">Occupied</div>
        <div style="font-family:var(--font-mono); font-size:1.75rem; font-weight:600; color:#EF4444;">{total_occ}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------- LIVE DISPLAY ----------
st.markdown('<div style="font-size:0.65rem; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:var(--text-3); margin-bottom:0.875rem; display:flex; align-items:center; gap:0.5rem;">Live Parking Status <span style="width:6px;height:6px;background:#10B981;border-radius:50%;display:inline-block;box-shadow:0 0 6px #10B981;"></span></div>', unsafe_allow_html=True)

render_live_parking()
