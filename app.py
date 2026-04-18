import streamlit as st
import hashlib
import time as _time
from streamlit_autorefresh import st_autorefresh
import base64
import os
import firebase_admin
from firebase_admin import credentials, db
import json

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

# ---------- SIMULATION ----------
SENSOR_INTERVAL_MINUTES = 10

def _get_simulated_state():
    interval_seconds = SENSOR_INTERVAL_MINUTES * 60
    bucket = int(_time.time() // interval_seconds)
    def _is_occupied(hash_id):
        h = int(hashlib.md5(f"{bucket}-{hash_id}".encode()).hexdigest(), 16)
        return (h % 100) < 45
    zone_a = {f"A{r}{c}": _is_occupied(f"zA{r}{c}") for r in range(1, 4) for c in range(1, 5)}
    zone_c = {f"C{r}{c}": _is_occupied(f"zC{r}{c}") for r in range(1, 5) for c in range(1, 4)}
    return zone_a, zone_c

def get_zone_b(sensor_data):
    b11 = sensor_data.get("B11", sensor_data.get("C11", False))
    b12 = sensor_data.get("B12", sensor_data.get("C12", False))
    b13 = sensor_data.get("B13", sensor_data.get("C13", False))
    return {
        "B11": b11, "B12": b12, "B13": b13,
        "B21": b11, "B22": b12, "B23": b13,
        "B31": b11, "B32": b12, "B33": b13,
    }

def _count(zone):
    total = len(zone)
    occ = sum(zone.values())
    return total - occ, occ, total

def render_live_parking():
    sensor_data = fetch_sensor_data()
    zone_a, zone_c = _get_simulated_state()
    zone_b = get_zone_b(sensor_data)

    def zone_payload(zone_dict):
        return json.dumps({k: bool(v) for k, v in zone_dict.items()})

    a_json = zone_payload(zone_a)
    b_json = zone_payload(zone_b)
    c_json = zone_payload(zone_c)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600;700&display=swap');

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
    background: transparent;
    font-family: 'Outfit', sans-serif;
    -webkit-tap-highlight-color: transparent;
    -webkit-text-size-adjust: 100%;
}}

/* ── DESKTOP ── */
.zones {{
    display: flex;
    flex-direction: row;
    gap: 12px;
    align-items: flex-start;
    width: 100%;
}}
.zone-wrap {{
    transition: flex 0.45s cubic-bezier(0.4,0,0.2,1);
    overflow: hidden;
    min-width: 0;
}}
.zone-wrap.dominant {{ flex: 3.2; }}
.zone-wrap.side {{ flex: 1; cursor: pointer; }}

.zone-card {{
    background: #0F1117;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 1rem;
    transition: border-color 0.3s, box-shadow 0.3s, opacity 0.3s;
}}
.zone-card.dominant {{
    border-color: rgba(99,102,241,0.35);
    box-shadow: 0 0 0 1px rgba(99,102,241,0.10), 0 12px 40px rgba(99,102,241,0.10);
}}
.zone-card.side {{ opacity: 0.55; }}
.zone-card.side:hover {{ opacity: 0.85; border-color: rgba(255,255,255,0.12); }}

.zone-header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 0.625rem;
}}
.zone-name {{ font-size: 0.75rem; font-weight: 800; color: #F1F2F6; letter-spacing: -0.01em; }}
.zone-desc {{ font-size: 0.58rem; color: #4B5068; letter-spacing: 0.05em; text-transform: uppercase; margin-top: 2px; }}
.zone-count {{ font-family: 'JetBrains Mono', monospace; font-size: 1rem; font-weight: 700; text-align: right; }}
.zone-count small {{ font-size: 0.62rem; color: #4B5068; font-weight: 400; }}
.zone-free-label {{ font-size: 0.58rem; color: #4B5068; margin-top: 2px; text-align: right; }}

.zone-bar-bg {{ height: 3px; background: #1E2230; border-radius: 99px; margin-bottom: 0.75rem; overflow: hidden; }}
.zone-bar-fill {{ height: 100%; border-radius: 99px; }}

.slots-row {{ display: grid; gap: 6px; margin-bottom: 6px; }}
.slot {{
    background: rgba(16,185,129,0.10);
    border: 1.5px solid rgba(16,185,129,0.35);
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 4px;
    min-height: 48px;
}}
.slot.occ {{ background: rgba(239,68,68,0.12); border-color: rgba(239,68,68,0.35); }}
.slot-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #10B981; flex-shrink: 0; }}
.slot.occ .slot-dot {{ background: #EF4444; }}
.slot-label {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    font-weight: 700;
    color: #10B981;
    display: flex;
    align-items: center;
    gap: 2px;
}}
.slot.occ .slot-label {{ color: #EF4444; }}
.live-dot {{ width: 5px; height: 5px; border-radius: 50%; background: #6366F1; display: inline-block; flex-shrink: 0; }}

.zone-footer {{
    display: flex;
    gap: 0.875rem;
    flex-wrap: wrap;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 0.62rem;
}}
.f-green {{ color: #10B981; }}
.f-red {{ color: #EF4444; }}
.f-accent {{ color: #6366F1; }}

/* ── MOBILE ── */
@media (max-width: 600px) {{
    .zones {{
        flex-direction: column;
        gap: 8px;
    }}
    .zone-wrap {{
        width: 100% !important;
        flex: none !important;
    }}

    /* Side card on mobile: compact single row tap target */
    .zone-card.side {{
        opacity: 1;
        display: flex;
        flex-direction: row;
        align-items: center;
        padding: 0.85rem 1rem;
        gap: 0;
    }}
    .zone-card.side .zone-header {{
        margin-bottom: 0;
        flex: 1;
        align-items: center;
    }}
    .zone-card.side .zone-desc {{ display: none; }}
    .zone-card.side .zone-bar-bg {{ display: none; }}
    .zone-card.side .slots-area {{ display: none; }}
    .zone-card.side .zone-footer {{ display: none; }}
    .zone-card.side .zone-name {{ font-size: 0.82rem; }}
    .zone-card.side .zone-count {{ font-size: 1.1rem; }}
    .zone-card.side .zone-free-label {{ font-size: 0.58rem; }}
    .side-arrow {{
        font-size: 1.1rem;
        color: #4B5068;
        padding-left: 0.5rem;
        flex-shrink: 0;
    }}

    /* Dominant card on mobile */
    .zone-card.dominant {{ padding: 1rem; }}
    .zone-card.dominant .zone-name {{ font-size: 0.82rem; }}
    .zone-card.dominant .zone-count {{ font-size: 1.1rem; }}
    .zone-card.dominant .slot {{ min-height: 52px; padding: 10px 4px; }}
    .zone-card.dominant .slot-dot {{ width: 9px; height: 9px; }}
    .zone-card.dominant .slot-label {{ font-size: 0.65rem; }}
    .zone-card.dominant .zone-footer {{ font-size: 0.65rem; }}
    .side-arrow {{ display: inline; }}
}}

/* Hide arrow on desktop */
@media (min-width: 601px) {{
    .side-arrow {{ display: none; }}
}}
</style>
</head>
<body>
<div class="zones" id="zones"></div>
<script>
const DATA = {{
  A: {{ dict: {a_json}, rows: 3, cols: 4, name: "Zone A", desc: "Block 3 \u00d7 4", live: [] }},
  B: {{ dict: {b_json}, rows: 3, cols: 3, name: "Zone B", desc: "Live Sensor \u00b7 3 \u00d7 3", live: ["B11","B12","B13"] }},
  C: {{ dict: {c_json}, rows: 4, cols: 3, name: "Zone C", desc: "Block 4 \u00d7 3", live: [] }}
}};

let active = sessionStorage.getItem('parkos_zone') || 'B';

function barColor(pct) {{
    return pct > 40 ? '#10B981' : pct > 15 ? '#F59E0B' : '#EF4444';
}}

function buildSlots(key, rows, cols, live) {{
    let html = '<div class="slots-area">';
    for (let r = 1; r <= rows; r++) {{
        html += '<div class="slots-row" style="grid-template-columns:repeat(' + cols + ',1fr)">';
        for (let c = 1; c <= cols; c++) {{
            const sid = key + r + c;
            const occ = DATA[key].dict[sid] || false;
            const isLive = live.includes(sid);
            html += '<div class="slot' + (occ ? ' occ' : '') + '">';
            html += '<div class="slot-dot"></div>';
            html += '<div class="slot-label">' + r + c + (isLive ? '<span class="live-dot"></span>' : '') + '</div>';
            html += '</div>';
        }}
        html += '</div>';
    }}
    html += '</div>';
    return html;
}}

function buildCard(key, isDominant) {{
    const d = DATA[key];
    const entries = Object.values(d.dict);
    const total = entries.length;
    const occ = entries.filter(Boolean).length;
    const free = total - occ;
    const pct = Math.round(free / total * 100);
    const bc = barColor(pct);
    const liveHTML = d.live.length ? '<span class="f-accent">\u25cf Live</span>' : '';
    const arrowHTML = '<span class="side-arrow">\u203a</span>';

    return '<div class="zone-card ' + (isDominant ? 'dominant' : 'side') + '">' +
        '<div class="zone-header">' +
            '<div>' +
                '<div class="zone-name">' + d.name + '</div>' +
                '<div class="zone-desc">' + d.desc + '</div>' +
            '</div>' +
            '<div>' +
                '<div class="zone-count" style="color:' + bc + '">' + free + '<small>/' + total + '</small></div>' +
                '<div class="zone-free-label">free slots</div>' +
            '</div>' +
        '</div>' +
        '<div class="zone-bar-bg"><div class="zone-bar-fill" style="width:' + pct + '%;background:' + bc + '"></div></div>' +
        (isDominant ? buildSlots(key, d.rows, d.cols, d.live) : '') +
        '<div class="zone-footer">' +
            '<span class="f-green">\ud83d\udfe2 Available (' + free + ')</span>' +
            '<span class="f-red">\ud83d\udd34 Occupied (' + occ + ')</span>' +
            liveHTML +
        '</div>' +
        (!isDominant ? arrowHTML : '') +
        '</div>';
}}

function render() {{
    const zones = document.getElementById('zones');
    zones.innerHTML = '';
    ['A', 'B', 'C'].forEach(function(key) {{
        const isDominant = key === active;
        const wrap = document.createElement('div');
        wrap.className = 'zone-wrap ' + (isDominant ? 'dominant' : 'side');
        wrap.innerHTML = buildCard(key, isDominant);
        if (!isDominant) {{
            function makeHandler(k) {{
                return function(e) {{
                    e.preventDefault();
                    active = k;
                    sessionStorage.setItem('parkos_zone', k);
                    render();
                }};
            }}
            var handler = makeHandler(key);
            wrap.addEventListener('click', handler);
            wrap.addEventListener('touchend', handler, {{ passive: false }});
        }}
        zones.appendChild(wrap);
    }});
}}

render();
</script>
</body>
</html>"""

    import streamlit.components.v1 as components
    components.html(html, height=600, scrolling=False)


# ---------- HEADER ----------
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:center;gap:1rem;padding:0.25rem 0 1rem;margin-bottom:2rem;border-bottom:1px solid rgba(255,255,255,0.06);">
    <img src="data:image/png;base64,{logo_base64}" style="width:56px;height:56px;object-fit:contain;filter:drop-shadow(0 4px 16px rgba(99,102,241,0.5)) brightness(1.1);flex-shrink:0;">
    <div>
        <div style="font-family:'Outfit',sans-serif;font-size:2.2rem;font-weight:800;color:#F1F2F6;line-height:1;letter-spacing:-0.04em;">ParkOS</div>
        <div style="font-family:'Outfit',sans-serif;font-size:0.8rem;color:#4B5068;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;margin-top:4px;">Faculty Parking Portal</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------- SUMMARY STATS ----------
sensor_data = fetch_sensor_data()
zone_a, zone_c = _get_simulated_state()
zone_b = get_zone_b(sensor_data)
all_zones = {**zone_a, **zone_b, **zone_c}
total_slots = len(all_zones)
total_free  = sum(1 for v in all_zones.values() if not v)
total_occ   = total_slots - total_free

st.markdown(f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.75rem;margin-bottom:1.5rem;">
    <div style="background:#0F1117;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1rem 1.25rem;">
        <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#4B5068;margin-bottom:0.35rem;">Total Slots</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:1.75rem;font-weight:600;color:#F1F2F6;">{total_slots}</div>
    </div>
    <div style="background:#0F1117;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1rem 1.25rem;">
        <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#4B5068;margin-bottom:0.35rem;">Available</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:1.75rem;font-weight:600;color:#10B981;">{total_free}</div>
    </div>
    <div style="background:#0F1117;border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:1rem 1.25rem;">
        <div style="font-size:0.65rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#4B5068;margin-bottom:0.35rem;">Occupied</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:1.75rem;font-weight:600;color:#EF4444;">{total_occ}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------- LIVE LABEL ----------
st.markdown('<div style="font-size:0.65rem;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#4B5068;margin-bottom:0.875rem;display:flex;align-items:center;gap:0.5rem;">Live Parking Status <span style="width:6px;height:6px;background:#10B981;border-radius:50%;display:inline-block;box-shadow:0 0 6px #10B981;"></span></div>', unsafe_allow_html=True)

# ---------- LIVE DISPLAY ----------
render_live_parking()
