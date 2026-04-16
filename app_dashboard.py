"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              CHOCOBERRY INTELLIGENCE — MERGED APPLICATION                   ║
║         Dashboard (Streamlit) + Labour Cost Report (Excel)                  ║
║                        Jan 2026 – Apr 2026                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Run dashboard:   streamlit run app_dashboard.py
Generate Excel:  python app_dashboard.py --report
"""

import sys
import os
import logging
import re as _re
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import datetime as dt_module
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from pathlib import Path   
import sqlite3
import streamlit as st
st.set_page_config(
    page_title="Chocoberry Intelligence",
    layout="wide",
    page_icon="🍫",
    initial_sidebar_state="expanded",
)

from dotenv import load_dotenv
load_dotenv()

# Import the sync logic directly
try:
    from sync_portal_invoices import sync_from_portal
except ImportError:
    sync_from_portal = None

# ══════════════════════════════════════════════════════════════════════════════
# ██  AUTHENTICATION SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

def check_password():
    """Returns True if the user had the correct password."""
    import base64

    if st.session_state.get("password_correct", False):
        return True

    def get_base64_bin_file(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        valid_pass = None
        
        # 1. Try to get password from Streamlit Cloud Secrets
        try:
            if "DASHBOARD_PASSWORD" in st.secrets:
                valid_pass = st.secrets["DASHBOARD_PASSWORD"]
        except Exception:
            pass

        # 2. Try to get password from Environment Variables (Local)
        if not valid_pass:
            valid_pass = os.environ.get("DASHBOARD_PASSWORD")

        # 3. Verify
        # Get input and strip spaces
        user_input = str(st.session_state["password_input"]).strip()
        actual_pass = str(valid_pass).strip() if valid_pass else None

        if actual_pass and user_input == actual_pass:
            st.session_state["password_correct"] = True
            del st.session_state["password_input"]
        else:
            st.session_state["password_correct"] = False

    # ── BEAUTIFUL LOGIN UI (ALWAYS SHOW IF NOT LOGGED IN) ──────────────────
    bg_img = ""
    if os.path.exists("login_banner.png"):
        bg_img = get_base64_bin_file("login_banner.png")

    st.markdown(f"""
        <style>
        .stApp {{
            background: linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.4)), 
                        url("data:image/png;base64,{bg_img}");
            background-size: cover;
            background-position: top center;
            background-attachment: fixed;
        }}
        .login-wrapper {{
            text-align: center;
            margin-top: 35vh;
            padding: 20px;
        }}
        .login-title {{
            font-family: 'Syne', sans-serif;
            font-size: 26px;
            font-weight: 800;
            color: #f5a623;
            letter-spacing: 2px;
            margin-bottom: 5px;
            text-shadow: 2px 2px 10px rgba(0,0,0,0.9);
        }}
        .login-sub {{
            font-size: 11px;
            color: #ffffff;
            text-transform: uppercase;
            letter-spacing: 4px;
            margin-bottom: 40px;
            text-shadow: 1px 1px 5px rgba(0,0,0,0.9);
            opacity: 0.9;
        }}
        .stTextInput {{
            max-width: 400px;
            margin: 0 auto;
        }}
        .stTextInput label {{
            font-weight: 900 !important;
            color: #f5a623 !important;
            font-size: 16px !important;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-bottom: 8px;
            display: block;
        }}
        div[data-baseweb="input"] {{
            background: rgba(0,0,0,0.6) !important;
            border: 1px solid rgba(245, 166, 35, 0.5) !important;
            border-radius: 12px !important;
            backdrop-filter: blur(10px);
        }}
        input {{
            color: white !important;
            text-align: center !important;
        }}
        header, [data-testid="stSidebar"] {{
            visibility: hidden;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">CHOCOBERRY BUSINESS INTELLIGENCE SYSTEM</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">FINANCIAL COMMAND CENTRE</div>', unsafe_allow_html=True)
    
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.text_input("ENTER PASSWORD", type="password", on_change=password_entered, key="password_input", placeholder="••••••••")
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.markdown('<p style="color:#ff4b4b; font-size:12px; margin-top:10px; font-weight:bold">ACCESS DENIED — UNAUTHORIZED ATTEMPT</p>', unsafe_allow_html=True)

    st.markdown('<p style="margin-top:100px; font-size:10px; color:rgba(255,255,255,0.4); letter-spacing:2px">RESTRICTED ACCESS — AUTHORIZED PERSONNEL ONLY</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    return False

if not check_password():
    st.stop()


def parse_time_range(time_str):
    parts = _re.split(r'[-–]', str(time_str).replace(' ', ''))
    if len(parts) != 2:
        return []
    try:
        sh, sm = map(int, parts[0].split(':'))
        eh, em = map(int, parts[1].split(':'))
    except Exception:
        return []
    start_dec = sh + sm / 60
    end_dec   = eh + em / 60
    if end_dec <= start_dec:
        end_dec += 24
    hours = []
    h_dec = float(sh)
    while h_dec < end_dec and h_dec < start_dec + 24:
        if start_dec < h_dec + 1.0 and end_dec > h_dec:
            hours.append(int(h_dec) % 24)
        h_dec += 1.0
    return hours

def format_hour_ampm(h_int):
    """Converts 21 to '9:00 PM' and 0 to '12:00 AM'."""
    h = h_int % 24
    suffix = "AM" if h < 12 else "PM"
    h_12 = h % 12
    if h_12 == 0: h_12 = 12
    return f"{h_12}:00 {suffix}"

# ── Integration Patch Imports ─────────────────────────────────────────────────
try:
    from recipe_engine import RecipeEngine, DB_PATH as RECIPE_DB_PATH
    _recipe_engine = RecipeEngine()
except ImportError:
    _recipe_engine = None
    RECIPE_DB_PATH = "recipes.db"

try:
    from weekly_pdf_report import generate_weekly_pdf
    _pdf_available = True
except ImportError:
    _pdf_available = False


# ══════════════════════════════════════════════════════════════════════════════
# ██  SECTION 1 — SHARED CONSTANTS & DATA
# ══════════════════════════════════════════════════════════════════════════════

from invoice_db import InvoiceDB
inv_db = InvoiceDB()

# Calculate dynamic week label
_now = datetime.now()
_start_of_week = _now - timedelta(days=_now.weekday())
_end_of_week = _start_of_week + timedelta(days=6)
WEEK_LABEL = f"{_start_of_week.strftime('%d %b')} – {_end_of_week.strftime('%d %b %Y')}"

LABOUR_THRESHOLD        = 0.30   # 30% flag
UNDERSTAFFING_THRESHOLD = 300    # £/hr daily avg revenue — needs full team
OVERSTAFFING_THRESHOLD  = 20     # £/hr daily avg revenue — too many staff

SBY_STAFF = {
    "Munira":   {"max_sby_hrs": 4, "hourly_rate": 6.00},  # matches CSV £6
    "Bhoomika": {"max_sby_hrs": 4, "hourly_rate": 6.00},  # matches CSV £6
    "Dhiraj":   {"max_sby_hrs": 4, "hourly_rate": 9.00},  # matches CSV £9
}


# ── Daily Sales (91 days) ─────────────────────────────────────────────────────

DAILY_DATA = [
    {"date":"2026-01-01","label":"01 Jan","day":"Thursday",  "net":5218.42,"orders":321,"revenue":5345.13,"tax":126.71,"refunds":0.0,  "rolling7":5218.42},
    {"date":"2026-01-02","label":"02 Jan","day":"Friday",    "net":2442.13,"orders":162,"revenue":2568.47,"tax":118.8, "refunds":0.0,  "rolling7":3830.28},
    {"date":"2026-01-03","label":"03 Jan","day":"Saturday",  "net":2925.06,"orders":217,"revenue":3057.82,"tax":121.36,"refunds":0.0,  "rolling7":3528.54},
    {"date":"2026-01-04","label":"04 Jan","day":"Sunday",    "net":3690.21,"orders":229,"revenue":3858.86,"tax":161.79,"refunds":0.0,  "rolling7":3568.95},
    {"date":"2026-01-05","label":"05 Jan","day":"Monday",    "net":1629.71,"orders":112,"revenue":1703.16,"tax":70.38, "refunds":0.0,  "rolling7":3181.11},
    {"date":"2026-01-06","label":"06 Jan","day":"Tuesday",   "net":1633.21,"orders":103,"revenue":1693.06,"tax":59.85, "refunds":0.0,  "rolling7":2923.12},
    {"date":"2026-01-07","label":"07 Jan","day":"Wednesday", "net":2023.36,"orders":134,"revenue":2114.93,"tax":75.54, "refunds":0.0,  "rolling7":2794.59},
    {"date":"2026-01-08","label":"08 Jan","day":"Thursday",  "net":1593.06,"orders":109,"revenue":1644.92,"tax":45.46, "refunds":0.0,  "rolling7":2276.68},
    {"date":"2026-01-09","label":"09 Jan","day":"Friday",    "net":2780.58,"orders":194,"revenue":2886.44,"tax":105.86,"refunds":0.0,  "rolling7":2325.03},
    {"date":"2026-01-10","label":"10 Jan","day":"Saturday",  "net":2615.66,"orders":189,"revenue":2734.38,"tax":115.18,"refunds":0.0,  "rolling7":2280.83},
    {"date":"2026-01-11","label":"11 Jan","day":"Sunday",    "net":2702.4, "orders":177,"revenue":2812.15,"tax":109.75,"refunds":0.0,  "rolling7":2139.71},
    {"date":"2026-01-12","label":"12 Jan","day":"Monday",    "net":1939.04,"orders":120,"revenue":2029.65,"tax":90.61, "refunds":0.0,  "rolling7":2183.9},
    {"date":"2026-01-13","label":"13 Jan","day":"Tuesday",   "net":2361.77,"orders":161,"revenue":2485.89,"tax":104.53,"refunds":0.0,  "rolling7":2287.98},
    {"date":"2026-01-14","label":"14 Jan","day":"Wednesday", "net":1808.49,"orders":122,"revenue":1885.35,"tax":73.25, "refunds":0.0,  "rolling7":2257.29},
    {"date":"2026-01-15","label":"15 Jan","day":"Thursday",  "net":2214.01,"orders":165,"revenue":2318.5, "tax":104.49,"refunds":0.0,  "rolling7":2345.99},
    {"date":"2026-01-16","label":"16 Jan","day":"Friday",    "net":2745.0, "orders":190,"revenue":2837.76,"tax":92.76, "refunds":0.0,  "rolling7":2340.91},
    {"date":"2026-01-17","label":"17 Jan","day":"Saturday",  "net":3003.35,"orders":222,"revenue":3132.82,"tax":129.47,"refunds":0.0,  "rolling7":2396.29},
    {"date":"2026-01-18","label":"18 Jan","day":"Sunday",    "net":3027.84,"orders":200,"revenue":3152.64,"tax":124.8, "refunds":0.0,  "rolling7":2442.79},
    {"date":"2026-01-19","label":"19 Jan","day":"Monday",    "net":1939.73,"orders":136,"revenue":2018.49,"tax":78.76, "refunds":0.0,  "rolling7":2442.88},
    {"date":"2026-01-20","label":"20 Jan","day":"Tuesday",   "net":2206.58,"orders":140,"revenue":2296.37,"tax":79.66, "refunds":0.0,  "rolling7":2420.71},
    {"date":"2026-01-21","label":"21 Jan","day":"Wednesday", "net":1955.7, "orders":144,"revenue":2035.51,"tax":77.27, "refunds":0.0,  "rolling7":2441.74},
    {"date":"2026-01-22","label":"22 Jan","day":"Thursday",  "net":1941.86,"orders":139,"revenue":2008.55,"tax":55.35, "refunds":0.0,  "rolling7":2402.87},
    {"date":"2026-01-23","label":"23 Jan","day":"Friday",    "net":3077.0, "orders":208,"revenue":3182.7, "tax":105.7, "refunds":0.0,  "rolling7":2450.29},
    {"date":"2026-01-24","label":"24 Jan","day":"Saturday",  "net":3425.0, "orders":216,"revenue":3549.52,"tax":124.52,"refunds":0.0,  "rolling7":2510.53},
    {"date":"2026-01-25","label":"25 Jan","day":"Sunday",    "net":3511.11,"orders":241,"revenue":3610.83,"tax":99.22, "refunds":0.0,  "rolling7":2579.57},
    {"date":"2026-01-26","label":"26 Jan","day":"Monday",    "net":1947.63,"orders":125,"revenue":2025.87,"tax":78.24, "refunds":0.0,  "rolling7":2580.7},
    {"date":"2026-01-27","label":"27 Jan","day":"Tuesday",   "net":1788.84,"orders":143,"revenue":1864.92,"tax":73.37, "refunds":0.0,  "rolling7":2521.02},
    {"date":"2026-01-28","label":"28 Jan","day":"Wednesday", "net":2402.72,"orders":153,"revenue":2514.59,"tax":111.88,"refunds":0.0,  "rolling7":2584.88},
    {"date":"2026-01-29","label":"29 Jan","day":"Thursday",  "net":1968.01,"orders":134,"revenue":2078.58,"tax":101.98,"refunds":0.0,  "rolling7":2588.62},
    {"date":"2026-01-30","label":"30 Jan","day":"Friday",    "net":2880.35,"orders":186,"revenue":2993.91,"tax":100.81,"refunds":0.0,  "rolling7":2560.52},
    {"date":"2026-01-31","label":"31 Jan","day":"Saturday",  "net":3825.62,"orders":244,"revenue":3983.5, "tax":144.49,"refunds":0.0,  "rolling7":2617.75},
    {"date":"2026-02-01","label":"01 Feb","day":"Sunday",    "net":3224.11,"orders":212,"revenue":3351.81,"tax":117.68,"refunds":0.0,  "rolling7":2576.75},
    {"date":"2026-02-02","label":"02 Feb","day":"Monday",    "net":2167.89,"orders":160,"revenue":2279.6, "tax":100.1, "refunds":0.0,  "rolling7":2608.22},
    {"date":"2026-02-03","label":"03 Feb","day":"Tuesday",   "net":2325.2, "orders":143,"revenue":2420.6, "tax":90.86, "refunds":0.0,  "rolling7":2684.84},
    {"date":"2026-02-04","label":"04 Feb","day":"Wednesday", "net":2058.73,"orders":143,"revenue":2158.28,"tax":85.85, "refunds":0.0,  "rolling7":2635.7},
    {"date":"2026-02-05","label":"05 Feb","day":"Thursday",  "net":2036.35,"orders":138,"revenue":2117.87,"tax":75.74, "refunds":0.0,  "rolling7":2645.46},
    {"date":"2026-02-06","label":"06 Feb","day":"Friday",    "net":3421.16,"orders":219,"revenue":3533.42,"tax":108.53,"refunds":0.0,  "rolling7":2722.72},
    {"date":"2026-02-07","label":"07 Feb","day":"Saturday",  "net":3002.72,"orders":224,"revenue":3123.13,"tax":109.92,"refunds":0.0,  "rolling7":2605.17},
    {"date":"2026-02-08","label":"08 Feb","day":"Sunday",    "net":3379.13,"orders":207,"revenue":3521.07,"tax":141.94,"refunds":0.0,  "rolling7":2627.31},
    {"date":"2026-02-09","label":"09 Feb","day":"Monday",    "net":1931.47,"orders":135,"revenue":2024.51,"tax":87.23, "refunds":0.0,  "rolling7":2593.54},
    {"date":"2026-02-10","label":"10 Feb","day":"Tuesday",   "net":2314.9, "orders":158,"revenue":2437.44,"tax":89.69, "refunds":0.0,  "rolling7":2592.07},
    {"date":"2026-02-11","label":"11 Feb","day":"Wednesday", "net":2198.34,"orders":146,"revenue":2285.52,"tax":80.7,  "refunds":0.0,  "rolling7":2612.01},
    {"date":"2026-02-12","label":"12 Feb","day":"Thursday",  "net":2073.6, "orders":151,"revenue":2147.36,"tax":73.76, "refunds":0.0,  "rolling7":2617.33},
    {"date":"2026-02-13","label":"13 Feb","day":"Friday",    "net":2855.32,"orders":200,"revenue":2997.14,"tax":128.9, "refunds":8.5,  "rolling7":2536.5},
    {"date":"2026-02-14","label":"14 Feb","day":"Saturday",  "net":4068.76,"orders":277,"revenue":4243.85,"tax":159.19,"refunds":0.0,  "rolling7":2688.79},
    {"date":"2026-02-15","label":"15 Feb","day":"Sunday",    "net":4118.7, "orders":259,"revenue":4305.48,"tax":177.37,"refunds":0.0,  "rolling7":2794.44},
    {"date":"2026-02-16","label":"16 Feb","day":"Monday",    "net":2805.67,"orders":181,"revenue":2946.24,"tax":132.56,"refunds":0.0,  "rolling7":2919.33},
    {"date":"2026-02-17","label":"17 Feb","day":"Tuesday",   "net":2952.82,"orders":198,"revenue":3106.83,"tax":154.01,"refunds":0.0,  "rolling7":3010.46},
    {"date":"2026-02-18","label":"18 Feb","day":"Wednesday", "net":2505.41,"orders":163,"revenue":2603.57,"tax":98.16, "refunds":0.0,  "rolling7":3054.33},
    {"date":"2026-02-19","label":"19 Feb","day":"Thursday",  "net":2378.08,"orders":162,"revenue":2451.72,"tax":73.64, "refunds":0.0,  "rolling7":3097.82},
    {"date":"2026-02-20","label":"20 Feb","day":"Friday",    "net":2857.67,"orders":197,"revenue":2937.9, "tax":80.23, "refunds":0.0,  "rolling7":3098.16},
    {"date":"2026-02-21","label":"21 Feb","day":"Saturday",  "net":3004.84,"orders":201,"revenue":3098.06,"tax":85.3,  "refunds":0.0,  "rolling7":2946.17},
    {"date":"2026-02-22","label":"22 Feb","day":"Sunday",    "net":3114.74,"orders":214,"revenue":3201.83,"tax":69.15, "refunds":0.0,  "rolling7":2802.75},
    {"date":"2026-02-23","label":"23 Feb","day":"Monday",    "net":2065.74,"orders":133,"revenue":2143.65,"tax":77.91, "refunds":0.0,  "rolling7":2697.04},
    {"date":"2026-02-24","label":"24 Feb","day":"Tuesday",   "net":2072.35,"orders":148,"revenue":2164.55,"tax":85.04, "refunds":0.0,  "rolling7":2571.26},
    {"date":"2026-02-25","label":"25 Feb","day":"Wednesday", "net":2326.49,"orders":185,"revenue":2405.64,"tax":79.15, "refunds":0.0,  "rolling7":2545.7},
    {"date":"2026-02-26","label":"26 Feb","day":"Thursday",  "net":2105.8, "orders":157,"revenue":2190.96,"tax":74.91, "refunds":10.25,"rolling7":2506.8},
    {"date":"2026-02-27","label":"27 Feb","day":"Friday",    "net":3012.8, "orders":205,"revenue":3109.85,"tax":97.05, "refunds":0.0,  "rolling7":2528.97},
    {"date":"2026-02-28","label":"28 Feb","day":"Saturday",  "net":3820.58,"orders":257,"revenue":3937.94,"tax":122.38,"refunds":0.0,  "rolling7":2645.5},
    {"date":"2026-03-01","label":"01 Mar","day":"Sunday",    "net":3776.45,"orders":255,"revenue":3880.34,"tax":100.12,"refunds":0.0,  "rolling7":2740.03},
    {"date":"2026-03-02","label":"02 Mar","day":"Monday",    "net":2183.65,"orders":161,"revenue":2258.07,"tax":71.81, "refunds":0.0,  "rolling7":2756.87},
    {"date":"2026-03-03","label":"03 Mar","day":"Tuesday",   "net":2388.9, "orders":170,"revenue":2474.73,"tax":78.55, "refunds":0.0,  "rolling7":2802.1},
    {"date":"2026-03-04","label":"04 Mar","day":"Wednesday", "net":2153.17,"orders":156,"revenue":2211.95,"tax":58.78, "refunds":0.0,  "rolling7":2777.34},
    {"date":"2026-03-05","label":"05 Mar","day":"Thursday",  "net":2473.78,"orders":189,"revenue":2558.44,"tax":79.18, "refunds":0.0,  "rolling7":2829.9},
    {"date":"2026-03-06","label":"06 Mar","day":"Friday",    "net":2492.26,"orders":204,"revenue":2555.31,"tax":63.05, "refunds":0.0,  "rolling7":2755.54},
    {"date":"2026-03-07","label":"07 Mar","day":"Saturday",  "net":3280.24,"orders":242,"revenue":3354.23,"tax":64.64, "refunds":0.0,  "rolling7":2678.35},
    {"date":"2026-03-08","label":"08 Mar","day":"Sunday",    "net":3532.74,"orders":225,"revenue":3622.64,"tax":87.79, "refunds":0.0,  "rolling7":2643.53},
    {"date":"2026-03-09","label":"09 Mar","day":"Monday",    "net":2688.14,"orders":186,"revenue":2762.62,"tax":74.48, "refunds":0.0,  "rolling7":2715.6},
    {"date":"2026-03-10","label":"10 Mar","day":"Tuesday",   "net":2429.5, "orders":150,"revenue":2544.68,"tax":88.63, "refunds":0.0,  "rolling7":2721.4},
    {"date":"2026-03-11","label":"11 Mar","day":"Wednesday", "net":2237.36,"orders":161,"revenue":2323.18,"tax":78.93, "refunds":0.0,  "rolling7":2733.43},
    {"date":"2026-03-12","label":"12 Mar","day":"Thursday",  "net":2212.21,"orders":145,"revenue":2297.8, "tax":82.35, "refunds":0.0,  "rolling7":2696.06},
    {"date":"2026-03-13","label":"13 Mar","day":"Friday",    "net":3131.92,"orders":219,"revenue":3246.58,"tax":114.66,"refunds":0.0,  "rolling7":2787.44},
    {"date":"2026-03-14","label":"14 Mar","day":"Saturday",  "net":2834.07,"orders":216,"revenue":2941.77,"tax":93.14, "refunds":0.0,  "rolling7":2723.71},
    {"date":"2026-03-15","label":"15 Mar","day":"Sunday",    "net":3757.79,"orders":248,"revenue":3896.49,"tax":124.84,"refunds":0.0,  "rolling7":2755.86},
    {"date":"2026-03-16","label":"16 Mar","day":"Monday",    "net":2072.84,"orders":157,"revenue":2135.18,"tax":62.34, "refunds":0.0,  "rolling7":2667.96},
    {"date":"2026-03-17","label":"17 Mar","day":"Tuesday",   "net":2351.2, "orders":158,"revenue":2447.42,"tax":84.26, "refunds":0.0,  "rolling7":2656.77},
    {"date":"2026-03-18","label":"18 Mar","day":"Wednesday", "net":2203.3, "orders":176,"revenue":2278.59,"tax":64.7,  "refunds":0.0,  "rolling7":2651.9},
    {"date":"2026-03-19","label":"19 Mar","day":"Thursday",  "net":2018.95,"orders":142,"revenue":2101.01,"tax":75.85, "refunds":6.0,  "rolling7":2624.3},
    {"date":"2026-03-20","label":"20 Mar","day":"Friday",    "net":4193.47,"orders":321,"revenue":4340.21,"tax":136.7, "refunds":0.0,  "rolling7":2775.95},
    {"date":"2026-03-21","label":"21 Mar","day":"Saturday",  "net":4644.38,"orders":323,"revenue":4836.61,"tax":182.23,"refunds":10.0, "rolling7":3034.56},
    {"date":"2026-03-22","label":"22 Mar","day":"Sunday",    "net":3648.79,"orders":240,"revenue":3843.51,"tax":170.42,"refunds":5.5,  "rolling7":3018.99},
    {"date":"2026-03-23","label":"23 Mar","day":"Monday",    "net":1728.88,"orders":118,"revenue":1822.34,"tax":93.46, "refunds":0.0,  "rolling7":2969.85},
    {"date":"2026-03-24","label":"24 Mar","day":"Tuesday",   "net":2153.63,"orders":136,"revenue":2251.7, "tax":98.07, "refunds":0.0,  "rolling7":2941.63},
    {"date":"2026-03-25","label":"25 Mar","day":"Wednesday", "net":1506.73,"orders":104,"revenue":1564.49,"tax":57.76, "refunds":0.0,  "rolling7":2842.12},
    {"date":"2026-03-26","label":"26 Mar","day":"Thursday",  "net":1630.87,"orders":111,"revenue":1694.76,"tax":60.29, "refunds":0.0,  "rolling7":2786.68},
    {"date":"2026-03-27","label":"27 Mar","day":"Friday",    "net":2291.34,"orders":166,"revenue":2413.62,"tax":111.25,"refunds":0.0,  "rolling7":2514.95},
    {"date":"2026-03-28","label":"28 Mar","day":"Saturday",  "net":2750.21,"orders":198,"revenue":2873.55,"tax":102.76,"refunds":0.0,  "rolling7":2244.35},
    {"date":"2026-03-29","label":"29 Mar","day":"Sunday",    "net":3508.68,"orders":220,"revenue":3622.8, "tax":114.12,"refunds":0.0,  "rolling7":2224.33},
    {"date":"2026-03-30","label":"30 Mar","day":"Monday",    "net":2142.66,"orders":139,"revenue":2252.33,"tax":109.67,"refunds":0.0,  "rolling7":2283.45},
    {"date":"2026-03-31","label":"31 Mar","day":"Tuesday",   "net":2590.23,"orders":162,"revenue":2693.75,"tax":99.99, "refunds":0.0,  "rolling7":2345.82},
    {"date":"2026-04-01","label":"01 Apr","day":"Wednesday", "net":2160.24,"orders":145,"revenue":2278.51,"tax":103.81,"refunds":7.5,  "rolling7":2439.18},
    {"date":"2026-04-02","label":"02 Apr","day":"Thursday",  "net":2488.5, "orders":151,"revenue":2575.94,"tax":87.44, "refunds":0.0,  "rolling7":2558.05},
    {"date":"2026-04-03","label":"03 Apr","day":"Friday",    "net":2703.06,"orders":177,"revenue":2804.37,"tax":84.67, "refunds":0.0,  "rolling7":2616.87},
    {"date":"2026-04-04","label":"04 Apr","day":"Saturday",  "net":3020.78,"orders":197,"revenue":3121.88,"tax":101.10,"refunds":0.0,  "rolling7":2655.52},
    {"date":"2026-04-05","label":"05 Apr","day":"Sunday",    "net":4373.81,"orders":268,"revenue":4557.93,"tax":170.40,"refunds":0.0,  "rolling7":2779.11},
    {"date":"2026-04-06","label":"06 Apr","day":"Monday",    "net":2816.47,"orders":197,"revenue":2953.64,"tax":116.08,"refunds":8.5,  "rolling7":2875.37},
    {"date":"2026-04-07","label":"07 Apr","day":"Tuesday",   "net":2195.79,"orders":135,"revenue":2327.65,"tax":115.13,"refunds":0.0,  "rolling7":2819.02},
    {"date":"2026-04-08","label":"08 Apr","day":"Wednesday", "net":2421.34,"orders":171,"revenue":2520.78,"tax":93.94, "refunds":5.5,  "rolling7":2859.96},
    {"date":"2026-04-09","label":"09 Apr","day":"Thursday",  "net":2403.16,"orders":176,"revenue":2511.78,"tax":108.62,"refunds":0.0,  "rolling7":2847.77},
    {"date":"2026-04-10","label":"10 Apr","day":"Friday",    "net":2795.04,"orders":188,"revenue":2898.72,"tax":103.68,"refunds":0.0,  "rolling7":2860.91},
    {"date":"2026-04-11","label":"11 Apr","day":"Saturday",  "net":3446.30,"orders":222,"revenue":3566.70,"tax":120.40,"refunds":0.0,  "rolling7":2921.70},
    {"date":"2026-04-12","label":"12 Apr","day":"Sunday",    "net":3582.86,"orders":220,"revenue":3722.64,"tax":139.78,"refunds":0.0,  "rolling7":2808.71},

]

# ── Weekly summaries ──────────────────────────────────────────────────────────

WEEKLY_DATA = [
    {"week":"29 Dec","net":14275.82,"orders":985, "tax":285.16},
    {"week":"05 Jan","net":14977.98,"orders":1033,"tax":299.56},
    {"week":"12 Jan","net":17099.5, "orders":1169,"tax":341.99},
    {"week":"19 Jan","net":18056.98,"orders":1238,"tax":361.14},
    {"week":"26 Jan","net":18037.28,"orders":1237,"tax":360.75},
    {"week":"02 Feb","net":18391.18,"orders":1261,"tax":367.82},
    {"week":"09 Feb","net":19561.09,"orders":1341,"tax":391.22},
    {"week":"16 Feb","net":19619.23,"orders":1345,"tax":392.38},
    {"week":"23 Feb","net":19180.21,"orders":1315,"tax":383.60},
    {"week":"02 Mar","net":18504.74,"orders":1269,"tax":370.09},
    {"week":"09 Mar","net":19290.99,"orders":1323,"tax":385.82},
    {"week":"16 Mar","net":21132.93,"orders":1449,"tax":422.66},
    {"week":"23 Mar","net":15570.34,"orders":1067,"tax":311.41},
    {"week":"30 Mar","net":19454.19,"orders":1301,"tax":520.46},
    {"week":"06 Apr","net":19661.42,"orders":1303,"tax":599.63},

]

# ── Channel / dispatch / payment data ────────────────────────────────────────

CHANNEL_DATA = {
    # Updated: Jan 1 – Apr 13 2026 (103 trading days) from net_sales_by_sales_channel.csv
    "POS (In-Store)":  169228.60,
    "Uber Eats":        67821.49,
    "Deliveroo":        32588.87,
    "Just Eat":          2465.79,
    "Web (Flipdish)":     630.47,
}

DISPATCH_DATA = {
    # Updated: Jan 1 – Apr 13 2026 (103 trading days) from net_sales_by_dispatch_type.csv
    "Delivery":   {"revenue": 100330.79, "orders": 6873},
    "Dine In":    {"revenue":  90169.39, "orders": 6177},
    "Take Away":  {"revenue":  72366.38, "orders": 4960},
    "Collection": {"revenue":  10016.82, "orders":  550},
}

PAYMENT_DATA = {
    # Updated: Jan 1 – Apr 13 2026 (103 trading days) from net_sales_by_payment_method.csv
    "Credit Card": 133168.29,
    "Paid Online": 103654.79,
    "Cash":         32661.69,
    "Mix":           2713.20,
    "Unpaid":          685.42,
}

# ── Hourly data (91-day totals) ───────────────────────────────────────────────

HOURLY_DATA = {
    "00:00": 18606.96, "01:00":  4925.09, "02:00":  1710.26, "03:00":    17.20,
    "04:00":     0.00, "05:00":     0.00, "06:00":     0.00, "07:00":     0.00,
    "08:00":     0.00, "09:00":    34.86, "10:00":   260.24, "11:00":   706.49,
    "12:00":  3604.52, "13:00":  4495.56, "14:00":  5225.56, "15:00":  5099.38,
    "16:00":  6496.33, "17:00":  9685.77, "18:00": 17564.17, "19:00": 30166.44,
    "20:00": 35952.63, "21:00": 37477.92, "22:00": 32565.99, "23:00": 26144.93,
}

# Keyed by integer hour for labour calculations
HOURLY_TOTAL = {
     0: 18606.96,  1:  4925.09,  2:  1710.26,  3:    17.20,
     9:    34.86, 10:   260.24, 11:   706.49, 12:  3604.52,
    13:  4495.56, 14:  5225.56, 15:  5099.38, 16:  6496.33,
    17:  9685.77, 18: 17564.17, 19: 30166.44, 20: 35952.63,
    21: 37477.92, 22: 32565.99, 23: 26144.93,
}
HOURLY_AVG = {h: round(v / 102, 2) for h, v in HOURLY_TOTAL.items()}

# ── Forecast ──────────────────────────────────────────────────────────────────

FORECAST_DATA = {
    "Monday":    2158.13,
    "Tuesday":   2381.14,
    "Wednesday": 2026.91,
    "Thursday":  1954.01,
    "Friday":    3205.58,
    "Saturday":  3409.55,
    "Sunday":    3638.42,
}
WEEK_FORECAST_TOTAL = sum(FORECAST_DATA.values())

FORECAST_HISTORY = {
    "Week of 9 Mar":  {"forecast": 18800.0,             "actual": 19290.99},
    "Week of 16 Mar": {"forecast": 19100.0,             "actual": 21132.93},
    "Week of 23 Mar": {"forecast": 20500.0,             "actual": 15570.34},
    "Week of 30 Mar": {"forecast": 18900.0,             "actual": 19454.19},
    "Week of 6 Apr":  {"forecast": WEEK_FORECAST_TOTAL, "actual": 19661.42},
    "Week of 13 Apr": {"forecast": WEEK_FORECAST_TOTAL, "actual": None},
}


# ══════════════════════════════════════════════════════════════════════════════
# ██  SECTION 2 — LABOUR REPORT CALCULATIONS
# ══════════════════════════════════════════════════════════════════════════════

def calc_staff_wages(data):
    if "personnel" not in data: return pd.DataFrame()
    rows = []
    for name, p in data["personnel"].items():
        actual_hrs = 0
        if data["shifts"]:
            actual_hrs = len([s for s in data["shifts"] if s["name"].upper() == name.upper()])

        # Case-insensitive key handling
        p_lower = {k.lower(): v for k, v in p.items()}
        ni_h = p_lower.get("ni hours", 0)
        ni_r = p_lower.get("ni rates", 0)
        hr_r = p_lower.get("hourly rate", 0)
        fw   = p_lower.get("fixed wage", 0)

        if fw > 0 and actual_hrs > 0:
            wage = fw
        elif actual_hrs <= ni_h:
            wage = actual_hrs * ni_r
        else:
            wage = (ni_h * ni_r) + ((actual_hrs - ni_h) * hr_r)

        wage = round(wage, 2)
        rows.append({
            "Name":             name,
            "Hours Worked":     actual_hrs,
            "NI Limit (hrs)":   ni_h,
            "NI Rate (£)":      f"£{ni_r:.2f}",
            "Std Rate (£)":     f"£{hr_r:.2f}",
            "Weekly Wage (£)":  wage,
            "Status":           "Fixed" if fw > 0 else ("Tiered" if ni_h > 0 else "Standard"),
        })
    return pd.DataFrame(rows).sort_values("Weekly Wage (£)", ascending=False)


def calc_labour_summary(staff_df, forecast_rev=0):
    if staff_df.empty:
        return {"Staff Wages Total":0, "Other Costs Total":0, "Total Labour Cost":0, "Labour % of Revenue":0, "SBY Max Additional Cost":0, "Forecast Week Revenue": forecast_rev}

    staff_wages  = staff_df["Weekly Wage (£)"].sum()
    # Dynamic loading of Fixed Costs from CSV
    fixed_path = os.path.join(os.getcwd(), "fixed_weekly_costs.csv")
    if os.path.exists(fixed_path):
        fdf = pd.read_csv(fixed_path)
        other_total = fdf["Amount"].sum()
    else:
        other_total = 665.0  # fallback
    total_labour = staff_wages + other_total
    labour_pct   = (total_labour / forecast_rev * 100) if forecast_rev > 0 else 0

    return {
        "Staff Wages Total":           round(staff_wages, 2),
        "Other Costs Total":           round(other_total, 2),
        "Total Labour Cost":           round(total_labour, 2),
        "Forecast Week Revenue":       round(forecast_rev, 2),
        "Labour % of Revenue":         round(labour_pct, 1),
        "Flag (>30%)":                 "🔴 OVER THRESHOLD" if labour_pct > 30 else "✅ WITHIN TARGET",
        "SBY Max Additional Cost":     255.0,
        "Total Max Labour (incl SBY)": round(total_labour + 255.0, 2),
        "Max Labour % (incl SBY)":     round((total_labour + 255.0) / (forecast_rev if forecast_rev > 0 else 1) * 100, 1),
    }


def calc_hourly_overlay(live_hourly_dict=None, data=None):
    rows = []
    h_data_source = live_hourly_dict if live_hourly_dict else {h: round(v/91,2) for h,v in HOURLY_TOTAL.items()}

    all_hours = range(24)
    dyn_staff_count = {}
    dyn_sby_count   = {}
    for h in all_hours:
        dyn_staff_count[h] = 0
        dyn_sby_count[h]   = 0

    if data and data.get("shifts"):
        for s in data["shifts"]:
            h_int = s["hour"]
            if s.get("is_sby"):
                dyn_sby_count[h_int] += 1
            else:
                dyn_staff_count[h_int] += 1

    for h in all_hours:
        revenue    = h_data_source.get(h, 0)
        conf_staff = round(dyn_staff_count[h] / 7, 1)
        sby_staff  = round(dyn_sby_count[h] / 7, 1)
        total_staff = conf_staff + sby_staff

        avg_rate = 11.44
        if data and "personnel" in data:
            rates = [float(p.get("Hourly Rate", 0)) for p in data["personnel"].values()]
            if rates: avg_rate = sum(rates) / len(rates)

        conf_cost  = round((conf_staff  * avg_rate) / 7, 2)
        sby_cost   = round((sby_staff   * avg_rate) / 7, 2)
        total_cost = conf_cost + sby_cost

        rev_per_staff = round(revenue / total_staff, 2) if total_staff > 0 else 0
        cost_ratio    = round(total_cost / revenue * 100, 2) if revenue > 0 else 999

        if revenue <= OVERSTAFFING_THRESHOLD and conf_staff > 2:
            flag = "🔴 OVERSTAFFED"
        elif revenue >= UNDERSTAFFING_THRESHOLD and total_staff < 6:
            flag = "🟡 UNDERSTAFFED"
        elif revenue >= UNDERSTAFFING_THRESHOLD and total_staff >= 6:
            flag = "✅ Well Covered"
        elif conf_staff == 0:
            flag = "⚪ No Staff / Closed"
        else:
            flag = "✅ OK"

        period = (
            "🔴 Dead"      if h in [3,4,5,6,7,8,9]  else
            "🟡 Morning"   if h in [10,11,12]         else
            "🟡 Afternoon" if h in [13,14,15,16]      else
            "🟠 Evening"   if h in [17,18]             else
            "🔥 Peak"      if h in [19,20,21,22,23]   else
            "🌙 Late Night"
        )

        rows.append({
            "Hour":                 f"{h:02d}:00",
            "Period":               period,
            "Avg Revenue (£)":      revenue,
            "Confirmed Staff":      conf_staff,
            "SBY Staff":            sby_staff,
            "Total Staff":          total_staff,
            "Confirmed Cost (£)":   conf_cost,
            "SBY Cost (£)":         sby_cost,
            "Total Staff Cost (£)": total_cost,
            "Revenue/Staff/Hr (£)": rev_per_staff,
            "Staff Cost % of Rev":  f"{cost_ratio:.1f}%",
            "Flag":                 flag,
        })
    return pd.DataFrame(rows)


def calc_overstaffing(overlay_df):
    return overlay_df[overlay_df["Flag"] == "🔴 OVERSTAFFED"][[
        "Hour", "Period", "Avg Revenue (£)", "Total Staff", "Total Staff Cost (£)", "Flag"
    ]].copy()


def calc_understaffing(overlay_df):
    return overlay_df[overlay_df["Flag"] == "🟡 UNDERSTAFFED"][[
        "Hour", "Period", "Avg Revenue (£)", "Total Staff", "Total Staff Cost (£)", "Flag"
    ]].copy()


def calc_day_labour(total_wages=None):
    """Distribute weekly wage cost across days proportional to forecast revenue.
    total_wages: pass live staff wage total from calc_staff_wages(); defaults to forecast-based estimate.
    """
    rows = []
    # Use live wages if provided, else estimate from Labour % target (28% of forecast)
    total_labour = total_wages if (total_wages and total_wages > 0) else round(WEEK_FORECAST_TOTAL * 0.28, 2)
    for day, day_revenue in FORECAST_DATA.items():
        day_share  = day_revenue / WEEK_FORECAST_TOTAL
        day_labour = round(total_labour * day_share, 2)
        day_pct    = round(day_labour / day_revenue * 100, 2)
        sby_flag   = (
            "Call SBY by 19:00" if day_revenue >= 3000 else
            "Monitor at 18:00"  if day_revenue >= 2300 else
            "No SBY needed"
        )
        rows.append({
            "Day":                  day,
            "Forecast Revenue (£)": day_revenue,
            "Est. Labour Cost (£)": day_labour,
            "Labour % of Revenue":  f"{day_pct:.1f}%",
            "Status":               "🔴 Over" if day_pct > 30 else "✅ OK",
            "SBY Recommendation":   sby_flag,
        })
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# ██  SECTION 3 — EXCEL HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _apply_header(ws, row, cols, fill_hex="1a1d26", font_hex="F5A623"):
    fill = PatternFill("solid", fgColor=fill_hex)
    font = Font(bold=True, color=font_hex, name="Arial", size=10)
    for col in range(1, cols + 1):
        c = ws.cell(row=row, column=col)
        c.fill = fill
        c.font = font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _apply_data_row(ws, row, cols, alt=False):
    fill = PatternFill("solid", fgColor="1E2130" if alt else "14161F")
    font = Font(color="E0E0E0", name="Arial", size=9)
    for col in range(1, cols + 1):
        c = ws.cell(row=row, column=col)
        c.fill = fill
        c.font = font
        c.alignment = Alignment(horizontal="center", vertical="center")


def _flag_cell(ws, row, col, value):
    c = ws.cell(row=row, column=col, value=value)
    if "🔴" in str(value):
        c.font = Font(color="FF4444", bold=True, name="Arial", size=9)
    elif "🟡" in str(value):
        c.font = Font(color="FFA500", bold=True, name="Arial", size=9)
    elif "✅" in str(value):
        c.font = Font(color="3ECF8E", bold=True, name="Arial", size=9)
    else:
        c.font = Font(color="E0E0E0", name="Arial", size=9)
    c.alignment = Alignment(horizontal="center", vertical="center")


def _set_col_widths(ws, widths):
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w


def _title_cell(ws, row, col, text, span_end=None):
    c = ws.cell(row=row, column=col, value=text)
    c.font = Font(bold=True, color="F5A623", name="Arial", size=13)
    c.fill = PatternFill("solid", fgColor="0D0F14")
    c.alignment = Alignment(horizontal="left", vertical="center")
    if span_end:
        ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=span_end)


def _write_df(ws, df, start_row=3, title=None, title_span=None):
    """Write DataFrame with styled header + alternating rows. Returns next free row."""
    if title:
        _title_cell(ws, start_row - 1, 1, title, title_span)

    cols = list(df.columns)
    n = len(cols)

    for ci, col in enumerate(cols, 1):
        ws.cell(row=start_row, column=ci, value=col)
    _apply_header(ws, start_row, n)

    for ri, (_, row_data) in enumerate(df.iterrows()):
        excel_row = start_row + 1 + ri
        _apply_data_row(ws, excel_row, n, alt=(ri % 2 == 1))
        for ci, val in enumerate(row_data, 1):
            c = ws.cell(row=excel_row, column=ci, value=val)
            c.alignment = Alignment(horizontal="center", vertical="center")
            if any(x in str(val) for x in ["🔴", "🟡", "✅", "🔥", "⚪"]):
                _flag_cell(ws, excel_row, ci, val)

    return start_row + 1 + len(df)


def _dark_bg(ws):
    ws.sheet_view.showGridLines = False
    for row in ws.iter_rows(min_row=1, max_row=200, min_col=1, max_col=20):
        for cell in row:
            if cell.fill.patternType is None or cell.fill.fgColor.rgb in ("00000000", "FFFFFFFF"):
                cell.fill = PatternFill("solid", fgColor="0D0F14")


# ══════════════════════════════════════════════════════════════════════════════
# ██  SECTION 4 — BUILD EXCEL WORKBOOK
# ══════════════════════════════════════════════════════════════════════════════

def build_labour_workbook(data, output_path):
    wb = Workbook()
    wb.remove(wb.active)

    f_rev = data["daily"]["Net sales"].sum() / (len(data["daily"]) / 7)
    staff_df   = calc_staff_wages(data)
    summary    = calc_labour_summary(staff_df, f_rev)
    overlay_df = calc_hourly_overlay(data.get("hourly_live"), data=data)
    over_df    = calc_overstaffing(overlay_df)
    under_df   = calc_understaffing(overlay_df)
    day_df     = calc_day_labour(total_wages=summary["Staff Wages Total"])

    other_costs_map = {
        "Kitchen Cleaner":  245.00, "Awais Bhai": 200.00, "Book Keeper": 60.00,
        "Anti Wage": 100.00, "Chintan Shopping": 60.00,
    }
    other_df   = pd.DataFrame(
        [{"Cost Item": k, "Amount (£)": v} for k, v in other_costs_map.items()]
    )

    # ── Sheet 1: Labour Summary ───────────────────────────────────────────────
    ws1 = wb.create_sheet("1 Labour Summary")
    ws1.sheet_properties.tabColor = "F5A623"
    ws1.row_dimensions[1].height  = 40
    ws1.row_dimensions[2].height  = 20
    ws1.sheet_view.showGridLines  = False

    ws1.merge_cells("A1:H1")
    c = ws1["A1"]
    c.value = f"CHOCOBERRY — LABOUR COST SUMMARY   |   Week: {WEEK_LABEL}"
    c.font  = Font(bold=True, color="F5A623", name="Arial", size=14)
    c.fill  = PatternFill("solid", fgColor="0D0F14")
    c.alignment = Alignment(horizontal="left", vertical="center")

    kpis = [
        ("STAFF WAGES",  f"£{summary['Staff Wages Total']:,.2f}"),
        ("OTHER COSTS",  f"£{summary['Other Costs Total']:,.2f}"),
        ("TOTAL LABOUR", f"£{summary['Total Labour Cost']:,.2f}"),
        ("FORECAST REV", f"£{summary['Forecast Week Revenue']:,.2f}"),
        ("LABOUR %",     f"{summary['Labour % of Revenue']}%"),
        ("STATUS",       summary['Flag (>30%)']),
        ("MAX SBY COST", f"£{summary['SBY Max Additional Cost']:,.2f}"),
        ("MAX LABOUR %", f"{summary['Max Labour % (incl SBY)']}%"),
    ]
    kpi_colors = [
        "1a1d26", "1a1d26", "1a1d26", "1a1d26",
        "2a1010" if summary["Labour % of Revenue"] > 30 else "102a18",
        "2a1010" if "OVER" in summary["Flag (>30%)"] else "102a18",
        "1a1d26", "1a1d26",
    ]
    for col_i, ((label, value), bg) in enumerate(zip(kpis, kpi_colors), 1):
        lc = ws1.cell(row=3, column=col_i, value=label)
        lc.font = Font(bold=True, color="F5A623", name="Arial", size=8)
        lc.fill = PatternFill("solid", fgColor=bg)
        lc.alignment = Alignment(horizontal="center")

        color = "FF4444" if ("🔴" in value or "OVER" in value) else "3ECF8E" if "✅" in value else "E0E0E0"
        vc = ws1.cell(row=4, column=col_i, value=value)
        vc.font = Font(bold=True, color=color, name="Arial", size=11)
        vc.fill = PatternFill("solid", fgColor=bg)
        vc.alignment = Alignment(horizontal="center")
    ws1.row_dimensions[4].height = 26

    _write_df(ws1, staff_df, start_row=7,
              title="■ STAFF WAGES — Hours × Hourly Rate", title_span=8)
    _write_df(ws1, other_df, start_row=7 + len(staff_df) + 4,
              title="■ OTHER WEEKLY COSTS", title_span=4)
    _set_col_widths(ws1, [14, 12, 14, 14, 16, 10, 10, 10])

    # ── Sheet 2: Day Labour vs Revenue ────────────────────────────────────────
    ws2 = wb.create_sheet("2 Day Labour vs Revenue")
    ws2.sheet_view.showGridLines = False

    ws2.merge_cells("A1:F1")
    c = ws2["A1"]
    c.value = f"DAY-BY-DAY LABOUR COST vs FORECAST REVENUE   |   Week: {WEEK_LABEL}"
    c.font  = Font(bold=True, color="F5A623", name="Arial", size=13)
    c.fill  = PatternFill("solid", fgColor="0D0F14")
    c.alignment = Alignment(horizontal="left", vertical="center")

    end_row = _write_df(ws2, day_df, start_row=3,
                        title="■ Labour % per Day — flagged red if > 30%", title_span=6)
    note_row = end_row + 2
    note = ws2.cell(row=note_row, column=1,
                    value="⚠️  Labour threshold: 30% of revenue. SBY staff not included — add if called in.")
    note.font = Font(color="FFA500", italic=True, name="Arial", size=9)
    note.fill = PatternFill("solid", fgColor="0D0F14")
    ws2.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=6)
    _set_col_widths(ws2, [14, 18, 18, 18, 12, 22])

    # ── Sheet 3: Hourly Overlay ───────────────────────────────────────────────
    ws3 = wb.create_sheet("3 Hourly Overlay")
    ws3.sheet_view.showGridLines = False

    ws3.merge_cells("A1:L1")
    c = ws3["A1"]
    c.value = "HOUR-BY-HOUR REVENUE vs STAFF COST OVERLAY   |   Baseline: Jan–Apr 2026 (91-day avg)"
    c.font  = Font(bold=True, color="F5A623", name="Arial", size=13)
    c.fill  = PatternFill("solid", fgColor="0D0F14")
    c.alignment = Alignment(horizontal="left", vertical="center")

    _write_df(ws3, overlay_df, start_row=3,
              title="■ Revenue vs Staff Cost — All Hours", title_span=12)
    _set_col_widths(ws3, [8, 14, 16, 14, 10, 12, 16, 12, 18, 18, 16, 20])

    # ── Sheet 4: Overstaffing Flags ───────────────────────────────────────────
    ws4 = wb.create_sheet("4 Overstaffing Flags")
    ws4.sheet_view.showGridLines = False

    ws4.merge_cells("A1:F1")
    c = ws4["A1"]
    c.value = "🔴 OVERSTAFFING FLAGS — Hours where staff cost exceeds revenue generated"
    c.font  = Font(bold=True, color="FF4444", name="Arial", size=13)
    c.fill  = PatternFill("solid", fgColor="0D0F14")
    c.alignment = Alignment(horizontal="left", vertical="center")

    if len(over_df) > 0:
        end_row = _write_df(ws4, over_df, start_row=3,
                            title="■ Overstaffed Hours", title_span=6)
    else:
        ws4.cell(row=3, column=1, value="✅ No overstaffing detected this week.").font = \
            Font(color="3ECF8E", bold=True, name="Arial", size=11)
        end_row = 5

    explanations = [
        "WHAT THIS MEANS:",
        f"• Overstaffing = confirmed staff > 2 during hours generating < £{OVERSTAFFING_THRESHOLD}/hr",
        "• These hours cost more in wages than they generate in revenue",
        "• RECOMMENDATION: Reduce morning shift start times or delay opening until 12:00",
        "• Hours 10:00–11:00 are the worst offenders — £706 revenue, 7 staff on shift",
        "• Consider: Start FOH staff at 12:00 instead of 11:30 on quiet days",
    ]
    exp_row = end_row + 2
    for i, text in enumerate(explanations):
        c = ws4.cell(row=exp_row + i, column=1, value=text)
        c.font = Font(color="F5A623" if i == 0 else "AAAAAA", bold=(i == 0), name="Arial", size=9)
        c.fill = PatternFill("solid", fgColor="0D0F14")
        ws4.merge_cells(start_row=exp_row+i, start_column=1, end_row=exp_row+i, end_column=6)
    _set_col_widths(ws4, [8, 16, 18, 14, 20, 20])

    # ── Sheet 5: Understaffing Flags ──────────────────────────────────────────
    ws5 = wb.create_sheet("5 Understaffing Flags")
    ws5.sheet_view.showGridLines = False

    ws5.merge_cells("A1:F1")
    c = ws5["A1"]
    c.value = "🟡 UNDERSTAFFING FLAGS — Peak hours where revenue is high but cover is low"
    c.font  = Font(bold=True, color="FFA500", name="Arial", size=13)
    c.fill  = PatternFill("solid", fgColor="0D0F14")
    c.alignment = Alignment(horizontal="left", vertical="center")

    if len(under_df) > 0:
        end_row = _write_df(ws5, under_df, start_row=3,
                            title="■ Understaffed Peak Hours", title_span=6)
    else:
        ws5.cell(row=3, column=1,
                 value="✅ No critical understaffing detected — peak hours appear well covered.").font = \
            Font(color="3ECF8E", bold=True, name="Arial", size=11)
        end_row = 5

    sby_lines = [
        "SBY CALL-IN GUIDE (Based on 18:00 trade signal):",
        "• 18:00 revenue looks HIGH → Call SBY staff in at 19:00",
        "• 18:00 revenue looks MODERATE → Call SBY at normal time (20:00)",
        "• 18:00 revenue looks QUIET → Delay SBY by 1 hour or release for night",
        "• PEAK HOURS 19:00–23:00 = 67.4% of all revenue — NEVER understaff these hours",
        f"• SBY max additional cost this week: £{summary['SBY Max Additional Cost']:.2f}",
    ]
    sby_row = end_row + 2
    for i, text in enumerate(sby_lines):
        c = ws5.cell(row=sby_row + i, column=1, value=text)
        c.font = Font(color="F5A623" if i == 0 else "AAAAAA", bold=(i == 0), name="Arial", size=9)
        c.fill = PatternFill("solid", fgColor="0D0F14")
        ws5.merge_cells(start_row=sby_row+i, start_column=1, end_row=sby_row+i, end_column=6)
    _set_col_widths(ws5, [8, 16, 18, 14, 20, 20])

    # ── Sheet 6: SBY Tracker ──────────────────────────────────────────────────
    ws6 = wb.create_sheet("6 SBY Tracker")
    ws6.sheet_view.showGridLines = False

    ws6.merge_cells("A1:G1")
    c = ws6["A1"]
    c.value = "🔥 STANDBY (SBY) DECISION TRACKER — Call-In Cost vs Savings"
    c.font  = Font(bold=True, color="F5A623", name="Arial", size=13)
    c.fill  = PatternFill("solid", fgColor="0D0F14")
    c.alignment = Alignment(horizontal="left", vertical="center")

    sby_df = pd.DataFrame([
        {
            "Name":             name,
            "Max SBY Hours":    v["max_sby_hrs"],
            "Rate (£/hr)":      v["hourly_rate"],
            "Max SBY Cost (£)": round(v["max_sby_hrs"] * v["hourly_rate"], 2),
            "Called In?":       "Leave blank",
            "Actual Hours":     "Leave blank",
            "Actual Cost (£)":  "Leave blank",
        }
        for name, v in SBY_STAFF.items()
    ])
    end_row = _write_df(ws6, sby_df, start_row=3,
                        title="■ SBY Staff — Fill in 'Called In?' each night", title_span=7)

    total_row = end_row + 1
    ws6.cell(row=total_row, column=1, value="TOTAL MAX SBY COST").font = \
        Font(bold=True, color="F5A623", name="Arial", size=10)
    ws6.cell(row=total_row, column=4,
             value=f"£{summary['SBY Max Additional Cost']:.2f}").font = \
        Font(bold=True, color="FF4444", name="Arial", size=10)
    for col in [1, 4]:
        ws6.cell(row=total_row, column=col).fill = PatternFill("solid", fgColor="1a1d26")
    _set_col_widths(ws6, [14, 14, 12, 16, 14, 14, 16])

    for ws in wb.worksheets:
        _dark_bg(ws)

    wb.save(output_path)
    print(f"✅  Saved: {output_path}")
    return summary, overlay_df, over_df, under_df


# ══════════════════════════════════════════════════════════════════════════════
# ██  SECTION 5 — DATA LOADING (dashboard)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def load_data():

    import streamlit as st

    base = os.path.join(os.getcwd(), "Sales Summary Data")

    revenue_path = os.path.join(os.getcwd(), "daily_sales_master.csv")
    if os.path.exists(revenue_path):
        df = pd.read_csv(revenue_path)
    else:
        df = pd.DataFrame(DAILY_DATA)

    # Column Normalization & Standard Name Mapping
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Map back to specific case-sensitive names expected by the dashboard
    df = df.rename(columns={
        "net":              "Net sales",
        "net sales":        "Net sales",
        "net_sales":        "Net sales",
        "orders":           "Orders",
        "tax":              "Tax on net sales",
        "tax on net sales": "Tax on net sales",
        "revenue":          "Revenue",
        "refunds":          "refunds",
        "day":              "day",
        "date":             "date",
    })

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    
    # Ensure missing columns (like refunds) have default values if absent
    if "refunds" not in df.columns:
        df["refunds"] = 0.0


    personnel_path = os.path.join(os.getcwd(), "personnel_rates_master.csv")
    profiles_path  = os.path.join(os.getcwd(), "staff_profiles.csv")
    personnel_data = {}

    if os.path.exists(personnel_path):
        p_df = pd.read_csv(personnel_path)
        p_df.columns = [c.strip() for c in p_df.columns]
        prof_df = pd.read_csv(profiles_path) if os.path.exists(profiles_path) else None

        for _, row in p_df.iterrows():
            name = str(row.get("Name","")).strip()
            if not name or name == "nan": continue
            entry = row.to_dict()
            entry["role"] = "Junior"
            entry["dept"] = "Front"
            if prof_df is not None:
                p_match = prof_df[prof_df["Name"].str.strip() == name]
                if not p_match.empty:
                    entry["role"] = p_match.iloc[0].get("Role", "Junior")
                    entry["dept"] = p_match.iloc[0].get("Department", "Front")
            personnel_data[name] = entry

    detailed_shifts = []
    
    # ── Dynamic Rota Path (Deducing Week) ──
    _latest_dt = None
    if not df.empty and "date" in df.columns:
        _latest_dt = pd.to_datetime(df["date"]).max()
    
    _folder_date = _latest_dt if _latest_dt is not None else datetime.today()
    _folder_start = _folder_date - pd.Timedelta(days=_folder_date.weekday())
    _folder_end = _folder_start + pd.Timedelta(days=6)
    _folder_name = f"Rota week {_folder_start.strftime('%d %b').lower()} - {_folder_end.strftime('%d %B').lower()} {_folder_start.year}"
    
    # Try multiple naming conventions due to manual/OS variations
    candidates = [
        _folder_name,
        f"Rota week {_folder_start.strftime('%d %b')} - {_folder_end.strftime('%d %B %Y')}",
        f"Rota week {_folder_start.strftime('%d %b').lower()} - {_folder_end.strftime('%d %B %Y').lower()}",
        f"Rota week {_folder_start.strftime('%d %B').lower()} - {_folder_end.strftime('%d %B').lower()} {_folder_start.year}",
    ]
    
    rota_det_path = None
    for cand in candidates:
        p = os.path.join(os.getcwd(), cand, "detailed_rota_with_shifts.csv")
        if os.path.exists(p):
            rota_det_path = p
            break
    
    if rota_det_path:
        with open(rota_det_path, "r") as f:
            r_lines = [l.split(",") for l in f.readlines()]
            r_days  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

            nickname_map = {
                "DHIRAJ": "Dhiraj Mangade", "ATHARAV": "Atharvkumar Sanjay", "ATHARV": "Atharvkumar Sanjay",
                "CHINTAN": "Chintan", "CHINTHAN": "Chintan",  # both spellings
                "DAMINI": "Damini Sharadchandra Aher", "NITIN": "Nithin", "NITHIN": "Nithin",
                "PAMITHA": "Pamitha Perera",
                "MELLISSA": "Mellissa Teshali Leontia", "MELLISA": "Mellissa Teshali Leontia",  # both spellings
                "DIKSHA": "Dikshya", "DIKSHYA": "Dikshya",
                "SUPREME": "Supreme Gurung", "TULIKA": "Tulika Das Adhikari", "MUNIRA": "Munira",
                "BHOOMIKA": "Bhoomika", "REWATHI": "Dhriti Kulshrestha", "DHRITI": "Dhriti Kulshrestha",
                "RAVI": "Ravi Kishore", "RAJESH": "Rajesh Yadav", "ASMA": "Asma"
            }

            for r_idx in range(len(r_lines)):
                row_data = r_lines[r_idx]
                if len(row_data) < 2: continue
                if any(x in row_data[0].upper() for x in ["MONDAY","KITCHEN","FRONT"]): continue

                for d_i in range(7):
                    c_t, c_n = d_i * 2, d_i * 2 + 1
                    if c_n < len(row_data):
                        t_r = row_data[c_t].strip()
                        raw_name = row_data[c_n].strip().upper()
                        if not raw_name or len(raw_name) < 2: continue

                        is_sby = ("SBY" in raw_name or "SYB" in raw_name)
                        n_nick = raw_name.split(" ")[0]
                        full_name = nickname_map.get(n_nick, n_nick.capitalize())

                        if t_r and full_name:
                            for hh in parse_time_range(t_r):
                                detailed_shifts.append({"day": r_days[d_i], "hour": hh, "name": full_name, "is_sby": is_sby})
    else:
        # Fallback to synthesizing if manual CSV is missing
        try:
            from rota_engine import RotaEngine
            engine = RotaEngine()
            engine.load_staff()
            engine.load_shifts()
            # Determine start of week based on today or a fixed reference
            w_start_dt = datetime.now() - timedelta(days=datetime.now().weekday()) 
            gen_rota = engine.generate_week(week_start=w_start_dt.replace(hour=0, minute=0, second=0))

            for _, r in gen_rota.iterrows():
                # Handle both Capital and lowercase keys for robustness (KeyError: 'end' fix)
                s_val = r.get("Start", r.get("start", "00:00"))
                e_val = r.get("End", r.get("end", "00:00"))
                h_start = int(str(s_val).split(":")[0])
                h_end   = int(str(e_val).split(":")[0])
                if h_end < h_start: h_end += 24

                for hh in range(h_start, h_end):
                    detailed_shifts.append({
                        "day":    r["Day"],
                        "hour":   hh % 24,
                        "name":   r["Name"],
                        "is_sby": r.get("SBY") == "Yes"
                    })
            st.info("💡 Rota data synthesized using Automated Rota Engine (Manual CSV not found).")
        except Exception as e:
            # Silent fallback if engine fails
            pass

    channel_dict  = CHANNEL_DATA.copy()
    dispatch_map  = {k: v.copy() for k, v in DISPATCH_DATA.items()}
    delivery_fees = 282.0
    hourly_map    = {h: 0.0 for h in range(24)}

    if os.path.exists(base):
        try:
            def clean(val):
                return float(str(val).replace("£","").replace(",","").strip()) if pd.notna(val) else 0.0

            # ── Strict Whitelist Harvest (prevents double-counting) ──────────────
            # Only these files carry authoritative DAILY timeline data.
            # Hourly / dispatch / channel files are read SEPARATELY below.
            DAILY_SUMMARY_FILES = {"sales_overview.csv", "net_sales_per_day.csv"}
            DETAIL_ORDER_FILES  = {"sales_data.csv"}

            all_orders_detail  = []
            all_daily_summaries = []

            # A. Detailed order-by-order export
            for f_name in DETAIL_ORDER_FILES:
                p = os.path.join(base, f_name)
                if not os.path.exists(p): continue
                try:
                    raw_df = pd.read_csv(p)
                    if "Order ID" not in raw_df.columns: continue
                    raw_df["date_dt"] = pd.to_datetime(raw_df["Order time"], errors="coerce")
                    raw_df = raw_df[raw_df["date_dt"].notna()]
                    for col in ["Net sales", "Revenue", "Refunds", "Tax on net sales"]:
                        if col in raw_df.columns: raw_df[col] = raw_df[col].apply(clean)
                    all_orders_detail.append(raw_df)
                except Exception as e:
                    logging.warning(f"Failed to load detailed order file {f_name}: {e}")

            # B. Daily summary exports (exactly one file wins per date via dedup)
            for f_name in DAILY_SUMMARY_FILES:
                p = os.path.join(base, f_name)
                if not os.path.exists(p): continue
                try:
                    raw_ov = pd.read_csv(p)
                    if "Order time" not in raw_ov.columns or "Net sales" not in raw_ov.columns: continue
                    raw_ov = raw_ov[raw_ov["Order time"].notna()].copy()
                    raw_ov["date"] = pd.to_datetime(raw_ov["Order time"], format="%Y-%m-%d", errors="coerce")
                    raw_ov = raw_ov[raw_ov["date"].notna() & (raw_ov["date"].dt.year >= 2024)]
                    for c in ["Net sales","Revenue","Orders","Tax on net sales","Refunds"]:
                        if c in raw_ov.columns: raw_ov[c] = raw_ov[c].apply(clean)
                    all_daily_summaries.append(raw_ov[["date","Net sales","Revenue","Orders","Tax on net sales","Refunds"] if "Orders" in raw_ov.columns else ["date","Net sales","Revenue","Tax on net sales","Refunds"]])
                except Exception as e:
                    logging.warning(f"Failed to load daily summary file {f_name}: {e}")

            # 2. Pull hourly / dispatch / channel from detailed orders or fallback CSVs
            detailed_kpis = {"hourly": {}}
            if all_orders_detail:
                full_orders = pd.concat(all_orders_detail).drop_duplicates(subset=["Order ID"])
                full_orders["date"] = full_orders["date_dt"].dt.normalize()

                # Aggregate detail into daily rows to supplement summary gaps
                daily_from_detail = full_orders.groupby("date", as_index=True).agg(
                    **{
                        "Net sales":        ("Net sales",        "sum"),
                        "Revenue":          ("Revenue",          "sum"),
                        "Refunds":          ("Refunds",          "sum"),
                        "Tax on net sales": ("Tax on net sales", "sum"),
                        "Orders":           ("Order ID",         "count"),
                    }
                ).reset_index()
                all_daily_summaries.append(daily_from_detail)

                # Hourly from detail (most accurate)
                full_orders["hour"] = full_orders["date_dt"].dt.hour
                detailed_kpis["hourly"] = full_orders.groupby("hour")["Net sales"].sum().to_dict()

                # Dispatch from detail
                if "Dispatch type" in full_orders.columns:
                    for k, v in full_orders.groupby("Dispatch type")["Net sales"].sum().items():
                        key = str(k).strip()
                        if key in dispatch_map: dispatch_map[key]["revenue"] = v

                # Channel from detail
                if "Sales channel name" in full_orders.columns:
                    for k, v in full_orders.groupby("Sales channel name")["Net sales"].sum().items():
                        key = str(k).strip()
                        for std in ["Deliveroo","Just Eat","POS","Uber Eats","Web"]:
                            if std.lower() in key.lower(): channel_dict[std] = v

            else:
                # Fallback: read hourly and dispatch from their dedicated summary CSVs
                hr_path = os.path.join(base, "net_sales_by_hour_of_day.csv")
                if os.path.exists(hr_path):
                    hr_df = pd.read_csv(hr_path)
                    for _, r in hr_df.iterrows():
                        try: detailed_kpis["hourly"][int(r.iloc[1])] = clean(r.iloc[2])
                        except Exception as e:
                            logging.warning(f"Failed to parse row in hourly CSV: {e}")

                dispatch_path = os.path.join(base, "net_sales_by_dispatch_type.csv")
                if os.path.exists(dispatch_path):
                    disp_df = pd.read_csv(dispatch_path)
                    for key, col_idx in [("Collection",1),("Delivery",2),("Dine In",3),("Take Away",4)]:
                        try: dispatch_map[key]["revenue"] = clean(disp_df.iloc[-1, col_idx])
                        except Exception as e:
                            logging.warning(f"Failed to parse row in dispatch CSV: {e}")

                ch_path = os.path.join(base, "net_sales_by_sales_channel.csv")
                if os.path.exists(ch_path):
                    ch_df = pd.read_csv(ch_path)
                    for i, std in enumerate(["Deliveroo","Just Eat","POS","Uber Eats","Web"]):
                        try: channel_dict[std] = clean(ch_df.iloc[-1, i+1])
                        except Exception as e:
                            logging.warning(f"Failed to parse row in channel CSV: {e}")

            hourly_map = {h: detailed_kpis["hourly"].get(h, 0.0) for h in range(24)}

            # 3. Merge daily timeline — dedupe by date (summary file wins, detail fills gaps)
            if all_daily_summaries:
                merged = pd.concat(all_daily_summaries).sort_values("date")
                # Keep the summary file row for each date; detail only fills missing dates
                merged = merged.drop_duplicates(subset=["date"], keep="first")
                merged = merged[merged["date"].dt.year >= 2024]   # safety: strip 1970 rows
                merged["rolling7"] = merged["Net sales"].rolling(window=7).mean().fillna(merged["Net sales"])
                merged["day"]      = merged["date"].dt.day_name()
                merged["refunds"]  = merged["Refunds"].apply(clean) if "Refunds" in merged.columns else 0.0
                df = merged.copy()

        except Exception as e:
            st.warning(f"Data engine error: {e}")

    # ── Auto-compute Weekly Summary from daily df ──────────────────────
    auto_weekly = []
    if not df.empty and "Net sales" in df.columns:
        _wk = df.copy()
        _wk["date"] = pd.to_datetime(_wk["date"])
        _wk["week_start"] = _wk["date"] - pd.to_timedelta(_wk["date"].dt.weekday, unit="D")
        _wk_grp = _wk.groupby("week_start").agg(
            net=("Net sales", "sum"),
            orders=("Orders", "sum") if "Orders" in _wk.columns else ("Net sales", "count"),
            tax=("Tax on net sales", "sum") if "Tax on net sales" in _wk.columns else ("Net sales", lambda x: 0),
        ).reset_index()
        for _, r in _wk_grp.iterrows():
            auto_weekly.append({
                "week":   r["week_start"].strftime("%d %b"),
                "net":    round(float(r["net"]), 2),
                "orders": int(r["orders"]),
                "tax":    round(float(r["tax"]), 2),
            })

    # ── Auto-compute Week Label from latest date ────────────────────────
    auto_week_label = WEEK_LABEL  # fallback
    if not df.empty:
        _latest = pd.to_datetime(df["date"]).max()
        _week_start = _latest - pd.Timedelta(days=_latest.weekday())
        _week_end = _week_start + pd.Timedelta(days=6)
        auto_week_label = f"{_week_start.strftime('%d %b')} – {_week_end.strftime('%d %b %Y')}"

    # ── Auto-compute Payment Data from CSV ─────────────────────────────
    auto_payment = dict(PAYMENT_DATA)  # fallback to static
    try:
        pay_path = os.path.join(base, "net_sales_by_payment_method.csv")
        if os.path.exists(pay_path):
            pay_csv = pd.read_csv(pay_path)
            # Last row has totals; column names are the payment methods
            pay_row = pay_csv.iloc[-1]
            _pay_map = {}
            for col in pay_csv.columns:
                try:
                    val = float(str(pay_row[col]).replace(",", "").replace("£", "").strip())
                    if val > 0:
                        _pay_map[col] = val
                except: pass
            if _pay_map:
                auto_payment = _pay_map
    except: pass

    # ── Auto-compute Channel Data from CSV ─────────────────────────────
    auto_channels = channel_dict  # already computed from CSV in harvest engine

    return {
        "daily":          df.sort_values("date"),
        "channels":       auto_channels,
        "dispatch_truth": dispatch_map,
        "delivery_fees":  delivery_fees,
        "shifts":         detailed_shifts,
        "hourly_live":    hourly_map,
        "personnel":      personnel_data,
        # ── Fully auto-computed from CSVs ───────────────────────────
        "weekly":         auto_weekly,
        "payment":        auto_payment,
        "week_label":     auto_week_label,
    }



# ══════════════════════════════════════════════════════════════════════════════
# ██  SECTION 6 — STREAMLIT DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

import streamlit as st

st.markdown("""
<style>
    .stApp { background-color: #0a0b0f; }
    .main .block-container { padding: 24px 32px; max-width: 1600px; }
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');
    html, body, [class*="css"] { font-family: 'DM Mono', monospace; color: #e8e9f0; }
    [data-testid="stSidebar"] { background-color: #12141a !important; border-right: 1px solid #252836; }
    [data-testid="stSidebar"] * { color: #e8e9f0 !important; }
    .sidebar-logo { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 20px; color: #f5a623 !important; letter-spacing: -0.5px; margin-bottom: 4px; }
    .sidebar-sub { font-size: 11px; color: #6b7094 !important; letter-spacing: 1px; text-transform: uppercase; }
    .live-dot { display:inline-block;width:8px;height:8px;border-radius:50%;background:#3ecf8e;margin-right:6px;animation:pulse 2s infinite; }
    @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.4;} }
    .status-box { background-color:#1a1d26;padding:10px 14px;border-radius:8px;border-left:3px solid #f5a623;margin-top:6px;font-size:12px;color:#6b7094 !important; }
    [data-testid="stMetric"] { background:#1a1d26;border:1px solid #252836;border-radius:12px;padding:12px 10px;border-left:3px solid #f5a623; }
    [data-testid="stMetricValue"] { font-family:'Syne',sans-serif !important;font-size:18px !important;font-weight:800 !important;color:#e8e9f0 !important;white-space:nowrap !important; }
    [data-testid="stMetricLabel"] { font-size:9px !important;letter-spacing:1.5px;text-transform:uppercase;color:#6b7094 !important; }
    [data-testid="stMetricDelta"] { font-size:11px !important; }
    .chart-card { background:#1a1d26;border:1px solid #252836;border-radius:12px;padding:22px;margin-bottom:16px; }
    .section-title { font-family:'Syne',sans-serif;font-weight:700;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#6b7094;margin-bottom:12px;margin-top:8px; }
    .page-title { font-family:'Syne',sans-serif;font-weight:800;font-size:24px;color:#e8e9f0;margin-bottom:4px; }
    .page-sub { font-size:12px;color:#6b7094;margin-bottom:24px; }
    .insight-box { background:#12141a;border:1px solid #252836;border-radius:8px;padding:12px 16px;margin-top:8px;font-size:11px;color:#6b7094;line-height:1.6; }
    .insight-box b { color:#e8e9f0; }
    [data-testid="stDataFrame"] { border:1px solid #252836 !important;border-radius:8px !important;overflow:hidden; }
    .stTabs [data-baseweb="tab-list"] { background:#12141a;border-radius:10px;padding:4px;gap:4px;border:1px solid #252836; }
    .stTabs [data-baseweb="tab"] { background:transparent;border-radius:8px;color:#6b7094;font-family:'DM Mono',monospace;font-size:12px;padding:8px 18px; }
    .stTabs [aria-selected="true"] { background:#1a1d26 !important;color:#e8e9f0 !important; }
    .stTabs [data-baseweb="tab-border"] { display:none; }
    .stSelectbox > div > div { background:#1a1d26;border:1px solid #252836;border-radius:8px;color:#e8e9f0; }
    .stDateInput > div > div { background:#1a1d26;border:1px solid #252836;border-radius:8px; }
    hr { border-color: #252836; }
    .period-badge { display:inline-block;background:#1a1d26;border:1px solid #252836;padding:5px 14px;border-radius:20px;font-size:11px;color:#6b7094; }
    .labour-kpi { background:#1a1d26;border:1px solid #252836;border-radius:10px;padding:14px;text-align:center;margin-bottom:8px; }
    .labour-kpi-label { font-size:9px;color:#6b7094;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px; }
    .labour-kpi-value { font-family:'Syne',sans-serif;font-size:18px;font-weight:800;color:#e8e9f0; }
</style>
""", unsafe_allow_html=True)

COLORS = {
    "accent":  "#f5a623", "accent2": "#e8724a",
    "accent3": "#7c5cbf", "accent4": "#3ecf8e",
    "red":     "#e05c5c", "muted":   "#6b7094",
}
PALETTE = [COLORS["accent"], COLORS["accent2"], COLORS["accent3"],
           COLORS["accent4"], COLORS["red"], COLORS["muted"]]

def dark_layout(fig, height=340, showlegend=False):
    fig.update_layout(
        height=height, template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono, monospace", color="#6b7094", size=11),
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=showlegend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(size=10), bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zeroline=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zeroline=False),
    )
    return fig

def _load():
    return load_data()

data   = _load()
all_df = data["daily"]

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-logo">Choco<span style="color:#e8e9f0">berry</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub"><span class="live-dot" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#3ecf8e;margin-right:5px;"></span>Intelligence Dashboard</div>', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("**📅 Date Range**")
    min_d = all_df["date"].min().date()
    max_d = all_df["date"].max().date()
    dr    = st.date_input("Date Range", [min_d, max_d], label_visibility="collapsed")
    start_d, end_d = (dr[0], dr[1]) if len(dr) == 2 else (min_d, max_d)

    st.markdown("**🚚 Dispatch Type**")
    dispatch_opts = ["All","Collection","Delivery","Dine In","Take Away"]
    sel_dispatch  = st.selectbox("Dispatch Type", dispatch_opts, label_visibility="collapsed")

    st.markdown("**📊 Sales Channel**")
    channel_opts = ["All"] + list(CHANNEL_DATA.keys())
    sel_channel  = st.selectbox("Sales Channel", channel_opts, label_visibility="collapsed")

    st.markdown("---")
    f_df = all_df[(all_df["date"].dt.date >= start_d) & (all_df["date"].dt.date <= end_d)]
    total_orders = int(f_df["Orders"].sum())
    st.markdown(f'<div class="status-box">💎 <b>{total_orders:,}</b> transactions selected</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="status-box">📅 Period: <b>{start_d.strftime("%d %b")} → {end_d.strftime("%d %b %Y")}</b></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="status-box">📈 {len(f_df)} trading days in view</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**🔧 Labour Report**")
    if st.button("📥 Generate Excel Report", width="stretch"):
        import tempfile, io
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
        build_labour_workbook(data, tmp_path)
        with open(tmp_path, "rb") as f:
            xlsx_bytes = f.read()
        os.unlink(tmp_path)
        st.download_button(
            label="⬇️ Download chocoberry_labour_report.xlsx",
            data=xlsx_bytes,
            file_name="chocoberry_labour_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    st.markdown("---")
    st.markdown("**🌐 Remote Cloud Sync**")
    # Get portal URL from session state or default
    if "portal_url_input" not in st.session_state:
        st.session_state["portal_url_input"] = os.environ.get("PORTAL_URL", "http://localhost:5050")
    
    portal_url_val = st.text_input("Invoice Portal URL", 
                               value=st.session_state["portal_url_input"],
                               placeholder="e.g. https://portal.render.com",
                               help="Paste your Render or Streamlit Portal URL here to sync invoices from staff.")
    st.session_state["portal_url"] = portal_url_val.rstrip("/")
    st.markdown('<div style="font-size:10px; color:#6b7094">Syncs staff uploads from your phone-friendly portal into this system.</div>', unsafe_allow_html=True)

# ── KPI computation ───────────────────────────────────────────────────────
master_rev    = f_df["Revenue"].sum()
master_tax    = f_df["Tax on net sales"].sum()
master_ord    = f_df["Orders"].sum()
master_net    = f_df["Net sales"].sum()
total_refunds = f_df["refunds"].sum() if "refunds" in f_df.columns else 47.75

total_truth_rev = sum(v["revenue"] for v in data["dispatch_truth"].values())
total_truth_ord = sum(v["orders"]  for v in data["dispatch_truth"].values())
dispatch_ratio  = (
    data["dispatch_truth"].get(sel_dispatch, {}).get("revenue", 0) / total_truth_rev
    if sel_dispatch != "All" and total_truth_rev > 0 else 1.0
)

display_rev = master_rev * dispatch_ratio
display_ord = master_ord * dispatch_ratio
display_tax = master_tax * dispatch_ratio
display_net = master_net * dispatch_ratio
aov         = display_rev / display_ord if display_ord > 0 else 0
daily_avg   = display_net / len(f_df)  if len(f_df)  > 0 else 0

# ── Page header ───────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
  <div>
    <div class="page-title">🍫 Chocoberry Intelligence Dashboard</div>
    <div class="page-sub">Business performance &middot; {start_d.strftime('%b %Y')} &ndash; {end_d.strftime('%b %Y')} &middot; {len(f_df)} trading days</div>
  </div>
  <div class="period-badge">📅 {start_d.strftime('%d %b')} – {end_d.strftime('%d %b %Y')} &nbsp;·&nbsp; {sel_dispatch}</div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13 = st.tabs([
    "📊 Overview", "📈 Trends", "🕐 Patterns", "🛒 Channels",
    "⏰ Efficiency", "🔮 Forecast", "💷 Labour Report", "📅 Rota Builder",
    "🍕 Inventory & COGS", "♻️ Waste Log", "🚀 Strategic Optimization", "📄 Invoice Management", "💾 Database Explorer"
])

# ════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="section-title">Key Performance Indicators</div>', unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Total Net Sales",  f"£{display_net:,.0f}", f"+403% YoY" if sel_dispatch == "All" else sel_dispatch)
    k2.metric("🛒 Total Orders",     f"{int(display_ord):,}", f"{len(f_df)} trading days")
    k3.metric("🎯 Avg Order Value",  f"£{aov:.2f}")
    k4.metric("📅 Daily Average",    f"£{daily_avg:,.0f}")

    k5, k6, k7, k8 = st.columns(4)
    k5.metric("🏦 Tax Collected",    f"£{display_tax:,.0f}", "3.7% of net sales")
    k6.metric("🚚 Total Charges",    "£520.75", "+569% vs prior period")
    k7.metric("↩️ Total Refunds",    f"£{total_refunds:,.2f}", "0.02% refund rate ✅")
    k8.metric("🔥 Peak Hour",        "21:00", "£37,478 · 19-23 = 85% rev")

    st.markdown("---")
    st.markdown('<div class="section-title">Daily Revenue Trend</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        plot_df = f_df.copy()
        if sel_dispatch != "All":
            plot_df["Net sales"] = plot_df["Net sales"] * dispatch_ratio

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=plot_df["date"], y=plot_df["Net sales"],
            name="Daily Net Sales", fill="tozeroy",
            line=dict(color=COLORS["accent"], width=1.5),
            fillcolor="rgba(245,166,35,0.08)",
        ))
        rolling_src = plot_df["rolling7"] if "rolling7" in plot_df.columns else plot_df["Net sales"].rolling(7).mean()
        fig.add_trace(go.Scatter(
            x=plot_df["date"], y=rolling_src,
            name="7-Day Rolling Avg",
            line=dict(color=COLORS["accent2"], width=2.5, dash="dot"),
        ))
        dark_layout(fig, height=320, showlegend=True)
        fig.update_xaxes(title="")
        fig.update_yaxes(title="", tickprefix="£")
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.markdown("**Period Comparison**")
        st.markdown(f"""
        <div style="background:#1a1d26;border:1px solid #252836;border-radius:10px;padding:14px;margin-bottom:8px;text-align:center">
            <div style="font-size:10px;color:#6b7094;margin-bottom:4px">THIS PERIOD ({start_d.strftime('%b')}–{end_d.strftime('%b %Y')})</div>
            <div style="font-family:Syne,sans-serif;font-size:22px;font-weight:800;color:#f5a623">£{display_net:,.0f}</div>
            <div style="font-size:10px;color:#6b7094">Net sales</div>
        </div>
        <div style="background:#1a1d26;border:1px solid #252836;border-radius:10px;padding:14px;margin-bottom:8px;text-align:center">
            <div style="font-size:10px;color:#6b7094;margin-bottom:4px">LAST PERIOD</div>
            <div style="font-family:Syne,sans-serif;font-size:22px;font-weight:800;color:#6b7094">£49,777</div>
            <div style="font-size:10px;color:#6b7094">Net sales</div>
        </div>
        <div style="background:#1a1d26;border:1px solid #f5a623;border-radius:10px;padding:14px;text-align:center">
            <div style="font-size:10px;color:#6b7094;margin-bottom:4px">GROWTH</div>
            <div style="font-family:Syne,sans-serif;font-size:28px;font-weight:800;color:#3ecf8e">+448%</div>
            <div style="font-size:10px;color:#6b7094">Net sales vs prior period</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Monthly Breakdown</div>', unsafe_allow_html=True)
    m_df = f_df.copy()
    m_df["month_str"] = m_df["date"].dt.strftime("%B %Y")
    monthly_stats = m_df.groupby("month_str").agg({"Net sales": "sum", "Orders": "sum"}).reset_index()
    monthly_stats["sort_key"] = pd.to_datetime(monthly_stats["month_str"], format="%B %Y")
    monthly_stats = monthly_stats.sort_values("sort_key").drop(columns=["sort_key"])
    monthly_stats["AOV"] = (monthly_stats["Net sales"] / monthly_stats["Orders"]).apply(lambda x: f"£{x:.2f}")
    monthly_stats["Orders"] = monthly_stats["Orders"].apply(lambda x: f"{int(x):,}")
    monthly_stats["Net Sales"] = monthly_stats["Net sales"].apply(lambda x: f"£{x:,.0f}")
    monthly_display = monthly_stats[["month_str","Net Sales","Orders","AOV"]]
    monthly_display.columns = ["Month","Net Sales","Orders","AOV"]
    st.dataframe(monthly_display, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Day-by-Day Performance Table</div>', unsafe_allow_html=True)

    day_table_df = f_df.copy()
    if sel_dispatch != "All":
        day_table_df["Net sales"] = day_table_df["Net sales"] * dispatch_ratio
        day_table_df["Revenue"]   = day_table_df["Revenue"]   * dispatch_ratio
        day_table_df["Orders"]    = day_table_df["Orders"]    * dispatch_ratio

    day_table_df = day_table_df.sort_values("date").reset_index(drop=True)
    day_table_df["AOV"]   = (day_table_df["Revenue"] / day_table_df["Orders"]).round(2)
    day_table_df["WoW %"] = day_table_df["Net sales"].pct_change(periods=7).mul(100).round(1)
    peak_idx = day_table_df["Net sales"].idxmax()
    slow_idx = day_table_df["Net sales"].idxmin()

    display_day = day_table_df[["date","day","Net sales","Orders","AOV","Tax on net sales","WoW %"]].copy()
    display_day.columns = ["Date","Day","Net Sales £","Orders","AOV £","Tax £","WoW %"]
    display_day["Date"]        = display_day["Date"].dt.strftime("%d %b")
    display_day["Net Sales £"] = display_day["Net Sales £"].round(2)
    display_day["AOV £"]       = display_day["AOV £"].round(2)
    display_day["Tax £"]       = display_day["Tax £"].round(2)
    display_day["WoW %"]       = display_day["WoW %"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")

    def highlight_rows(row):
        if row.name == peak_idx:
            return ["background-color: rgba(62,207,142,0.15); color: #3ecf8e"] * len(row)
        elif row.name == slow_idx:
            return ["background-color: rgba(245,166,35,0.12); color: #f5a623"] * len(row)
        return [""] * len(row)

    styled = display_day.style.apply(highlight_rows, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True, height=320)
    st.markdown('<div class="insight-box">🟢 <b>Green row</b> = peak day (highest net sales) &nbsp;|&nbsp; 🟡 <b>Amber row</b> = slowest day &nbsp;|&nbsp; WoW % = change vs same day the prior week</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Best & Worst Trading Days</div>', unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("**🏆 Top 5 Best Days**")
        top5 = day_table_df.nlargest(5, "Net sales")[["date","day","Net sales","Orders"]].copy()
        top5["date"]      = top5["date"].dt.strftime("%d %b %Y")
        top5["Net sales"] = top5["Net sales"].apply(lambda x: f"£{x:,.0f}")
        top5.columns      = ["Date","Day","Net Sales","Orders"]
        top5.insert(0, "#", ["🥇","🥈","🥉","4","5"])
        st.dataframe(top5, width="stretch", hide_index=True)
        st.markdown('<div class="insight-box">🎯 New Year\'s Day, Spring weekend spikes, and Valentine\'s are the 3 peak events. Plan staffing in advance.</div>', unsafe_allow_html=True)

    with b2:
        st.markdown("**📉 5 Slowest Days**")
        bot5 = day_table_df.nsmallest(5, "Net sales")[["date","day","Net sales","Orders"]].copy()
        bot5["date"]      = bot5["date"].dt.strftime("%d %b %Y")
        bot5["Net sales"] = bot5["Net sales"].apply(lambda x: f"£{x:,.0f}")
        bot5.columns      = ["Date","Day","Net Sales","Orders"]
        bot5.insert(0, "#", ["1","2","3","4","5"])
        st.dataframe(bot5, width="stretch", hide_index=True)
        st.markdown('<div class="insight-box">⚠️ Thursdays & early January Mondays are consistently slowest. Consider reduced staffing and promotions.</div>', unsafe_allow_html=True)

    # ── PDF Report Button ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">Weekly PDF Report</div>', unsafe_allow_html=True)
    if _pdf_available:
        if st.button("📄 Generate Weekly PDF Report", key="pdf_gen"):
            with st.spinner("Generating PDF..."):
                pdf_bytes = generate_weekly_pdf(data, data["week_label"])
            fname = f"chocoberry_weekly_{datetime.now().strftime('%Y%m%d')}.pdf"
            st.download_button(
                "⬇️ Download PDF",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                key="pdf_dl"
            )
    else:
        st.info("Install reportlab to enable PDF export: `pip install reportlab`")


# ════════════════════════════════════════════════════════════════════
# TAB 2 — TRENDS
# ════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-title">Weekly Summary — Revenue, Orders & Tax</div>', unsafe_allow_html=True)

    # Auto-computed weekly data from CSVs via load_data()
    wk_df = pd.DataFrame(data["weekly"]) if data["weekly"] else pd.DataFrame(WEEKLY_DATA)
    wk_df["AOV"]       = (wk_df["net"] / wk_df["orders"].replace(0, 1)).round(2)
    wk_df["WoW Net %"] = wk_df["net"].pct_change().mul(100).round(1)
    wk_df["WoW Ord %"] = wk_df["orders"].pct_change().mul(100).round(1)

    weekly_display = wk_df.copy()
    weekly_display.columns = ["Week", "Net Sales £", "Orders", "Tax £", "AOV £", "WoW Net %", "WoW Ord %"]
    weekly_display["Net Sales £"] = weekly_display["Net Sales £"].apply(lambda x: f"£{x:,.0f}")
    weekly_display["Tax £"]       = weekly_display["Tax £"].apply(lambda x: f"£{x:,.0f}")
    weekly_display["AOV £"]       = weekly_display["AOV £"].apply(lambda x: f"£{x:.2f}")
    weekly_display["WoW Net %"]   = weekly_display["WoW Net %"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    weekly_display["WoW Ord %"]   = weekly_display["WoW Ord %"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "—")
    st.dataframe(weekly_display, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Weekly Revenue Trend</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        # Highlight highest week automatically
        _max_net = wk_df["net"].max()
        colors_weekly = [COLORS["accent2"] if r["net"] == _max_net else COLORS["accent"] for _, r in wk_df.iterrows()]
        fig_w = go.Figure(go.Bar(
            x=wk_df["week"], y=wk_df["net"],
            marker_color=colors_weekly, marker_line_color=COLORS["accent"], marker_line_width=1,
        ))
        fig_w.update_traces(marker_opacity=0.8)
        dark_layout(fig_w, 300)
        fig_w.update_yaxes(tickprefix="£")
        fig_w.update_layout(title=dict(text="Weekly Net Sales", font=dict(size=13, color="#e8e9f0")))
        st.plotly_chart(fig_w, width="stretch")

    with col2:
        wow_pct   = wk_df["net"].pct_change().mul(100).dropna()
        wow_weeks = wk_df["week"].iloc[1:].tolist()
        fig_wow   = go.Figure(go.Bar(
            x=wow_weeks, y=wow_pct.values,
            marker_color=[COLORS["accent4"] if v >= 0 else COLORS["red"] for v in wow_pct.values],
            marker_opacity=0.8,
        ))
        dark_layout(fig_wow, 300)
        fig_wow.update_yaxes(ticksuffix="%")
        fig_wow.update_layout(title=dict(text="Week-over-Week Net Sales Growth %", font=dict(size=13, color="#e8e9f0")))
        st.plotly_chart(fig_wow, width="stretch")

    st.markdown("---")
    st.markdown('<div class="section-title">Monthly Overview</div>', unsafe_allow_html=True)

    # Dynamic monthly grouping — works for any date range
    _monthly = f_df.copy()
    _monthly["month_key"] = _monthly["date"].dt.to_period("M")
    _mon_grp = _monthly.groupby("month_key").agg({"Net sales": "sum", "Orders": "sum"}).reset_index()
    _mon_grp["month_label"] = _mon_grp["month_key"].dt.strftime("%b '%y")
    _mon_grp["AOV"] = (_mon_grp["Net sales"] / _mon_grp["Orders"].replace(0, 1)).round(2)
    _mon_colors = [COLORS["accent"], COLORS["accent2"], COLORS["accent4"], COLORS["accent3"],
                   COLORS["muted"], COLORS["red"]][:len(_mon_grp)]

    col3, col4, col5 = st.columns(3)

    with col3:
        fig_mb = go.Figure(go.Bar(
            x=_mon_grp["month_label"], y=_mon_grp["Net sales"],
            marker_color=_mon_colors, marker_line_width=0, marker_opacity=0.85,
        ))
        dark_layout(fig_mb, 240)
        fig_mb.update_yaxes(tickprefix="£")
        fig_mb.update_layout(title=dict(text="Monthly Net Sales", font=dict(size=12, color="#e8e9f0")))
        st.plotly_chart(fig_mb, width="stretch")

    with col4:
        fig_mo = go.Figure(go.Bar(
            x=_mon_grp["month_label"], y=_mon_grp["Orders"],
            marker_color=[f"rgba(124,92,191,{0.5 + 0.35*(i/max(len(_mon_grp)-1,1))})" for i in range(len(_mon_grp))],
            marker_line_color=COLORS["accent3"], marker_line_width=1.5,
        ))
        dark_layout(fig_mo, 240)
        fig_mo.update_layout(title=dict(text="Monthly Order Count", font=dict(size=12, color="#e8e9f0")))
        st.plotly_chart(fig_mo, width="stretch")

    with col5:
        st.markdown("<br>", unsafe_allow_html=True)
        best_aov_idx = _mon_grp["AOV"].idxmax()
        for idx, row in _mon_grp.iterrows():
            color = "#3ecf8e" if idx == best_aov_idx else "#6b7094"
            arrow = " ↑" if idx == best_aov_idx else ""
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(255,255,255,.04)">
                <span style="font-size:12px;color:#6b7094">{row['month_label']}</span>
                <span style="font-family:Syne,sans-serif;font-weight:700;font-size:14px;color:{color}">£{row['AOV']:.2f}{arrow}</span>
            </div>
            """, unsafe_allow_html=True)
        _best_mon = _mon_grp.loc[best_aov_idx, "month_label"]
        st.markdown(f'<div class="insight-box">AOV trending — <b>{_best_mon}</b> has the highest avg order value in this period.</div>', unsafe_allow_html=True)


    st.markdown("---")
    st.markdown('<div class="section-title">7-Day Rolling Average vs Actual Daily Sales</div>', unsafe_allow_html=True)

    plot_df2 = f_df.copy()
    if sel_dispatch != "All":
        plot_df2["Net sales"] = plot_df2["Net sales"] * dispatch_ratio

    fig_roll = go.Figure()
    fig_roll.add_trace(go.Scatter(
        x=plot_df2["date"], y=plot_df2["Net sales"],
        name="Daily Actual", line=dict(color="rgba(124,92,191,0.6)", width=1),
    ))
    fig_roll.add_trace(go.Scatter(
        x=plot_df2["date"], y=plot_df2["Net sales"].rolling(7).mean(),
        name="7D Rolling Avg", line=dict(color=COLORS["accent"], width=2.5),
    ))
    dark_layout(fig_roll, 320, showlegend=True)
    fig_roll.update_yaxes(tickprefix="£")
    st.plotly_chart(fig_roll, width="stretch")


# ════════════════════════════════════════════════════════════════════
# TAB 3 — PATTERNS
# ════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-title">Weekly Trading Patterns</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    dow_map    = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    dow_totals = f_df.groupby("day")["Net sales"].sum().reindex(dow_map, fill_value=0)
    dow_labels = [d[:3] for d in dow_map]
    dow_nets   = dow_totals.values

    with col1:
        bar_colors = [COLORS["accent"] if i >= 4 else "rgba(245,166,35,0.35)" for i in range(7)]
        fig_dow = go.Figure(go.Bar(
            x=dow_labels, y=dow_nets,
            marker_color=bar_colors,
            marker_line_color=COLORS["accent"], marker_line_width=1.5,
        ))
        dark_layout(fig_dow, 280)
        fig_dow.update_yaxes(tickprefix="£")
        fig_dow.update_layout(title=dict(text="Revenue by Day of Week", font=dict(size=13, color="#e8e9f0")))
        st.plotly_chart(fig_dow, width="stretch")

    with col2:
        dow_ord_tot = f_df.groupby("day")["Orders"].sum().reindex(dow_map, fill_value=1)
        dow_aov     = [round(n/o, 2) if o > 0 else 0 for n,o in zip(dow_nets, dow_ord_tot)]
        day_counts  = f_df["day"].value_counts().reindex(dow_map, fill_value=1)
        dow_avg     = [round(n/c, 0) for n,c in zip(dow_nets, day_counts)]

        dow_table = pd.DataFrame({
            "Day":     [f"{d} {'🟢' if d=='Sunday' else '🔴' if d=='Monday' else ''}" for d in dow_map],
            "Total £": [f"£{n:,.0f}" for n in dow_nets],
            "Orders":  [f"{int(o):,}" for o in dow_ord_tot],
            "AOV":     [f"£{a:.2f}" for a in dow_aov],
            "Avg/Day": [f"£{avg:,.0f}" for avg in dow_avg],
        })
        st.dataframe(dow_table, width="stretch", hide_index=True)
        st.markdown('<div class="insight-box">📅 Fri/Sat/Sun generate <b>55% of weekly revenue</b> despite being 3 of 7 days. Sunday averages <b>£3,461/day</b> vs Monday\'s £2,088.</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">24-Hour Activity Distribution</div>', unsafe_allow_html=True)

    hour_keys = [f"{h:02d}:00" for h in range(24)]
    hour_vals = [data["hourly_live"].get(h, 0.0) for h in range(24)]

    h_colors = []
    for v in hour_vals:
        if v > 30000:   h_colors.append("rgba(245,166,35,0.95)")
        elif v > 15000: h_colors.append("rgba(245,166,35,0.65)")
        elif v > 5000:  h_colors.append("rgba(245,166,35,0.4)")
        else:           h_colors.append("rgba(245,166,35,0.15)")

    fig_hr = go.Figure(go.Bar(x=hour_keys, y=hour_vals, marker_color=h_colors, marker_line_width=0))
    dark_layout(fig_hr, 280)
    fig_hr.update_yaxes(tickprefix="£")
    fig_hr.update_layout(title=dict(text="Net Sales by Hour of Day", font=dict(size=13, color="#e8e9f0")))
    st.plotly_chart(fig_hr, width="stretch")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('<p style="color:#f5a623;font-weight:700;margin-bottom:0">🔥 Top 3 Busiest Hours</p>', unsafe_allow_html=True)
        h_sorted = sorted(data["hourly_live"].items(), key=lambda x: x[1], reverse=True)
        top3_h   = h_sorted[:3]

        for i, (h_int, val) in enumerate(top3_h):
            h_str  = f"{format_hour_ampm(h_int)} – {format_hour_ampm(h_int+1)}"
            color_h = [COLORS["accent"], COLORS["accent2"], COLORS["accent3"]][i]
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="font-size:12px;color:#6b7094">{h_str}</span><span style="font-family:Syne,sans-serif;font-weight:700;color:{color_h}">£{val:,.0f}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="insight-box">💡 Peak window <b>{format_hour_ampm(top3_h[0][0])} – {format_hour_ampm(top3_h[2][0]+1)}</b> generates highest revenues. Full staff mandatory.</div>', unsafe_allow_html=True)


    with c2:
        st.markdown('<p style="color:#f5a623;font-weight:700;margin-bottom:0">🌙 Late Night Activity</p>', unsafe_allow_html=True)

        # Dynamic: pull from live hourly data
        _late_hours = [(0, f"{format_hour_ampm(0)} – {format_hour_ampm(1)}"), 
                       (1, f"{format_hour_ampm(1)} – {format_hour_ampm(2)}"), 
                       (2, f"{format_hour_ampm(2)} – {format_hour_ampm(3)}")]
        _midnight = data["hourly_live"].get(0, 0)
        for h_int, h_label in _late_hours:
            val = data["hourly_live"].get(h_int, 0)
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="font-size:12px;color:#6b7094">{h_label}</span><span style="font-family:Syne,sans-serif;font-weight:700">£{val:,.0f}</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="insight-box">🌙 Midnight hour generates <b>£{_midnight:,.0f}</b> — significant late-night trade.</div>', unsafe_allow_html=True)


    with c3:
        st.markdown('<p style="color:#f5a623;font-weight:700;margin-bottom:0">🌅 Quietest Hours</p>', unsafe_allow_html=True)

        # Dynamic: find the 3 lowest non-zero hours
        _nonzero = [(h, v) for h, v in data["hourly_live"].items() if v > 0]
        _quietest = sorted(_nonzero, key=lambda x: x[1])[:3]
        for h_int, val in _quietest:
            h_label = f"{format_hour_ampm(h_int)} – {format_hour_ampm(h_int+1)}"
            color = COLORS["red"] if val < 500 else COLORS["muted"]
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="font-size:12px;color:#6b7094">{h_label}</span><span style="font-family:Syne,sans-serif;font-weight:700;color:{color}">£{val:,.0f}</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="insight-box">📉 Early morning hours are essentially dead. No staffing or deliveries needed before midday.</div>', unsafe_allow_html=True)



# ════════════════════════════════════════════════════════════════════
# TAB 4 — CHANNELS
# ════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-title">Dispatch & Sales Channels</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        disp_rev_total = sum(v["revenue"] for v in data["dispatch_truth"].values())
        disp_ord_total = sum(v["orders"]  for v in data["dispatch_truth"].values())
        disp_labels    = list(data["dispatch_truth"].keys())
        disp_revs      = [data["dispatch_truth"][k]["revenue"] for k in disp_labels]

        fig_disp = go.Figure(go.Pie(
            labels=disp_labels, values=disp_revs, hole=0.6,
            marker=dict(colors=PALETTE[:4], line=dict(color="#12141a", width=3)),
        ))
        fig_disp.update_traces(textinfo="label+percent", textfont_size=11)
        dark_layout(fig_disp, 300, showlegend=False)
        fig_disp.update_layout(title=dict(text="Revenue by Dispatch Type", font=dict(size=13, color="#e8e9f0")))
        st.plotly_chart(fig_disp, width="stretch")

        dispatch_rows = []
        for k in disp_labels:
            rev       = data["dispatch_truth"][k]["revenue"]
            ord_count = data["dispatch_truth"][k]["orders"]
            rev_pct   = rev / disp_rev_total * 100
            ord_pct   = ord_count / disp_ord_total * 100
            aov_d     = rev / ord_count if ord_count > 0 else 0
            dispatch_rows.append({
                "Type":    k,
                "Revenue": f"£{rev:,.0f}",
                "Rev %":   f"{rev_pct:.1f}%",
                "Orders":  f"{ord_count:,}",
                "Ord %":   f"{ord_pct:.1f}%",
                "AOV":     f"£{aov_d:.2f}",
            })
        st.dataframe(pd.DataFrame(dispatch_rows), width="stretch", hide_index=True)
        st.markdown('<div class="insight-box">📦 Delivery leads on revenue (37.3%) but Dine In has stronger AOV. Collection is 3.8% of orders — smallest segment.</div>', unsafe_allow_html=True)

    with col2:
        ch_df  = pd.DataFrame(list(data["channels"].items()), columns=["Platform","Sales"])
        fig_ch = go.Figure(go.Bar(
            x=ch_df["Platform"], y=ch_df["Sales"],
            marker_color=PALETTE[:len(ch_df)], marker_line_width=0,
        ))
        dark_layout(fig_ch, 300)
        fig_ch.update_yaxes(tickprefix="£")
        fig_ch.update_layout(title=dict(text="Revenue by Platform", font=dict(size=13, color="#e8e9f0")))
        st.plotly_chart(fig_ch, width="stretch")

    st.markdown("---")
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**Platform Detail**")
        ch_total = sum(data["channels"].values())
        ch_table = []
        for i, (platform, sales) in enumerate(data["channels"].items()):
            ch_table.append({
                "#":          ["🥇","🥈","🥉","4","5"][i],
                "Platform":   platform,
                "Net Sales":  f"£{sales:,.0f}",
                "% Share":    f"{sales/ch_total*100:.1f}%",
            })
        st.dataframe(pd.DataFrame(ch_table), width="stretch", hide_index=True)
        st.markdown('<div class="insight-box">⚠️ Flipdish web orders only <b>0.3%</b> of revenue. Promoting direct web ordering avoids platform commissions — major opportunity.</div>', unsafe_allow_html=True)

    with col4:
        pay_df  = pd.DataFrame(list(data["payment"].items()), columns=["Method","Sales"])
        fig_pay = go.Figure(go.Pie(
            labels=pay_df["Method"], values=pay_df["Sales"], hole=0.55,
            marker=dict(colors=PALETTE, line=dict(color="#12141a", width=3)),
        ))
        fig_pay.update_traces(textinfo="label+percent", textfont_size=10)
        dark_layout(fig_pay, 260, showlegend=False)
        fig_pay.update_layout(title=dict(text="Payment Methods", font=dict(size=13, color="#e8e9f0")))
        st.plotly_chart(fig_pay, width="stretch")
        st.markdown('<div class="insight-box">⚠️ <b>£687 unpaid orders</b> needs investigation. 11.8% cash — ensure reconciliation is in place.</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Key Business Insights</div>', unsafe_allow_html=True)

    i1, i2, i3 = st.columns(3)
    i4, i5, i6 = st.columns(3)
    insights = [
        ("📈","Revenue Growth +403%","Business scaled dramatically vs prior period. £250K vs £49.8K previously — strong month-on-month growth continues."),
        ("🚗","Delivery Dominates","Delivery = 37.3% (£89.7K) of all revenue. Uber Eats alone at 25.4% — making it the #2 source after in-store POS."),
        ("🌙","Late Night Business","85% of revenue between 19:00–23:00. Essentially a late-night dessert destination. Morning hours near-zero."),
        ("📅","Weekend Warriors","Fri/Sat/Sun generate 55% of weekly revenue. Sunday alone averages £3,461/day vs Monday's £2,088."),
        ("🌐","Web Orders Underused","Flipdish web ordering at 0.3% (£630) is almost unused. Direct ordering avoids delivery platform commissions."),
        ("⚠️","Thursday Weak Spot","Thursdays consistently slowest with multiple sub-£1,700 days. Consider Thursday promotions or reduced hours."),
    ]
    for col, (icon, title, body) in zip([i1, i2, i3, i4, i5, i6], insights):
        col.markdown(f"""
        <div style="background:#12141a;border:1px solid #252836;border-radius:10px;padding:16px;height:100%">
            <div style="font-size:20px;margin-bottom:8px">{icon}</div>
            <div style="font-family:Syne,sans-serif;font-weight:700;font-size:13px;color:#e8e9f0;margin-bottom:6px">{title}</div>
            <div style="font-size:11px;color:#6b7094;line-height:1.6">{body}</div>
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# TAB 5 — EFFICIENCY
# ════════════════════════════════════════════════════════════════════
with tab5:
    # --- DEFAULTS ---
    peak_label  = "20:00 - 22:00"  # Sensible default peak
    quiet_label = "12:00 - 15:00"  # Sensible default quiet

    st.markdown('<div class="section-title">Labour Analytics & Staffing Efficiency</div>', unsafe_allow_html=True)

    if not data["shifts"]:
        st.info("🕒 Detailed shift data (detailed_rota_with_shifts.csv) empty or not parsed. Review file format.")
    else:
        shift_df  = pd.DataFrame(data["shifts"])

        personnel_dict = data.get("personnel", {})
        def get_rate(name):
            return personnel_dict.get(name, {}).get("Hourly Rate", 11.44)

        shift_df["cost"] = shift_df["name"].apply(get_rate)
        h_labour  = shift_df.groupby("hour")["cost"].sum().reindex(range(10, 24), fill_value=0)

        h_sales_list = []
        for h in range(24):
            h_str = format_hour_ampm(h)
            h_sales_list.append({"Hour": h_str, "Rev": data["hourly_live"].get(h, 0.0)})
        h_sales = pd.DataFrame(h_sales_list)

        labour_map = {format_hour_ampm(h): v for h, v in h_labour.items()}
        h_sales["Labour"] = h_sales["Hour"].map(labour_map).fillna(0)

        fig_eff = go.Figure()
        fig_eff.add_trace(go.Bar(
            x=h_sales["Hour"], y=h_sales["Rev"], name="Avg Hourly Sales £",
            marker_color="rgba(245,166,35,0.4)", marker_line_width=0,
        ))
        fig_eff.add_trace(go.Scatter(
            x=h_sales["Hour"], y=h_sales["Labour"], name="Avg Labour Cost £",
            line=dict(color=COLORS["red"], width=3, shape="spline"),
        ))
        dark_layout(fig_eff, 350, showlegend=True)
        fig_eff.update_yaxes(tickprefix="£")
        fig_eff.update_layout(title=dict(text="Sales Volume vs. Staffing Cost (Daily Average)", font=dict(size=14, color="#e8e9f0")))
        st.plotly_chart(fig_eff, width="stretch")
        st.markdown('<div class="insight-box">🔴 <b>Red line</b> = Labour Cost | 🟡 <b>Yellow bars</b> = Sales Revenue. Hours with high red lines but low bars indicate <b>Overstaffing</b>. Target: Revenue should be >3x Labour.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Orders per Staff Hour (OPSH)**")
        if data["shifts"]:
            shift_df2   = pd.DataFrame(data["shifts"])
            staff_per_h = shift_df2.groupby("hour")["name"].nunique().reindex(range(24), fill_value=0)

            h_ord_list = []
            for h in range(24):
                h_ord_list.append({"Hour": format_hour_ampm(h), "Rev": data["hourly_live"].get(h, 0.0), "h_int": h})
            h_ord = pd.DataFrame(h_ord_list).set_index("h_int")

            h_ord["staff"] = staff_per_h
            h_ord["OPSH"] = h_ord.apply(lambda r: r["Rev"] / r["staff"] if r["staff"] > 0 else 0, axis=1)
            
            # --- Dynamic Stats Calculation ---
            # Peak: Highest Rev/Staff between 11:00 and 23:00 (ignore late night anomalies)
            peak_h = h_ord[(h_ord.index >= 11) & (h_ord["staff"] > 0)]["OPSH"].idxmax()
            quiet_h = h_ord[(h_ord.index >= 11) & (h_ord["staff"] > 1)]["OPSH"].idxmin()
            
            peak_label = f"{format_hour_ampm(peak_h)} - {format_hour_ampm((peak_h+1)%24)}"
            quiet_label = f"{format_hour_ampm(quiet_h)} - {format_hour_ampm((quiet_h+1)%24)}"

            fig_ops = go.Figure(go.Scatter(
                x=h_ord["Hour"], y=h_ord["OPSH"],
                fill="tozeroy", line=dict(color=COLORS["accent4"], width=3),
                fillcolor="rgba(62,207,142,0.05)",
            ))
            dark_layout(fig_ops, 250)
            fig_ops.update_layout(title=dict(text="Efficiency: Orders per Staff Member/Hour", font=dict(size=12, color="#e8e9f0")))
            st.plotly_chart(fig_ops, width="stretch")
        else:
            st.warning("Requires shift times.")

    with c2:
        st.markdown("**Operational Stats**")
        st.markdown(f"""
        <div style="background:#1a1c24;padding:20px;border-radius:12px;border:1px solid #252836">
            <div style="color:#6b7094;font-size:11px;text-transform:uppercase">Peak Efficiency Window</div>
            <div style="font-family:Syne,sans-serif;font-size:24px;color:#3ecf8e;font-weight:800">{peak_label}</div>
            <div style="margin-top:15px;color:#6b7094;font-size:11px;text-transform:uppercase">Quiet Zone (Lowest Efficiency)</div>
            <div style="font-family:Syne,sans-serif;font-size:24px;color:#e05c5c;font-weight:800">{quiet_label}</div>
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# TAB 6 — FORECAST
# ════════════════════════════════════════════════════════════════════
with tab6:
    # Auto-compute next week date range from latest data date
    from datetime import timedelta
    _today       = pd.to_datetime(all_df["date"]).max()
    _next_mon    = _today + timedelta(days=(7 - _today.weekday()))
    _next_sun    = _next_mon + timedelta(days=6)
    _fc_label    = f"{_next_mon.strftime('%d %b')} – {_next_sun.strftime('%d %b %Y')}"
    _fc_aov      = (all_df["Net sales"].sum() / all_df["Orders"].replace(0,1).sum()).round(2) if "Orders" in all_df.columns else 0
    _fc_data_from = (all_df["date"].max() - timedelta(days=28)).strftime("%d %b")
    _fc_data_to   = all_df["date"].max().strftime("%d %b")

    st.markdown(f'<div class="section-title">Sales Forecast — Week of {_fc_label}</div>', unsafe_allow_html=True)

    f1, f2, f3 = st.columns(3)
    f1.metric("📐 Forecast Method",    "4-Week Rolling",  f"Same-day avg: {_fc_data_from} – {_fc_data_to}")
    # f2 and f3 filled after dynamic_forecast is computed below

    st.markdown("---")
    st.markdown('<div class="section-title">Manual Override — Adjust Forecast for Events & Promotions</div>', unsafe_allow_html=True)
    st.markdown('<div class="insight-box" style="margin-bottom:12px">Use overrides to adjust any day\'s forecast for known factors: bank holidays, local events, social campaigns, or operational changes. Enter a % uplift (positive) or reduction (negative).</div>', unsafe_allow_html=True)

    dow_map        = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    day_averages   = {}
    day_stds       = {}

    for day in dow_map:
        day_hist = all_df[all_df["day"] == day].sort_values("date", ascending=False)
        last_4   = day_hist.head(4)["Net sales"]
        if not last_4.empty:
            day_averages[day] = last_4.mean()
            day_stds[day]     = last_4.std() if len(last_4) > 1 else last_4.mean() * 0.1
        else:
            day_averages[day] = 0.0
            day_stds[day]     = 0.0

    dynamic_forecast = pd.Series(day_averages).reindex(dow_map, fill_value=0)
    dynamic_stds     = pd.Series(day_stds).reindex(dow_map, fill_value=0)

    last_7_days = all_df.sort_values("date", ascending=False).head(7)
    alert_triggered = False
    alerts_found    = []

    for _, row in last_7_days.iterrows():
        d_name = row["day"]
        actual = row["Net sales"]
        expected = day_averages.get(d_name, 0.0)
        if expected > 0:
            var = (actual - expected) / expected
            if abs(var) > 0.15:
                alert_triggered = True
                status = "🔥 PEAK OVER-TRADE" if var > 0 else "❄️ UNEXPECTED DROP"
                alerts_found.append(f"**{row['date'].strftime('%d %b')} ({d_name})**: {status} at **{var:+.1f}%** deviation (Actual £{actual:,.0f} vs Est. £{expected:,.0f})")

    if alert_triggered:
        with st.container():
            st.markdown(f'<div style="background:rgba(224,92,92,0.1);border:1px solid #e05c5c;padding:16px;border-radius:12px;margin-bottom:20px"><div style="color:#e05c5c;font-family:Syne,sans-serif;font-weight:800;font-size:13px;letter-spacing:1px;margin-bottom:8px">🚨 CRITICAL ACCURACY ALERTS — MODEL DEVIATION DETECTED</div>', unsafe_allow_html=True)
            for a in alerts_found[:3]:
                st.markdown(f'<div style="color:#6b7094;font-size:11px;margin-bottom:4px">{a}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    ov_cols      = st.columns(7)
    override_pct = {}
    f_days       = dow_map

    for i, day in enumerate(f_days):
        base_val = dynamic_forecast[day]
        with ov_cols[i]:
            st.markdown(f"<div style='font-size:11px;color:#6b7094;text-align:center;margin-bottom:4px'>{day[:3]}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:12px;color:#f5a623;text-align:center;margin-bottom:6px'>£{base_val:,.0f}</div>", unsafe_allow_html=True)
            override_pct[day] = st.number_input(
                label=day, value=0, min_value=-50, max_value=100, step=5,
                label_visibility="collapsed", key=f"ov_{day}",
                help=f"% adjustment for {day}",
            )

    adjusted_forecast_map = {
        day: round(dynamic_forecast[day] * (1 + override_pct[day] / 100), 2)
        for day in f_days
    }
    st.session_state["weekly_forecast"] = adjusted_forecast_map
    adjusted_forecast = list(adjusted_forecast_map.values())
    total_base_fc     = dynamic_forecast.sum()
    total_adjusted_fc = sum(adjusted_forecast)
    override_applied  = any(v != 0 for v in override_pct.values())

    # Fill f2/f3 metrics now that dynamic_forecast is known
    f2.metric("💰 Total Week Forecast", f"£{total_base_fc:,.0f}", "Sum of 7 rolling day averages")
    f3.metric("🎯 Forecast AOV",        f"£{_fc_aov:.2f}",         f"{len(all_df)}-day trailing average")

    if override_applied:
        oa1, oa2, oa3 = st.columns(3)
        oa1.metric("Base Forecast",     f"£{total_base_fc:,.0f}")
        oa2.metric("Adjusted Forecast", f"£{total_adjusted_fc:,.0f}",
                   f"{((total_adjusted_fc - total_base_fc)/total_base_fc*100):+.1f}%")
        oa3.metric("Override Impact",   f"£{total_adjusted_fc - total_base_fc:+,.0f}")

    override_reason = st.text_input(
        "Override reason (optional)",
        placeholder="e.g. Good Friday bank holiday, -20% expected Mon/Tue | Cardiff event +15% Fri",
        key="override_reason",
    )

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        f_days_labels = [d[:3] for d in f_days]
        f_base_vals   = list(dynamic_forecast.values)
        f_adj_vals    = list(adjusted_forecast_map.values())

        fig_fc = go.Figure()

        upper_band = [v + dynamic_stds[d] for d, v in zip(f_days, f_base_vals)]
        lower_band = [max(0, v - dynamic_stds[d]) for d, v in zip(f_days, f_base_vals)]

        fig_fc.add_trace(go.Scatter(
            name="Lower Bound", x=f_days_labels, y=lower_band,
            line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig_fc.add_trace(go.Scatter(
            name="Forecast Range (±1σ)", x=f_days_labels, y=upper_band,
            fill='tonexty', fillcolor="rgba(124,92,191,0.08)", line=dict(width=0),
            hoverinfo="skip"
        ))
        fig_fc.add_trace(go.Bar(
            name="Base Forecast", x=f_days_labels, y=f_base_vals,
            marker_color="rgba(124,92,191,0.35)",
            marker_line_color=COLORS["accent3"], marker_line_width=1,
        ))
        if override_applied:
            fig_fc.add_trace(go.Bar(
                name="Adjusted Forecast", x=f_days_labels, y=f_adj_vals,
                marker_color=COLORS["accent3"],
                marker_line_color=COLORS["accent3"], marker_line_width=1.5, marker_opacity=0.85,
            ))
        dark_layout(fig_fc, 300, showlegend=override_applied)
        fig_fc.update_yaxes(tickprefix="£")
        fig_fc.update_layout(
            title=dict(text="Next Week Revenue Forecast" + (" (Adjusted)" if override_applied else ""),
                       font=dict(size=13, color="#e8e9f0")),
            barmode="overlay",
        )
        st.plotly_chart(fig_fc, width="stretch")

    with col2:
        st.markdown("**Day-by-Day Forecast**")
        max_adj = max(adjusted_forecast_map.values())
        min_adj = min(adjusted_forecast_map.values())
        for day, adj_val in adjusted_forecast_map.items():
            pct        = adj_val / max_adj if max_adj > 0 else 0
            color      = COLORS["accent4"] if adj_val == max_adj else (COLORS["red"] if adj_val == min_adj else COLORS["accent"])
            delta_html = ""
            if override_pct.get(day, 0) != 0:
                delta_color = "#3ecf8e" if override_pct[day] > 0 else "#e05c5c"
                delta_html  = f' <span style="font-size:10px;color:{delta_color}">({override_pct[day]:+d}%)</span>'
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)">
                <div style="width:80px;font-size:12px;color:#6b7094">{day}</div>
                <div style="flex:1;height:6px;background:#252836;border-radius:3px;overflow:hidden">
                    <div style="width:{pct*100:.0f}%;height:100%;background:linear-gradient(90deg,{COLORS['accent3']},{COLORS['accent']});border-radius:3px"></div>
                </div>
                <div style="width:90px;text-align:right;font-family:Syne,sans-serif;font-weight:700;font-size:13px;color:{color}">£{adj_val:,.0f}{delta_html}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;margin-top:14px;padding-top:12px;border-top:1px solid #252836">
            <span style="font-size:12px;color:#6b7094;text-transform:uppercase;letter-spacing:1px">Total {'Adjusted ' if override_applied else ''}Forecast</span>
            <span style="font-family:Syne,sans-serif;font-weight:800;font-size:18px;color:#f5a623">£{total_adjusted_fc:,.0f}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Forecast vs Actual — Retrospective Comparison</div>', unsafe_allow_html=True)

    # --- DYNAMIC FORECAST RETROSPECTIVE ---
    # Merge historical predictions with live actuals from data["weekly"]
    # For now, we'll maintain the historical forecast targets, but pull 'Actual' from the live df
    history_mapping = {
        "Week of 9 Mar":  {"fc": 18800},
        "Week of 16 Mar": {"fc": 19100},
        "Week of 23 Mar": {"fc": 20500},
        "Week of 30 Mar": {"fc": 18900},
        "Week of 6 Apr":  {"fc": 18774},
    }
    
    # Normalize live actuals from data["weekly"] using datetime for robust matching
    live_weekly = {}
    for w in data["weekly"]:
        try:
            # standardise to "DD Mon" format (e.g. "09 Mar")
            dt = pd.to_datetime(w["week"] + " 2026", format="%d %b %Y", errors='coerce')
            if pd.notna(dt):
                live_weekly[dt.strftime("%d %b")] = w["net"]
        except: pass

    history_rows = []
    for label, target in history_mapping.items():
        # Normalize the history label for lookup
        match_key = label.replace("Week of ", "").strip()
        try:
            dt_hist = pd.to_datetime(match_key + " 2026", format="%d %b %Y", errors='coerce')
            norm_key = dt_hist.strftime("%d %b") if pd.notna(dt_hist) else match_key
        except:
            norm_key = match_key
            
        actual = live_weekly.get(norm_key)
        fc = target["fc"]
        
        if actual is not None and actual > 0:
            diff    = actual - fc
            acc_pct = (1 - abs(diff) / fc) * 100
            history_rows.append({
                "Week":       label,
                "Forecast £": f"£{fc:,.0f}",
                "Actual £":   f"£{actual:,.0f}",
                "Difference": f"£{diff:+,.0f}",
                "Accuracy %": f"{acc_pct:.1f}%",
                "Status":     "✅" if acc_pct >= 90 else ("⚠️" if acc_pct >= 75 else "❌"),
                "raw_fc":     fc,
                "raw_act":    actual
            })
        else:
            history_rows.append({
                "Week":       label,
                "Forecast £": f"£{fc:,.0f}",
                "Actual £":   "— (pending)",
                "Difference": "—",
                "Accuracy %": "—",
                "Status":     "🔮 Upcoming",
                "raw_fc":     fc,
                "raw_act":    None
            })
    
    st.dataframe(pd.DataFrame(history_rows).drop(columns=["raw_fc","raw_act"]), width="stretch", hide_index=True)

    completed = [(wk, e) for wk, e in FORECAST_HISTORY.items() if e["actual"] is not None]
    if completed:
        fc_chart_weeks  = [w for w, _ in completed]
        fc_chart_fc     = [e["forecast"] for _, e in completed]
        fc_chart_actual = [e["actual"]   for _, e in completed]

        fig_cmp = go.Figure()
        fig_cmp.add_trace(go.Scatter(
            x=fc_chart_weeks, y=fc_chart_fc, name="Forecast", mode="lines+markers",
            line=dict(color=COLORS["accent3"], width=2, dash="dot"), marker=dict(size=8),
        ))
        fig_cmp.add_trace(go.Scatter(
            x=fc_chart_weeks, y=fc_chart_actual, name="Actual", mode="lines+markers",
            line=dict(color=COLORS["accent4"], width=2.5), marker=dict(size=8),
        ))
        dark_layout(fig_cmp, 280, showlegend=True)
        fig_cmp.update_yaxes(tickprefix="£")
        fig_cmp.update_layout(title=dict(text="Forecast vs Actual — Weekly Comparison", font=dict(size=13, color="#e8e9f0")))
        st.plotly_chart(fig_cmp, width="stretch")

        valid_completed = [r for r in history_rows if r["raw_act"] is not None]
        if valid_completed:
            fc_chart_weeks  = [r["Week"] for r in valid_completed]
            fc_chart_fc     = [r["raw_fc"] for r in valid_completed]
            fc_chart_actual = [r["raw_act"] for r in valid_completed]

            acc_vals = [(1 - abs(r["raw_act"] - r["raw_fc"]) / r["raw_fc"]) * 100 for r in valid_completed]
            avg_acc  = sum(acc_vals) / len(acc_vals)

            fig_acc = go.Figure()
            fig_acc.add_trace(go.Scatter(
                x=fc_chart_weeks, y=acc_vals, name="Accuracy %", mode="lines+markers",
                line=dict(color=COLORS["accent"], width=2), marker=dict(size=7),
                fill="tozeroy", fillcolor="rgba(245,166,35,0.06)",
            ))
            fig_acc.add_hline(y=90, line_dash="dot", line_color=COLORS["accent4"],
                              annotation_text="90% target", annotation_position="right")
            dark_layout(fig_acc, 220, showlegend=False)
            fig_acc.update_yaxes(ticksuffix="%", range=[0, 110])
            fig_acc.update_layout(title=dict(text=f"Forecast Accuracy % by Week  (avg: {avg_acc:.1f}%)", font=dict(size=13, color="#e8e9f0")))
            st.plotly_chart(fig_acc, width="stretch")

            a1, a2, a3 = st.columns(3)
            a1.metric("📊 Average Accuracy",  f"{avg_acc:.1f}%",              "Across completed weeks")
            best_acc_idx  = acc_vals.index(max(acc_vals))
            a2.metric("🏆 Best Week",  fc_chart_weeks[best_acc_idx],  f"{max(acc_vals):.1f}% accurate")
            worst_acc_idx = acc_vals.index(min(acc_vals))
            a3.metric("⚠️ Worst Week", fc_chart_weeks[worst_acc_idx], f"{min(acc_vals):.1f}% accurate")

    st.markdown("---")
    st.markdown('<div class="section-title">Forecast Assumptions & Historical Performance</div>', unsafe_allow_html=True)
    g1, g2, g3 = st.columns(3)

    with g1:
        st.markdown("**📋 Model Assumptions**")
        _date_range_str = f"{_fc_data_from} – {_fc_data_to}"
        for row in [("Method","4-Week Same-Day Avg"),("Data Used", _date_range_str),
                    ("Data Points/Day","3–4 observations"),("Refund Adjusted","✅ Yes")]:
            st.markdown(f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="font-size:11px;color:#6b7094">{row[0]}</span><span style="font-size:12px;color:#e8e9f0">{row[1]}</span></div>', unsafe_allow_html=True)

    with g2:
        st.markdown("**⚠️ Override Factors Applied**")
        if override_applied:
            for day, pct in override_pct.items():
                if pct != 0:
                    col_c = "#3ecf8e" if pct > 0 else "#e05c5c"
                    st.markdown(f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="font-size:11px;color:#6b7094">{day}</span><span style="font-size:12px;font-weight:700;color:{col_c}">{pct:+d}%</span></div>', unsafe_allow_html=True)
            if override_reason:
                st.markdown(f'<div class="insight-box">📝 <b>Reason:</b> {override_reason}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="insight-box">No overrides applied. Base forecast in use.</div>', unsafe_allow_html=True)
            st.markdown('<div class="insight-box">📅 <b>Bank Holiday</b> — Check for Good Friday, Easter Monday impacts</div>', unsafe_allow_html=True)
            st.markdown('<div class="insight-box">🎉 <b>Local Events</b> — Cardiff events can significantly boost Fri/Sat</div>', unsafe_allow_html=True)

    with g3:
        st.markdown("**📊 Last 4 Weeks Actuals**")
        # Dynamic: pull from live weekly data
        _wk_hist = pd.DataFrame(data["weekly"]).tail(4) if data["weekly"] else pd.DataFrame()
        if not _wk_hist.empty:
            _wk_max = _wk_hist["net"].max()
            _wk_min = _wk_hist["net"].min()
            for _, _wr in _wk_hist.iterrows():
                _arrow = " ↑" if _wr["net"] == _wk_max else (" ↓" if _wr["net"] == _wk_min else "")
                _col   = "#3ecf8e" if _wr["net"] == _wk_max else ("#e05c5c" if _wr["net"] == _wk_min else "#e8e9f0")
                st.markdown(f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.04)"><span style="font-size:11px;color:#6b7094">Wk {_wr["week"]}</span><span style="font-family:Syne,sans-serif;font-weight:700;font-size:13px;color:{_col}">£{_wr["net"]:,.0f}{_arrow}</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="insight-box">High week-to-week variance. Treat forecast as baseline — apply override factors above.</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════
# TAB 7 — LABOUR REPORT
# ════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown('<div class="section-title">Labour Cost Analysis — Week: ' + data["week_label"] + ' &nbsp;|&nbsp; 👷 Responsible: DHIRAJ</div>', unsafe_allow_html=True)

    staff_df_live   = calc_staff_wages(data)
    summary_live    = calc_labour_summary(staff_df_live, forecast_rev=total_adjusted_fc)
    overlay_df_live = calc_hourly_overlay(data["hourly_live"], data=data)
    over_df_live    = calc_overstaffing(overlay_df_live)
    under_df_live   = calc_understaffing(overlay_df_live)
    day_df_live     = calc_day_labour(total_wages=summary_live["Staff Wages Total"])

    krow1_1, krow1_2, krow1_3 = st.columns(3)
    krow1_1.metric("👥 Staff Wages",       f"£{summary_live['Staff Wages Total']:,.2f}")
    krow1_2.metric("🧾 Other Costs",       f"£{summary_live['Other Costs Total']:,.2f}")
    krow1_3.metric("💷 Total Labour",      f"£{summary_live['Total Labour Cost']:,.2f}")

    st.markdown("<br>", unsafe_allow_html=True)

    krow2_1, krow2_2, krow2_3 = st.columns(3)
    krow2_1.metric("📈 Forecast Revenue",  f"£{summary_live['Forecast Week Revenue']:,.2f}")
    flag_val = summary_live['Labour % of Revenue']
    krow2_2.metric("📊 Labour %",          f"{flag_val}%",
                "🔴 OVER 30%" if flag_val > 30 else "✅ Within Target")
    krow2_3.metric("🔥 Max SBY Cost",      f"£{summary_live['SBY Max Additional Cost']:,.2f}")

    st.markdown("---")

    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.markdown("**👷 Staff Wages — Hours × Rate**")
        wage_display = staff_df_live.copy()
        wage_display["Weekly Wage (£)"] = wage_display["Weekly Wage (£)"].apply(lambda x: f"£{x:,.2f}")
        st.dataframe(wage_display, width="stretch", hide_index=True)

        total_wages = staff_df_live["Weekly Wage (£)"].sum()
        v_avg_rate = 8.69
        if data and "personnel" in data:
            v_rates = [float(p.get("Hourly Rate", 0)) for p in data["personnel"].values()]
            if v_rates: v_avg_rate = sum(v_rates) / len(v_rates)
        st.markdown(f'<div class="insight-box">💰 <b>Total Staff Wages: £{total_wages:,.2f}</b> &nbsp;|&nbsp; {len(staff_df_live)} staff members &nbsp;|&nbsp; Avg rate: £{v_avg_rate:.2f}/hr</div>', unsafe_allow_html=True)

    with col_b:
        st.markdown("**🧾 Other Weekly Costs**")
        other_costs_final = {
            "Kitchen Cleaner":  245.00, "Awais Bhai": 200.00, "Book Keeper": 60.00,
            "Anti Wage": 100.00, "Chintan Shopping": 60.00,
        }
        other_df_live = pd.DataFrame(
            [{"Cost Item": k, "Amount (£)": f"£{v:,.2f}"} for k, v in other_costs_final.items()]
        )
        st.dataframe(other_df_live, width="stretch", hide_index=True)

        st.markdown("**🔥 SBY Staff — Max Call-In**")
        sby_rows = []
        for name, v in SBY_STAFF.items():
            sby_rows.append({
                "Name":          name,
                "Max Hrs":       v["max_sby_hrs"],
                "Rate (£/hr)":   f"£{v['hourly_rate']:.2f}",
                "Max Cost (£)":  f"£{v['max_sby_hrs'] * v['hourly_rate']:.2f}",
            })
        st.dataframe(pd.DataFrame(sby_rows), width="stretch", hide_index=True)
        st.markdown(f'<div class="insight-box">⚠️ SBY max additional cost: <b>£{summary_live["SBY Max Additional Cost"]:.2f}</b> — only incurred if all SBY staff called in</div>', unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("**📅 Day-by-Day Labour vs Forecast Revenue**")
    day_display = day_df_live.copy()

    def color_labour_status(val):
        if "🔴" in str(val): return "color: #FF4444; font-weight: bold"
        if "✅" in str(val):  return "color: #3ECF8E; font-weight: bold"
        return ""

    st.dataframe(day_display.style.map(color_labour_status, subset=["Status"]),
                 width="stretch", hide_index=True)
    st.markdown('<div class="insight-box">⚠️ Labour threshold: 30% of revenue. SBY staff not included above — add if called in. Call SBY by 19:00 on days with forecast revenue ≥ £3,000.</div>', unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("**🕐 Hour-by-Hour Revenue vs Staff Cost Overlay**")

    fig_overlay = go.Figure()
    fig_overlay.add_trace(go.Bar(
        x=overlay_df_live["Hour"], y=overlay_df_live["Avg Revenue (£)"],
        name="Avg Revenue £", marker_color="rgba(245,166,35,0.45)", marker_line_width=0,
    ))
    fig_overlay.add_trace(go.Scatter(
        x=overlay_df_live["Hour"], y=overlay_df_live["Total Staff Cost (£)"],
        name="Total Staff Cost £", mode="lines+markers",
        line=dict(color=COLORS["red"], width=2.5, shape="spline"),
        marker=dict(size=6),
    ))
    fig_overlay.add_trace(go.Scatter(
        x=overlay_df_live["Hour"], y=overlay_df_live["Total Staff"],
        name="Total Staff (headcount)", mode="lines+markers",
        line=dict(color=COLORS["accent4"], width=1.5, dash="dot"),
        marker=dict(size=5),
        yaxis="y2",
    ))
    dark_layout(fig_overlay, 380, showlegend=True)
    fig_overlay.update_layout(
        title=dict(text="Hourly Revenue vs Staff Cost (91-day daily avg)", font=dict(size=14, color="#e8e9f0")),
        yaxis=dict(title="£", tickprefix="£", gridcolor="rgba(255,255,255,0.06)"),
        yaxis2=dict(title="Headcount", overlaying="y", side="right", showgrid=False,
                    tickfont=dict(color=COLORS["accent4"])),
    )
    st.plotly_chart(fig_overlay, width="stretch")

    st.markdown("---")

    flag_col1, flag_col2 = st.columns(2)

    with flag_col1:
        st.markdown("**🔴 Overstaffing Flags**")
        if len(over_df_live) > 0:
            st.dataframe(over_df_live, width="stretch", hide_index=True)
            st.markdown(f'<div class="insight-box">🔴 <b>{len(over_df_live)} overstaffed hour(s)</b> detected. Staff cost exceeds revenue generated. Recommend delaying morning shift starts or closing earlier on quiet days.</div>', unsafe_allow_html=True)
        else:
            st.success("✅ No overstaffing detected this week.")

    with flag_col2:
        st.markdown("**🟡 Understaffing Flags**")
        if len(under_df_live) > 0:
            st.dataframe(under_df_live, width="stretch", hide_index=True)
            st.markdown(f'<div class="insight-box">🟡 <b>{len(under_df_live)} understaffed hour(s)</b> detected. Peak revenue hours with insufficient cover. Call SBY staff in early.</div>', unsafe_allow_html=True)
        else:
            st.success("✅ No critical understaffing detected — peak hours well covered.")

    st.markdown("---")

    with st.expander("📋 Full Hourly Overlay Table — All Hours"):
        st.dataframe(overlay_df_live, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown('<div class="section-title">Export Full Labour Report</div>', unsafe_allow_html=True)
    st.markdown('<div class="insight-box" style="margin-bottom:12px">Click below to generate and download the full 6-sheet Excel labour report with dark theme formatting, KPI boxes, overstaffing flags, understaffing flags, and SBY tracker.</div>', unsafe_allow_html=True)

    if st.button("📊 Generate & Download Excel Labour Report", width="content"):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name
        build_labour_workbook(data, tmp_path)
        with open(tmp_path, "rb") as f:
            xlsx_bytes = f.read()
        os.unlink(tmp_path)
        st.download_button(
            label="⬇️ Download chocoberry_labour_report.xlsx",
            data=xlsx_bytes,
            file_name="chocoberry_labour_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )


# ════════════════════════════════════════════════════════════════════
# TAB 8 — ROTA BUILDER
# ════════════════════════════════════════════════════════════════════
with tab8:
    st.markdown('<div class="page-title">Intelligent Rota Builder</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Automated, constraint-based scheduling with fairness balancing.</div>', unsafe_allow_html=True)

    try:
        from rota_engine import RotaEngine
        engine = RotaEngine()
    except (ImportError, ModuleNotFoundError):
        st.warning("⚠️ rota_engine.py not found.")
        st.stop()

    # Define w_start FIRST before anything references it
    w_start = date.today() + timedelta(days=(7 - date.today().weekday()) % 7)

    # Check if week changed and clear stale rota
    if "last_w_start" not in st.session_state or st.session_state["last_w_start"] != w_start:
        st.session_state["last_w_start"] = w_start
        for k in ["active_rota", "active_rota_summary", "active_rota_warnings"]:
            if k in st.session_state:
                del st.session_state[k]

    rota_path = os.path.join(os.getcwd(), f"Rota week {w_start.strftime('%d %b %Y')}", "detailed_rota_with_shifts.csv")

    if os.path.exists(rota_path):
        st.success(f"🟢 Live Rota Detected for week of {w_start.strftime('%d %b')}.")
    else:
        st.info("⚪ No Live Rota yet. Use the generator below.")

    with st.expander("👤 Staff Profile Management — Single Source of Truth", expanded=False):
        st.markdown('<div class="insight-box">Edit staff availability, roles (Senior/Junior), and target hours below. These settings power the auto-scheduler.</div>', unsafe_allow_html=True)
        profiles_path = os.path.join(os.getcwd(), "staff_profiles.csv")
        if os.path.exists(profiles_path):
            curr_prof_df = pd.read_csv(profiles_path)
            edited_df = st.data_editor(curr_prof_df, width="stretch", num_rows="dynamic", hide_index=True, key="prof_editor")
            if st.button("💾 Save Profile Changes", width="content"):
                edited_df.to_csv(profiles_path, index=False, encoding="utf-8-sig")
                st.success("✅ Staff profiles updated successfully.")
                st.cache_data.clear()
        else:
            st.error("Missing staff_profiles.csv")

    st.markdown("---")
    st.markdown('<div class="section-title">Schedule Generation</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.markdown("**1. Configure Parameters**")
        w_start = st.date_input("Week Start Date (Monday recommended)", value=w_start)
        w_end = w_start + timedelta(days=6)
        st.markdown(f'<div style="background:rgba(245,166,35,0.1);border-radius:10px;padding:10px 15px;border:1px solid #f5a623;color:#f5a623;font-weight:700;font-size:14px;margin-top:10px;text-align:center">📅 {w_start.strftime("%d %b")} ➜ {w_end.strftime("%d %b %Y")}</div>', unsafe_allow_html=True)
        balance_bias = st.slider("Fairness Balance Bias", 0.0, 1.0, 0.5)

    with c2:
        st.markdown("**2. Generate**")
        if st.button("⚡ Generate Weekly Rota", width="stretch", type="primary"):
            try:
                engine.load_staff()
                engine.load_shifts()
            except FileNotFoundError as e:
                st.error(f"Missing file: {e}")
                st.stop()
            with st.spinner("Solving constraints..."):
                engine.load_historical_hours(weeks_back=3)
                new_rota = engine.generate_week(week_start=w_start)
                st.session_state["active_rota"] = new_rota
                st.session_state["active_rota_summary"] = engine.get_hours_summary()
                st.session_state["active_rota_warnings"] = list(engine.warnings)
                st.session_state["last_w_start"] = w_start
            st.success(f"✅ {len(new_rota)} shift assignments generated.")

        if st.button("🚀 Smart Rota (Forecast-Matched)", width="stretch"):
            try:
                engine.load_staff()
                engine.load_shifts()
            except FileNotFoundError as e:
                st.error(f"Missing file: {e}")
                st.stop()
            with st.spinner("Scaling to forecast..."):
                _fs = st.session_state.get("weekly_forecast")
                engine.load_historical_hours(weeks_back=3)
                new_rota = engine.generate_week(
                    week_start=w_start,
                    forecast_scaling=_fs
                )
                st.session_state["active_rota"] = new_rota
                st.session_state["active_rota_summary"] = engine.get_hours_summary()
                st.session_state["active_rota_warnings"] = list(engine.warnings)
                st.session_state["last_w_start"] = w_start
            st.success(f"✅ Smart Rota generated.")

    with c3:
        st.markdown("**3. Cost Estimate**")
        if "active_rota" in st.session_state:
            cost = engine.estimate_weekly_cost(st.session_state["active_rota"])
            st.markdown(f'<div class="status-box">💎 Weekly Wage Est: <b>£{cost["total"]:,.2f}</b></div>', unsafe_allow_html=True)

    if "active_rota" in st.session_state:
        st.markdown("---")
        st.markdown('<div class="section-title">Visual Weekly Schedule</div>', unsafe_allow_html=True)

        rota_df = st.session_state["active_rota"]

        if rota_df.empty:
            st.info("🕒 No shifts scheduled for the selected week/criteria.")
        else:
            grid_pivot = rota_df.pivot_table(
                index=["Name", "Role", "Department"],
                columns="Day",
                values="Shift",
                aggfunc=lambda x: " | ".join(x)
            ).reset_index()

            grid_pivot["role_sort"] = grid_pivot["Role"].map({"Senior": 0, "Junior": 1})
            grid_pivot = grid_pivot.sort_values(["Department", "role_sort"]).drop(columns=["role_sort"])

            day_cols = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            final_cols = ["Name","Role","Department"] + [d for d in day_cols if d in grid_pivot.columns]
            grid_display = grid_pivot[final_cols]

            st.dataframe(grid_display, width="stretch", hide_index=True)

            m1, m2 = st.columns(2)
            with m1:
                st.markdown("**🔍 Fairness & Hours Report**")
                summary = st.session_state.get("active_rota_summary", pd.DataFrame())
                st.dataframe(summary, height=300, width="stretch", hide_index=True)

            with m2:
                st.markdown("**⚠️ Constraints Check (Warnings)**")
                warnings_list = st.session_state.get("active_rota_warnings", [])
                if warnings_list:
                    for w in warnings_list:
                        st.warning(w)
                else:
                    st.success("✅ All shift constraints (Senior presence, headcount) satisfied.")

            st.markdown("---")
            c_push, c_down = st.columns(2)
            with c_push:
                if st.button("🚀 Push to Tab 7 (Commit to Live Data)", width="stretch"):
                    output_dir = os.path.join(os.getcwd(), f"Rota week {w_start.strftime('%d %b %Y')}")
                    if not os.path.exists(output_dir): os.makedirs(output_dir)

                    rota_df.to_csv(os.path.join(output_dir, "detailed_rota_with_shifts.csv"), index=False)
                    st.cache_data.clear() # Force Tab 7 to see the new file
                    st.balloons()
                    st.success(f"✅ Rota deployed to: {output_dir}")
            
            with c_down:
                csv_bytes = rota_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="⬇️ Download Rota CSV",
                    data=csv_bytes,
                    file_name=f"chocoberry_rota_{w_start.strftime('%d_%b_%Y')}.csv",
                    mime="text/csv",
                    width="stretch"
                )


# ════════════════════════════════════════════════════════════════════
# TAB 9 — INVENTORY & COGS  *** FULL REPLACEMENT ***
# ════════════════════════════════════════════════════════════════════
with tab9:
    st.markdown('<div class="page-title">Inventory & COGS Master</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Recipe cards · Auto stock deduction · Food cost % · Reorder alerts</div>', unsafe_allow_html=True)

    if _recipe_engine is None:
        st.error("recipe_engine.py not found. Place it in the same folder as app_dashboard.py.")
    else:
        eng = _recipe_engine

        # ── KPI row ────────────────────────────────────────────────────────────
        summary_inv = eng.weekly_stock_summary()
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("🥦 Ingredients",     summary_inv["total_ingredients"])
        k2.metric("🚨 Reorder Alerts",  summary_inv["reorder_alerts"],
                  delta="needs action" if summary_inv["reorder_alerts"] > 0 else "all ok",
                  delta_color="inverse" if summary_inv["reorder_alerts"] > 0 else "normal")
        k3.metric("🍕 Avg Food Cost",   f"{summary_inv['avg_food_cost_pct']}%")
        k4.metric("💷 Weekly COGS",     f"£{summary_inv['weekly_cogs']:,.2f}")
        k5.metric("🗑️ Weekly Waste",    f"£{summary_inv['weekly_waste_cost']:,.2f}")

        st.markdown("---")

        inv_tabs = st.tabs([
            "📋 Stock Levels", "🍕 Recipe Cards", "📊 Profitability",
            "⬇️ Auto-Deduct from Sales", "📦 Purchase Orders"
        ])

        # ── Tab: Stock Levels ─────────────────────────────────────────────────
        with inv_tabs[0]:
            st.markdown("**Current Stock Levels**")
            ings = eng.get_ingredients()
            alerts_inv = eng.get_reorder_alerts()

            if alerts_inv:
                st.markdown(f"""
                <div style="background:rgba(224,92,92,0.1);border:1px solid #e05c5c;
                            padding:12px 16px;border-radius:8px;margin-bottom:12px">
                    🚨 <b style="color:#e05c5c">{len(alerts_inv)} items below reorder point</b>
                </div>""", unsafe_allow_html=True)

            if ings:
                ing_df = pd.DataFrame(ings)
                ing_df["Status"] = ing_df.apply(
                    lambda r: "🚨 REORDER" if r["current_stock"] <= r["reorder_point"]
                    else ("⚠️ Low" if r["current_stock"] <= r["reorder_point"] * 1.5
                    else "✅ OK"), axis=1
                )
                ing_df["unit_cost"] = ing_df["unit_cost"].apply(lambda x: f"£{x:.4f}")
                ing_df["current_stock"] = ing_df["current_stock"].round(3)
                ing_df.columns = ["ID","Name","Unit","Unit Cost","Supplier",
                                   "Current Stock","Reorder Point","Status"]
                st.dataframe(ing_df.drop(columns=["ID"]), width="stretch", hide_index=True)
            else:
                st.info("No ingredients yet. Add them in the Recipe Cards tab.")

            st.markdown("---")
            st.markdown("**Manual Stock Adjustment (After Physical Count)**")
            if ings:
                sel_ing = st.selectbox("Ingredient", [i["name"] for i in ings], key="stock_adj")
                new_qty = st.number_input("New physical stock count", min_value=0.0, step=0.1, key="new_qty")
                if st.button("Update Stock", key="upd_stock"):
                    ing_id = next(i["id"] for i in ings if i["name"] == sel_ing)
                    eng.set_opening_stock(ing_id, new_qty)
                    st.success(f"✅ {sel_ing} updated to {new_qty}")
                    st.rerun()

        # ── Tab: Recipe Cards ─────────────────────────────────────────────────
        with inv_tabs[1]:
            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.markdown("**Add / Edit Ingredient**")
                with st.form("ing_form"):
                    ing_name   = st.text_input("Ingredient Name *")
                    ing_unit   = st.selectbox("Unit", ["kg","g","litre","ml","each","portion","pack"])
                    ing_cost   = st.number_input("Unit Cost (£)", min_value=0.0, step=0.01)
                    ing_supp   = st.text_input("Supplier")
                    ing_stock  = st.number_input("Opening Stock", min_value=0.0, step=0.1)
                    ing_reord  = st.number_input("Reorder Point", min_value=0.0, step=0.1)
                    if st.form_submit_button("Save Ingredient"):
                        if ing_name:
                            eng.upsert_ingredient(ing_name, ing_unit, ing_cost,
                                                   ing_supp, ing_stock, ing_reord)
                            st.success(f"✅ {ing_name} saved.")
                            st.rerun()

                st.markdown("---")
                st.markdown("**Add Menu Item**")
                with st.form("item_form"):
                    fd_name    = st.text_input("Flipdish Name (exact match) *")
                    disp_name  = st.text_input("Display Name")
                    item_cat   = st.selectbox("Category", ["Waffles","Crepes","Drinks",
                                                            "Sundaes","Hot Food","Extras","Other"])
                    sell_price = st.number_input("Selling Price (£)", min_value=0.0, step=0.5)
                    if st.form_submit_button("Save Menu Item"):
                        if fd_name:
                            eng.upsert_menu_item(fd_name, disp_name, item_cat, sell_price)
                            st.success(f"✅ {fd_name} saved.")
                            st.rerun()

            with col_right:
                st.markdown("**Build / Update Recipe Card**")
                items = eng.get_menu_items()
                ings  = eng.get_ingredients()

                if not items:
                    st.info("Add a menu item first (left panel).")
                elif not ings:
                    st.info("Add ingredients first (left panel).")
                else:
                    sel_item = st.selectbox("Menu Item", [i["display_name"] for i in items])
                    item_id  = next(i["id"] for i in items if i["display_name"] == sel_item)

                    existing = eng.get_recipe(item_id)
                    st.markdown(f"**Current recipe** ({len(existing)} ingredients, "
                                f"cost: £{sum(r['line_cost'] for r in existing):.4f})")
                    if existing:
                        rc_df = pd.DataFrame(existing)[["name","quantity","unit","line_cost"]]
                        rc_df.columns = ["Ingredient","Qty","Unit","Cost £"]
                        rc_df["Cost £"] = rc_df["Cost £"].apply(lambda x: f"£{x:.4f}")
                        st.dataframe(rc_df, width="stretch", hide_index=True)

                    st.markdown("**Add ingredient to recipe**")
                    with st.form("recipe_form"):
                        sel_ing  = st.selectbox("Ingredient", [i["name"] for i in ings])
                        qty      = st.number_input("Quantity per portion", min_value=0.001,
                                                   step=0.001, format="%.3f")
                        if st.form_submit_button("Add to Recipe"):
                            ing_id   = next(i["id"] for i in ings if i["name"] == sel_ing)
                            new_ings = [{"ingredient_id": r["ingredient_id"],
                                         "quantity": r["quantity"]} for r in existing]
                            new_ings.append({"ingredient_id": ing_id, "quantity": qty})
                            eng.set_recipe(item_id, new_ings)
                            st.success(f"✅ Added {sel_ing} to {sel_item}.")
                            st.rerun()

                    if existing and st.button("🗑️ Clear Full Recipe", key="clr_recipe"):
                        eng.set_recipe(item_id, [])
                        st.rerun()

                    st.markdown("---")
                    st.markdown("**Archive / Hide Menu Item**")
                    st.info("Deactivating an item stops it from appearing in dropdowns but keeps historical data.")
                    if st.button("📁 Archive this Menu Item", width="stretch"):
                        # Add a quick toggle in the engine or just use direct SQL
                        with sqlite3.connect(RECIPE_DB_PATH) as conn:
                            conn.execute("UPDATE menu_items SET active = 0 WHERE id = ?", (item_id,))
                        st.warning(f"Item '{sel_item}' has been archived.")
                        st.rerun()

            # ── CSV bulk import ─────────────────────────────────────────────
            st.markdown("---")
            st.markdown("**Bulk Import via CSV**")
            c1_inv, c2_inv = st.columns(2)
            with c1_inv:
                up_ing = st.file_uploader("Import Ingredients CSV",
                                          type="csv", key="ing_csv")
                if up_ing:
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
                        tmp.write(up_ing.read())
                        tmp_path = tmp.name
                    n = eng.import_ingredients_csv(tmp_path)
                    st.success(f"✅ Imported {n} ingredients.")
                    os.unlink(tmp_path)
            with c2_inv:
                up_items = st.file_uploader("Import Menu Items CSV",
                                            type="csv", key="items_csv")
                if up_items:
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
                        tmp.write(up_items.read())
                        tmp_path = tmp.name
                    n = eng.import_menu_items_csv(tmp_path)
                    st.success(f"✅ Imported {n} menu items.")
                    os.unlink(tmp_path)
            st.markdown('<div class="insight-box">CSV format — Ingredients: <b>name, unit, unit_cost, supplier, opening_stock, reorder_point</b> &nbsp;|&nbsp; Menu items: <b>flipdish_name, display_name, category, selling_price</b></div>', unsafe_allow_html=True)

        # ── Tab: Profitability ────────────────────────────────────────────────
        with inv_tabs[2]:
            st.markdown("**Menu Profitability — Star / Dog Matrix**")
            
            items_prof = eng.calc_item_profitability()

            if not items_prof:
                st.info("Add menu items with recipe cards and selling prices to see profitability.")
            else:
                for i in items_prof:
                    i["volume"] = 0
                    i["total_cogs"] = 0.0

                # Load sales volume safely
                sv_path = os.path.join(os.getcwd(), "Menu Item Report data", "Most sold items.csv")
                volume_loaded = False
                if os.path.exists(sv_path):
                    try:
                        sv_df = pd.read_csv(sv_path)
                        # Find name and qty columns robustly
                        name_col = next(
                            (c for c in sv_df.columns if any(x in c.lower() for x in ["item","name"])),
                            sv_df.columns[0]
                        )
                        qty_col = next(
                            (c for c in sv_df.columns if any(x in c.lower() for x in ["sold","qty","quantity","count","orders","total"])),
                            None
                        )
                        if qty_col:
                            # Clean and build lookup: lowercase stripped name -> int qty
                            vol_map = {}
                            for _, r in sv_df.iterrows():
                                raw_name = str(r[name_col]).strip()
                                raw_qty  = str(r[qty_col]).replace(",","").replace("£","").strip()
                                try:
                                    vol_map[raw_name.lower()] = int(float(raw_qty))
                                except (ValueError, TypeError):
                                    pass
                            
                            # Merge by fuzzy lowercase match
                            matched = 0
                            for i in items_prof:
                                key = str(i.get("flipdish_name","")).strip().lower()
                                disp_key = str(i.get("menu_item","")).strip().lower()
                                vol = vol_map.get(key) or vol_map.get(disp_key) or 0
                                i["volume"] = vol
                                i["total_cogs"] = round(vol * i["ingredient_cost"], 2)
                                if vol > 0:
                                    matched += 1
                            
                            volume_loaded = matched > 0
                            if not volume_loaded:
                                st.warning(
                                    f"⚠️ Sales file loaded ({len(vol_map)} items) but 0 names matched recipe items. "
                                    f"Check that Flipdish item names in your recipe DB match the CSV exactly. "
                                    f"Example CSV name: '{next(iter(vol_map))}' | "
                                    f"Example recipe name: '{items_prof[0].get('flipdish_name','?')}'"
                                )
                    except Exception as e:
                        st.warning(f"Could not load sales volume: {e}")

                prof_df = pd.DataFrame(items_prof)

                total_volume   = int(prof_df["volume"].sum())
                total_cogs_all = round(prof_df["total_cogs"].sum(), 2)
                with_rec       = [i for i in items_prof if i["has_recipe"]]

                p1, p2, p3, p4 = st.columns(4)
                p1.metric("Items with recipe",  len(with_rec))
                p2.metric("Total COGS Est.",    f"£{total_cogs_all:,.2f}",
                          f"{total_volume:,} units sold" if volume_loaded else "⚠️ no volume data")
                p3.metric("Avg GP %",
                          f"{sum(i['gp_pct'] for i in with_rec)/len(with_rec):.1f}%" if with_rec else "—")
                p4.metric("Avg food cost %",
                          f"{sum(i['food_cost_pct'] for i in with_rec)/len(with_rec):.1f}%" if with_rec else "—")


                # --- SCATTER CHART ---
                if not prof_df.empty and total_volume > 0:
                    matrix_fig = px.scatter(
                        prof_df[prof_df["volume"] > 0], 
                        x="volume", y="gp_pct", 
                        text="menu_item", color="category",
                        hover_data=["selling_price", "total_cogs"],
                        labels={"volume":"Sales Volume (Popularity)", "gp_pct":"Gross Profit % (Profitability)"},
                        title="Star / Dog Matrix: Popularity vs Profitability",
                        template="plotly_dark"
                    )
                    matrix_fig.update_traces(textposition='top center')
                    # Quadrant lines
                    med_vol = prof_df[prof_df["volume"] > 0]["volume"].median()
                    med_gp  = prof_df[prof_df["volume"] > 0]["gp_pct"].median()
                    matrix_fig.add_hline(y=med_gp, line_dash="dash", line_color="gray", annotation_text="Profitability Median")
                    matrix_fig.add_vline(x=med_vol, line_dash="dash", line_color="gray", annotation_text="Volume Median")
                    
                    st.plotly_chart(matrix_fig, width="stretch")
                else:
                    st.info("💡 Note: Missing sales volume data. To view the Profitability Matrix (Stars/Dogs), please ensure 'Most sold items.csv' is present in 'Menu Item Report data'. Showing table only.")

                disp = prof_df[["menu_item","category","volume","selling_price",
                                 "ingredient_cost","total_cogs","gp_pct"]].copy()
                disp.columns = ["Item","Category","Vol","Price £","Unit Cost £","Total COGS £","GP %"]
                disp["Price £"]     = disp["Price £"].apply(lambda x: f"£{x:.2f}")
                disp["Unit Cost £"] = disp["Unit Cost £"].apply(lambda x: f"£{x:.4f}")
                disp["Total COGS £"] = disp["Total COGS £"].apply(lambda x: f"£{x:,.2f}")
                disp["GP %"]        = disp["GP %"].apply(lambda x: f"{x:.1f}%")
                st.dataframe(disp.sort_values("Vol", ascending=False), width="stretch", hide_index=True)

                if os.path.exists(sv_path):
                    st.caption(f"💡 Based on latest Menu Item Report in folder (Auto-detected). Total units tracked: {total_volume:,}")
                else:
                    st.warning("⚠️ No 'Most sold items.csv' found in 'Menu Item Report data' folder. Volume analysis disabled.")


                import tempfile as _tmp
                if st.button("📥 Export Profitability CSV"):
                    with _tmp.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                        eng.export_profitability_csv(tmp.name)
                        csv_bytes = open(tmp.name, "rb").read()
                    st.download_button("⬇️ Download", csv_bytes,
                                       file_name="chocoberry_profitability.csv",
                                       mime="text/csv")

        # ── Tab: Auto-Deduct from Sales ───────────────────────────────────────
        with inv_tabs[3]:
            st.markdown("**Auto-Deduct Ingredients from Flipdish Sales Data**")
            st.markdown('<div class="insight-box">Upload the Flipdish <b>Menu Items Report</b> (CSV) and the engine will automatically deduct ingredient quantities from stock based on your recipe cards.</div>', unsafe_allow_html=True)

            up_sales = st.file_uploader("Upload Flipdish Menu Items CSV",
                                        type="csv", key="sales_deduct")
            deduct_date = st.date_input("Sales Date", value=datetime.now().date())

            if up_sales:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
                    tmp.write(up_sales.read())
                    tmp_path = tmp.name

                try:
                    sales_raw = pd.read_csv(tmp_path)
                    os.unlink(tmp_path)

                    name_col = next((c for c in sales_raw.columns
                                     if any(x in c.lower() for x in ["item","name","product"])),
                                    sales_raw.columns[0])
                    qty_col  = next((c for c in sales_raw.columns
                                     if any(x in c.lower() for x in ["sold","qty","quantity","count","orders"])),
                                    sales_raw.columns[1] if len(sales_raw.columns) > 1 else sales_raw.columns[0])

                    st.markdown(f"Detected: **item column** = `{name_col}`, **quantity column** = `{qty_col}`")
                    st.dataframe(sales_raw[[name_col, qty_col]].head(10), hide_index=True)

                    if st.button("▶ Run Auto-Deduction", type="primary"):
                        sales_list = [
                            {"item_name": str(row[name_col]), "units_sold": int(row[qty_col])}
                            for _, row in sales_raw.iterrows()
                            if pd.notna(row[qty_col]) and int(row[qty_col]) > 0
                        ]
                        result = eng.deduct_from_sales(sales_list,
                                                       deduct_date.strftime("%Y-%m-%d"))

                        st.success(f"✅ Processed {result['items_processed']} items. "
                                   f"Total COGS: £{result['total_cogs']:,.2f}")

                        if result["items_skipped"]:
                            st.warning(f"Skipped {len(result['items_skipped'])} items "
                                       f"(no recipe card or not in menu): "
                                       f"{', '.join(result['items_skipped'][:5])}")

                        st.markdown("**Stock levels have been updated. Check Stock Levels tab.**")
                        st.rerun()

                except Exception as e:
                    st.error(f"Could not parse CSV: {e}")

            else:
                st.markdown('<div class="insight-box">💡 <b>How this works:</b> Flipdish exports a "Menu Items" report showing items sold per item. This engine maps each item name to your recipe card, multiplies by units sold, and deducts every ingredient from current stock automatically.</div>', unsafe_allow_html=True)

        # ── Tab: Purchase Orders ──────────────────────────────────────────────
        with inv_tabs[4]:
            st.markdown("**Purchase Order Generator**")
            alerts_po = eng.get_reorder_alerts()

            if not alerts_po:
                st.success("✅ All ingredients above reorder point. No PO needed.")
            else:
                st.markdown(f"**{len(alerts_po)} items need reordering:**")

                po_df = pd.DataFrame(alerts_po)
                po_df["qty_to_order"] = (po_df["reorder_point"] * 3 - po_df["current_stock"]).round(2)
                po_df["qty_to_order"] = po_df["qty_to_order"].clip(lower=0)
                po_df["est_cost"] = (po_df["qty_to_order"] * po_df["unit_cost"]).round(2)

                st.dataframe(
                    po_df[["name","unit","current_stock","reorder_point","qty_to_order","est_cost","supplier"]].rename(
                        columns={"name":"Ingredient","unit":"Unit",
                                 "current_stock":"In Stock","reorder_point":"Reorder At",
                                 "qty_to_order":"Order Qty","est_cost":"Est Cost £","supplier":"Supplier"}
                    ),
                    width="stretch", hide_index=True
                )

                total_po = po_df["est_cost"].sum()
                st.metric("Estimated PO Total", f"£{total_po:,.2f}")

                po_text  = f"CHOCOBERRY — PURCHASE ORDER\n"
                po_text += f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}\n"
                po_text += "=" * 50 + "\n"
                for _, r in po_df.iterrows():
                    po_text += (f"  {r['name']:<30} {r['qty_to_order']:>8.2f} {r['unit']:<8}"
                                f"  Est: £{r['est_cost']:.2f}  [{r['supplier']}]\n")
                po_text += "=" * 50 + "\n"
                po_text += f"TOTAL ESTIMATED COST: £{total_po:,.2f}\n"

                st.download_button(
                    "⬇️ Download PO as Text File",
                    po_text.encode("utf-8"),
                    file_name=f"chocoberry_po_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                )



# ════════════════════════════════════════════════════════════════════
# TAB 10 — WASTE LOG & SHELF LIFE
# ════════════════════════════════════════════════════════════════════
with tab10:
    st.markdown('<div class="page-title">Waste Log & Expiry Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Predictive waste management and logged loss tracking (Integrated with Recipe Engine).</div>', unsafe_allow_html=True)

    w1, w2 = st.columns([1, 1])
    eng = _recipe_engine

    with w1:
        st.markdown("**🛡️ Shelf-Life & Waste Risk Matrix**")
        shelf_path = "shelf_life_master.csv"
        if os.path.exists(shelf_path):
            shelf_df = pd.read_csv(shelf_path)
            st.dataframe(shelf_df, width="stretch", hide_index=True)
        else:
            st.warning("shelf_life_master.csv not found.")

    with w2:
        st.markdown("**♻️ Forensic Waste Ledger (Live DB)**")
        if eng:
            with eng._conn() as conn:
                waste_db_df = pd.read_sql("SELECT waste_date, item_name, quantity, reason, cost_impact, logged_by FROM waste_events ORDER BY created_at DESC", conn)
            
            if not waste_db_df.empty:
                waste_db_df.columns = ["Date", "Item", "Qty", "Reason", "Cost Impact (£)", "User"]
                st.dataframe(waste_db_df, width="stretch", hide_index=True)
                total_waste_val = waste_db_df["Cost Impact (£)"].sum()
                st.markdown(f'<div class="labour-kpi"><div class="labour-kpi-label">Total DB Waste Impact</div><div class="labour-kpi-value" style="color:#e05c5c">£{total_waste_val:,.2f}</div></div>', unsafe_allow_html=True)
            else:
                st.info("No waste events logged in database.")
        else:
            st.error("Recipe Engine offline.")

    st.markdown("---")
    st.markdown("**🖊️ Record New Waste Event**")
    if eng:
        ings = eng.get_ingredients()
        try:
            with st.form("waste_form_upgrade"):
                f_date = st.date_input("Waste Date")
                # Dropdown from real ingredients
                f_ing_name = st.selectbox("Ingredient to Waste", [i["name"] for i in ings])
                f_qty  = st.number_input("Quantity Wasted", min_value=0.01, step=0.1)
                f_reason = st.selectbox("Reason", ["Expired", "Dropped", "Pre-Error", "Customer Refund", "Over-Prepped"])
                if st.form_submit_button("Log & Deduct Waste"):
                    ing_id = next(i["id"] for i in ings if i["name"] == f_ing_name)
                    cost = eng.log_waste(ing_id, f_qty, f_reason, logged_by="DHIRAJ")
                    st.success(f"✅ Logged {f_qty} of {f_ing_name}. Impact: £{cost:.2f}. Stock updated.")
                    st.rerun()
        except Exception as e:
            st.error(f"❌ Failed to save waste event: {e}")

    st.markdown("---")
    st.markdown("**🧠 Forensic Variance Analysis (Theoretical vs. Actual)**")
    
    col_v1, col_v2 = st.columns([2, 1])
    
    if eng:
        # 1. Get Sales Volume
        sv_path = os.path.join(os.getcwd(), "Menu Item Report data", "Most sold items.csv")
        if os.path.exists(sv_path):
            sv_df = pd.read_csv(sv_path)
            n_col = next((c for c in sv_df.columns if any(x in c.lower() for x in ["item","name"])), sv_df.columns[0])
            q_col = next((c for c in sv_df.columns if any(x in c.lower() for x in ["sold","qty","quantity"])), None)
            
            if q_col:
                # CLEAN COMMAS
                sv_df[q_col] = sv_df[q_col].astype(str).str.replace(",", "", regex=False)
                sales_input = [{"item_name": r[n_col], "units_sold": r[q_col]} for _, r in sv_df.iterrows()]
                theo_usage = eng.get_theoretical_usage(sales_input)
                
                if theo_usage:
                    v_rows = []
                    for ing, data in theo_usage.items():
                        # Get actual logged waste for this ingredient from the DB
                        with eng._conn() as conn:
                            logged_qty = conn.execute("SELECT SUM(quantity) FROM waste_events WHERE item_name = ?", (ing,)).fetchone()[0] or 0.0
                        
                        v_rows.append({
                            "Ingredient": ing,
                            "Unit": data["unit"],
                            "Theoretical Usage (Sales)": round(data["usage"], 2),
                            "Logged Waste (Ledger)": round(logged_qty, 2),
                            "Total Depletion": round(data["usage"] + logged_qty, 2),
                            "Theo Cost": f"£{data['cost']:.2f}"
                        })
                    
                    v_df = pd.DataFrame(v_rows)
                    with col_v1:
                        st.dataframe(v_df, width="stretch", hide_index=True)
                    
                    with col_v2:
                        total_theo_cost = sum(d["cost"] for d in theo_usage.values())
                        st.markdown(f"""
                        <div style="background:rgba(124,92,191,0.1);border:1px solid #7c5cbf;padding:20px;border-radius:12px">
                            <h3 style="color:#7c5cbf;margin:0">£{total_theo_cost:,.2f}</h3>
                            <p style="color:#6b7094;font-size:12px;margin:10px 0">Theoretical Consumption</p>
                            <hr style="border:0;border-top:1px solid #7c5cbf;opacity:0.2">
                            <p style="font-size:13px">This is what <b>should</b> have been consumed based on your recipes and sales records.</p>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Link recipes in the Inventory tab to see automatic usage analysis.")
            else:
                st.warning("Sales report format not recognized.")
        else:
            st.info("💡 Drop 'Most sold items.csv' to see automatic usage vs waste analysis.")


# ════════════════════════════════════════════════════════════════════
# TAB 11 — STRATEGIC OPTIMIZATION
# ════════════════════════════════════════════════════════════════════
with tab11:
    st.markdown('<div class="page-title">🚀 Live Menu Engineering Strategy</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Boston Matrix: Popularity (Flipdish Sales) vs. Profitability (Recipe Engine DB).</div>', unsafe_allow_html=True)

    eng = _recipe_engine
    if eng:
        # PULL LIVE PROFITABILITY FROM RECIPE ENGINE
        live_prof_data = eng.calc_item_profitability()
        
        sv_path = os.path.join(os.getcwd(), "Menu Item Report data", "Most sold items.csv")
        sales_summary = pd.DataFrame(columns=["item_name", "units"])
        using_dummy = False
        
        if os.path.exists(sv_path):
            try:
                sv_df = pd.read_csv(sv_path)
                n_col = next((c for c in sv_df.columns if any(x in c.lower() for x in ["item","name"])), sv_df.columns[0])
                q_col = next((c for c in sv_df.columns if any(x in c.lower() for x in ["sold","qty","quantity"])), None)
                if q_col:
                    sales_summary = sv_df[[n_col, q_col]].copy()
                    sales_summary.columns = ["item_name", "units"]
                    # CLEAN COMMAS AND CAST
                    sales_summary["units"] = sales_summary["units"].astype(str).str.replace(",", "", regex=False)
                    sales_summary["units"] = pd.to_numeric(sales_summary["units"], errors='coerce').fillna(0)
            except Exception:
                pass

        if live_prof_data:
            prof_df_strat = pd.DataFrame(live_prof_data)
            prof_df_strat = prof_df_strat[prof_df_strat["has_recipe"]]
            
            if not prof_df_strat.empty:
                if not sales_summary.empty:
                    # ENSURE BOTH ARE STRINGS AND STRIPPED TO AVOID VALUEERROR
                    prof_df_strat["flipdish_name"] = prof_df_strat["flipdish_name"].astype(str).str.strip()
                    sales_summary["item_name"] = sales_summary["item_name"].astype(str).str.strip()
                    
                    prof_df_strat = prof_df_strat.merge(sales_summary, left_on="flipdish_name", right_on="item_name", how="left").fillna(0)
                    prof_df_strat["Units Sold"] = prof_df_strat["units"].astype(float)
                    if prof_df_strat["Units Sold"].sum() == 0:
                        using_dummy = True
                else:
                    using_dummy = True

                if using_dummy:
                    st.info("💡 Note: Actual itemized sales volume data not found in 'Menu Item Report data'. Showing items at baseline 50-unit popularity for strategic visualization.")
                    prof_df_strat["Units Sold"] = 50.0 

                fig_strat = px.scatter(
                    prof_df_strat,
                    x="Units Sold", y="gp_pct", size="selling_price", color="category",
                    hover_name="menu_item", text="menu_item",
                    labels={"Units Sold": "Popularity (Sales Volume)", "gp_pct": "GP Margin (%)"},
                    template="plotly_dark"
                )
                
                fig_strat.update_traces(textposition='top center')
                fig_strat.add_hline(y=70, line_dash="dot", line_color="#3ecf8e", annotation_text="Target Margin (70%)")
                fig_strat.add_vline(x=prof_df_strat["Units Sold"].mean(), line_dash="dot", line_color="rgba(255,255,255,0.3)", annotation_text="Avg Popularity")

                dark_layout(fig_strat, height=600, showlegend=True)
                st.plotly_chart(fig_strat, width="stretch")

                st.markdown("""
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                    <div style="background:rgba(62,207,142,0.1);padding:15px;border-radius:10px;border:1px solid #3ecf8e">
                        <b style="color:#3ecf8e">🌟 STARS (Top Right)</b><br>
                        High Profit + High Volume. Your winners. Keep quality high and maintain pricing.
                    </div>
                    <div style="background:rgba(245,166,35,0.1);padding:15px;border-radius:10px;border:1px solid #f5a623">
                        <b style="color:#f5a623">🐴 WORKHORSES (Top Left)</b><br>
                        Low Profit + High Volume. Increase prices or reduce portion costs immediately.
                    </div>
                    <div style="background:rgba(124,92,191,0.1);padding:15px;border-radius:10px;border:1px solid #7c5cbf">
                        <b style="color:#7c5cbf">🧩 PUZZLES (Bottom Right)</b><br>
                        High Profit + Low Volume. Promote these via specials or social media.
                    </div>
                    <div style="background:rgba(224,92,92,0.1);padding:15px;border-radius:10px;border:1px solid #e05c5c">
                        <b style="color:#e05c5c">🐕 DOGS (Bottom Left)</b><br>
                        Low Profit + Low Volume. Consider removing these from the menu.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("🕒 **Recipe Data Required**: No menu items currently have linked recipes. To use Strategic Optimization, go to the **Inventory & COGS** tab and add ingredients to your menu items.")
        else:
            st.info("🕒 **Menu Data Required**: No menu items found in the database. Go to the **Inventory & COGS** tab to import your menu.")
    else:
        st.warning("Recipe Engine not found for strategic analytics.")


# ════════════════════════════════════════════════════════════════════
# TAB 12 — INVOICE MANAGEMENT  *** PORTAL SYNC ADDED ***
# ════════════════════════════════════════════════════════════════════
with tab12:
    st.markdown('<div class="page-title">📄 Invoice Intelligence Ledger</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">Financial payables, supplier auditing, and cash flow protection.</div>', unsafe_allow_html=True)

    # ── PORTAL SYNC STATUS PANEL ────────────────────────────────────────────
    portal_base = st.session_state.get("portal_url", "http://localhost:5050")
    try:
        import urllib.request as _ur
        portal_secret = os.environ.get("PORTAL_SECRET", "chocoberry2026")
        check_url = f"{portal_base}/api/pending"
        
        _req = _ur.Request(check_url, headers={"Authorization": f"Bearer {portal_secret}"})
        with _ur.urlopen(_req, timeout=3) as _r:
            _pending = json.loads(_r.read())
        
        if _pending:
            st.markdown(f"""
            <div style="background:rgba(245,166,35,0.1);border:1px solid #f5a623;
                        padding:14px 18px;border-radius:10px;margin-bottom:16px">
                <b style="color:#f5a623">📱 {len(_pending)} new invoice(s) uploaded by staff</b>
                — waiting to be synced from <code style="color:#f5a623">{portal_base}</code>
            </div>""", unsafe_allow_html=True)
            
            if st.button("🔄 Sync Staff Uploads Now", type="primary", key="portal_sync"):
                if sync_from_portal:
                    with st.spinner("Syncing latest uploads..."):
                        # Use the local secret from env or default
                        p_secret = os.environ.get("PORTAL_SECRET", "chocoberry2026")
                        sync_from_portal(portal_base=portal_base, portal_secret=p_secret)
                        st.success("✅ Staff uploads synced into ledger.")
                        st.rerun()
                else:
                    st.error("Sync module (sync_portal_invoices.py) not found.")
        else:
            st.markdown("""
            <div style="background:#102a18;border:1px solid #3ecf8e;
                        padding:10px 16px;border-radius:8px;margin-bottom:12px;
                        font-size:12px;color:#3ecf8e">
                ✅ Staff upload portal: online — no pending uploads
            </div>""", unsafe_allow_html=True)
    except Exception:
        st.markdown("""
        <div style="background:#12141a;border:1px solid #252836;
                    padding:10px 16px;border-radius:8px;margin-bottom:12px;
                    font-size:12px;color:#6b7094">
            ⚪ Staff portal offline — run <code>python invoice_portal.py</code> to start it
        </div>""", unsafe_allow_html=True)

    # ── 1. OVERDUE ALERTS PANEL ──────────────────────────────────────────────
    overdue_list = inv_db.get_overdue_invoices()
    if overdue_list:
        with st.container():
            st.markdown(f'<div style="background:rgba(224,92,92,0.1);border:1px solid #e05c5c;padding:16px;border-radius:12px;margin-bottom:20px"><div style="color:#e05c5c;font-family:Syne,sans-serif;font-weight:800;font-size:13px;letter-spacing:1px;margin-bottom:8px">🚨 CRITICAL OVERDUE PAYABLES — {len(overdue_list)} INVOICES LATE</div>', unsafe_allow_html=True)
            for inv_no, supp, amt, due in overdue_list[:3]:
                st.markdown(f'<div style="color:#6b7094;font-size:11px;margin-bottom:4px">⚠️ <b>{supp}</b> (Inv #{inv_no}): £{amt:,.2f} — Due: {due}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # ── 2. KPI SUMMARY ROW ──────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    all_invs = inv_db.get_all_invoices()
    total_unpaid = sum(row[5] for row in all_invs if row[6] != 'PAID')
    total_overdue = sum(row[2] for row in overdue_list)

    this_month_ym = datetime.now().strftime('%Y-%m')
    this_month_my = datetime.now().strftime('/%m/%Y')
    this_month_spend = 0
    for row in all_invs:
        d_str = str(row[3]) if row[3] else ""
        if d_str.startswith(this_month_ym) or d_str.endswith(this_month_my):
            this_month_spend += row[5]

    k1.metric("🔴 Total Unpaid", f"£{total_unpaid:,.2f}")
    k2.metric("⌛ Total Overdue", f"£{total_overdue:,.2f}", f"{len(overdue_list)} late", delta_color="inverse")
    k3.metric("💳 Month Spend", f"£{this_month_spend:,.2f}")
    k4.metric("📊 Suppliers", f"{len(set(row[2] for row in all_invs))}", "Active ledger")

    st.markdown("---")

    # ── 3. VIEW CONTROLS ────────────────────────────────────────────────────
    c_mode, c_depth = st.columns([2, 1])
    with c_mode:
        mode = st.radio("System Mode", ["📋 Accounts Registry", "🖊️ Record New Invoice (Dhiraj Mode)", "📈 Spend Analytics", "💰 Revenue Ledger"], horizontal=True)
    with c_depth:
        if mode == "📋 Accounts Registry":
            v_depth = st.radio("View Depth", ["Summarized", "Itemized (All 238+ Lines)"], horizontal=True)
        else:
            st.empty()

    if mode == "📋 Accounts Registry":
        st.markdown("**1. Filter Intelligence**")
        f1, f2, f3 = st.columns([2, 1, 1])
        search = f1.text_input("🔍 Search Invoices", placeholder="Supplier or Invoice #...")
        supp_opts = ["All Suppliers"] + sorted(list(set(row[2] for row in all_invs)))
        sel_supp = f2.selectbox("Filter by Supplier", supp_opts)
        stat_opts = ["All Statuses", "PAID", "UNPAID"]
        sel_stat = f3.selectbox("Status", stat_opts)

        st.markdown("---")
        if v_depth == "Summarized":
            f_invs = all_invs
            if sel_supp != "All Suppliers": f_invs = [r for r in f_invs if r[2] == sel_supp]
            if sel_stat != "All Statuses": f_invs = [r for r in f_invs if r[6] == sel_stat]
            if search: f_invs = [r for r in f_invs if search.lower() in str(r[1]).lower() or search.lower() in str(r[2]).lower()]

            if f_invs:
                reg_df = pd.DataFrame(f_invs, columns=["ID", "Invoice #", "Supplier", "Date", "Due Date", "Gross (£)", "Status", "Category", "Drive Path"])
                st.dataframe(reg_df.drop(columns=["ID"]), width="stretch", hide_index=True)

                st.download_button(
                    label="⬇️ Export Filtered Registry (CSV)",
                    data=reg_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"invoice_registry_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

                with st.expander("🛠️ Advanced Invoice Actions (Mark as Paid / View Metadata)"):
                    sel_inv = st.selectbox("Select Invoice to Action", [f"#{r[1]} - {r[2]}" for r in f_invs])
                    a_col1, a_col2 = st.columns(2)
                    if a_col1.button("✅ Mark as Paid", width="stretch"):
                        inv_id = [r[0] for r in f_invs if f"#{r[1]} - {r[2]}" == sel_inv][0]
                        inv_db.update_payment_status(inv_id, 'PAID')
                        st.success("Invoice status updated.")
                        st.rerun()
            else:
                st.info("No invoices found matching criteria.")
        else:
            items = inv_db.get_all_line_items()
            if items:
                item_df = pd.DataFrame(items, columns=["Invoice #", "Supplier", "Description", "Product Code", "Qty", "Unit", "Rate (£)", "Total (£)"])
                if sel_supp != "All Suppliers": item_df = item_df[item_df["Supplier"] == sel_supp]
                if search: item_df = item_df[item_df["Description"].str.contains(search, case=False)]

                st.markdown(f"**🔍 Displaying {len(item_df)} individual line items from forensic ledger**")
                st.dataframe(item_df, width="stretch", hide_index=True)
            else:
                st.warning("No line items found in the database.")
            st.markdown("---")

    elif mode == "🖊️ Record New Invoice (Dhiraj Mode)":
        with st.form("invoice_upload_form"):
            st.markdown("**1. Upload Proof of Delivery (Photo/PDF)**")
            u_file = st.file_uploader("Drop invoice trace here", type=["pdf", "png", "jpg"])

            st.markdown("---")
            st.markdown("**2. Manual Forensic Entry**")
            f1, f2 = st.columns(2)
            with f1:
                inv_no = st.text_input("Invoice Number")
                all_supps = [s[1] for s in inv_db.get_suppliers()]
                supplier = st.selectbox("Supplier", all_supps if all_supps else ["Cr8 Foods", "Freshways", "Bookers"])
            with f2:
                inv_date = st.date_input("Invoiced Date", value=datetime.now())
                total_val = st.number_input("Total Gross Amount (£)", min_value=0.0)

            cat = st.selectbox("Category", ["Food", "Packaging", "Labour", "Utilities", "Maintenance", "Other"])
            notes = st.text_area("Internal Notes")

            if st.form_submit_button("Submit to Intelligence Gateway"):
                if inv_no and total_val > 0:
                    supp_id = inv_db.add_supplier(supplier)
                    if inv_db.check_duplicate(inv_no, supp_id):
                        st.warning(f"⚠️ Duplicate detected: Invoice {inv_no} from {supplier} already exists.")
                    else:
                        # ── Organise Uploaded File ──────────────────────────────────
                        rel_path = ""
                        if u_file:
                            import shutil
                            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            safe_sup = "".join(c for c in supplier if c.isalnum() or c==' ').strip()
                            filename = f"{stamp}_{safe_sup.replace(' ','_')}_{int(total_val)}{os.path.splitext(u_file.name)[1]}"
                            
                            year_folder  = inv_date.strftime("%Y")
                            month_folder = inv_date.strftime("%m-%b")
                            target_dir   = Path(os.getcwd()) / "Invoices" / year_folder / month_folder / safe_sup
                            target_dir.mkdir(parents=True, exist_ok=True)
                            
                            target_path = target_dir / filename
                            with open(target_path, "wb") as f:
                                f.write(u_file.getbuffer())
                            rel_path = str(target_path.relative_to(Path(os.getcwd())))

                        inv_data = {
                            'invoice_number': inv_no,
                            'supplier_id':    supp_id,
                            'invoice_date':   inv_date.strftime('%Y-%m-%d'),
                            'total_amount':   total_val,
                            'category':       cat,
                            'notes':          notes,
                            'payment_status': 'UNPAID',
                            'image_path':     rel_path
                        }
                        inv_db.insert_invoice(inv_data)
                        st.success(f"✅ Invoice {inv_no} logged and saved to Drive-ready folder ({rel_path}).")
                        st.rerun()
                else:
                    st.error("Missing required fields (Invoice # or Total).")

    elif mode == "📈 Spend Analytics":
        st.markdown("**📊 Spend Intelligence**")

        c1_sa, c2_sa = st.columns(2)

        with c1_sa:
            analytics = inv_db.get_supplier_analytics()
            if analytics:
                ana_df = pd.DataFrame(analytics, columns=["Supplier", "Total Spend", "Count"])
                fig_spend = go.Figure(go.Bar(
                    x=ana_df["Supplier"], y=ana_df["Total Spend"],
                    marker_color=PALETTE[0],
                    marker_line_width=0,
                ))
                dark_layout(fig_spend, 350)
                fig_spend.update_layout(title="Total Spend by Supplier (£)")
                st.plotly_chart(fig_spend, width="stretch")

        with c2_sa:
            cat_analytics = inv_db.get_category_analytics()
            if cat_analytics:
                cat_df = pd.DataFrame(cat_analytics, columns=["Category", "Spend"])
                fig_cat = px.pie(
                    cat_df, values="Spend", names="Category",
                    hole=0.4, color_discrete_sequence=px.colors.sequential.YlOrRd
                )
                dark_layout(fig_cat, 350)
                fig_cat.update_layout(title="Spend by Category", showlegend=True)
                st.plotly_chart(fig_cat, width="stretch")

        st.markdown("---")
        st.markdown("**📉 Historical Spend Trend**")
        trend_data = inv_db.get_monthly_spend_trend()
        if trend_data:
            trend_df = pd.DataFrame(trend_data, columns=["Month", "Spend"])
            fig_trend = go.Figure(go.Scatter(
                x=trend_df["Month"], y=trend_df["Spend"],
                mode='lines+markers',
                line=dict(color=COLORS["accent"], width=3),
                marker=dict(size=8)
            ))
            dark_layout(fig_trend, 300)
            fig_trend.update_layout(
                title="Historical Spend Trend (Monthly Invoiced)",
                xaxis_title="Month",
                yaxis_title="Total Invoiced (£)"
            )
            st.plotly_chart(fig_trend, width="stretch")
        else:
            st.info("Ingest more monthly data to see trend lines.")

        st.markdown("---")
        st.markdown("**📊 Month-on-Month Supplier Comparison**")
        mom_data = inv_db.get_supplier_monthly_analytics()
        if mom_data:
            mom_df = pd.DataFrame(mom_data, columns=["Supplier", "Month", "Spend"])
            fig_mom = px.bar(
                mom_df, x="Month", y="Spend", color="Supplier",
                title="Spend Distribution by Supplier over Time",
                template="plotly_dark",
                barmode="stack"
            )
            dark_layout(fig_mom, 400)
            st.plotly_chart(fig_mom, width="stretch")

    elif mode == "💰 Revenue Ledger":
        st.markdown("**📈 Daily Revenue & Sales Master**")
        st.markdown('<div class="insight-box">Edit your daily sales figures here. All calculations (AOV, Labour %, Trends) will update automatically across the entire dashboard when you Save.</div>', unsafe_allow_html=True)

        rev_csv = os.path.join(os.getcwd(), "daily_sales_master.csv")
        if os.path.exists(rev_csv):
            sales_df = pd.read_csv(rev_csv)
            sales_df = sales_df.sort_values("date", ascending=False)

            edited_sales = st.data_editor(
                sales_df,
                width="stretch",
                num_rows="dynamic",
                hide_index=True,
                column_config={
                    "net": st.column_config.NumberColumn("Net Sales (£)", format="£%.2f"),
                    "revenue": st.column_config.NumberColumn("Gross (£)", format="£%.2f"),
                    "orders": st.column_config.NumberColumn("Orders"),
                }
            )

            if st.button("💾 Save Revenue Changes & Recalculate Dashboard", width="stretch"):
                edited_sales.to_csv(rev_csv, index=False, encoding="utf-8-sig")
                st.success("✅ Revenue ledger updated. Recalculating all project metrics...")
                st.cache_data.clear()
                st.rerun()
        else:
            st.error("Missing daily_sales_master.csv. Please restart the application to generate it.")


# ════════════════════════════════════════════════════════════════════
# TAB 13 — DATABASE EXPLORER
# ════════════════════════════════════════════════════════════════════
with tab13:
    st.markdown('<div class="section-title">Forensic Database Explorer</div>', unsafe_allow_html=True)
    st.markdown('<div class="insight-box">Select a database and table to inspect raw records. Use this for data auditing and integrity checks.</div>', unsafe_allow_html=True)

    db_choice = st.selectbox("Select Database", ["main_invoices (cbc_invoice_intelligence.db)", "recipe_engine (recipes.db)", "portal_uploads (invoices.db)"])
    
    db_mapping = {
        "main_invoices (cbc_invoice_intelligence.db)": "cbc_invoice_intelligence.db",
        "recipe_engine (recipes.db)": "recipes.db",
        "portal_uploads (invoices.db)": "invoices.db"
    }
    
    selected_db = db_mapping[db_choice]
    
    if os.path.exists(selected_db):
        import sqlite3
        with sqlite3.connect(selected_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cursor.fetchall() if r[0] not in ["sqlite_sequence"]]
            
            if tables:
                table_choice = st.selectbox("Select Table", tables)
                if table_choice:
                    table_choice_safe = str(table_choice).replace(" ", "_")
                    df_db = pd.read_sql_query(f"SELECT * FROM {table_choice} LIMIT 500", conn)
                    st.write(f"Showing last 500 records from **{table_choice}**")
                    st.dataframe(df_db, width="stretch")
                    
                    st.download_button(
                        label=f"⬇️ Export {table_choice} to CSV",
                        data=df_db.to_csv(index=False),
                        file_name=f"{table_choice_safe}_export.csv",
                        mime="text/csv"
                    )
            else:
                st.warning("No tables found in this database.")
    else:
        st.error(f"Database file not found: {selected_db}")

    st.markdown("---")
    st.markdown("**🛠️ Manual SQL Query (Advanced)**")
    query = st.text_area("Enter SQL Query", "SELECT * FROM suppliers", key="sql_query_area")
    if st.button("Execute Query", key="sql_exec_btn"):
        if not query.strip():
            st.warning("Please enter a query.")
        elif not query.strip().upper().startswith("SELECT"):
            st.error("🚫 Security Restriction: Only SELECT queries are allowed in the Database Explorer.")
        else:
            try:
                with sqlite3.connect(selected_db) as conn:
                    res_df = pd.read_sql_query(query, conn)
                    st.success("Query executed successfully.")
                    st.dataframe(res_df, width="stretch")
            except Exception as e:
                st.error(f"SQL Error: {e}")




def _print_labour_console(summary, over_df, under_df, overlay_df):
    print("\n" + "=" * 60)
    print("  CHOCOBERRY LABOUR ANALYSIS — CONSOLE SUMMARY")
    print(f"  Week: {WEEK_LABEL}")
    print("=" * 60)
    for k, v in summary.items():
        flag = ""
        if "%" in str(v) and "Labour %" in k:
            pct  = float(str(v).replace("%", ""))
            flag = " 🔴" if pct > 30 else " ✅"
        print(f"  {k:<35} {v}{flag}")

    print(f"\n  OVERSTAFFED HOURS:  {len(over_df)}")
    for _, r in over_df.iterrows():
        print(f"    🔴  {r['Hour']}  |  Rev: £{r['Avg Revenue (£)']:.2f}"
              f"  |  Staff: {r['Total Staff']}  |  Cost: £{r['Total Staff Cost (£)']:.2f}")

    print(f"\n  UNDERSTAFFED HOURS: {len(under_df)}")
    for _, r in under_df.iterrows():
        print(f"    🟡  {r['Hour']}  |  Rev: £{r['Avg Revenue (£)']:.2f}"
              f"  |  Staff: {r['Total Staff']}")

    print("\n  PEAK HOURS COVERAGE (19:00–23:00):")
    peak = overlay_df[overlay_df["Hour"].isin(["19:00","20:00","21:00","22:00","23:00"])]
    for _, r in peak.iterrows():
        print(f"    {r['Hour']}  Rev: £{r['Avg Revenue (£)']:>8,.2f}"
              f"  Staff: {r['Total Staff']:>2}"
              f"  Cost: £{r['Total Staff Cost (£)']:>6.2f}"
              f"  Rev/Staff: £{r['Revenue/Staff/Hr (£)']:>7,.2f}"
              f"  {r['Flag']}")
    print("=" * 60)


if __name__ == "__main__" and "--report" in sys.argv:
    OUTPUT = "chocoberry_labour_report.xlsx"
    summary, overlay_df, over_df, under_df = build_labour_workbook(load_data(), OUTPUT)
    _print_labour_console(summary, over_df, under_df, overlay_df)
