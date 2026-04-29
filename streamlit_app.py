import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

# --- Configuration & Theme ---
st.set_page_config(page_title="Chocoberry Staff Portal", page_icon="🍫", layout="centered")

# --- PLACEHOLDER FOR YOUR GOOGLE URL ---
# Paste your "Web App URL" from Google Apps Script here!
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwH21f0lQrxTn02osMx5Bxl3B49_M6_TVOMqQJMwUZYEYyAbsLDQncquq_8NMAM51UoeA/exec"

st.markdown("""
    <style>
    .main { background-color: #0a0b0f; }
    .stSelectbox label, .stTextInput label { color: #6b7094; font-weight: 700; font-size: 14px; }
    div[data-baseweb="select"] > div { background-color: #12141a; border-color: #252836; color: white; }
    .stButton>button {
        width: 100%;
        background: #f5a623;
        color: #0a0b0f;
        font-weight: 800;
        border-radius: 12px;
        border: none;
        padding: 15px;
        margin-top: 20px;
    }
    .header-box {
        text-align: center;
        padding: 20px;
        background: #12141a;
        border-radius: 15px;
        border: 1px solid #252836;
        margin-bottom: 25px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
    <div class="header-box">
        <h1 style='color:#f5a623;margin:0;'>Chocoberry</h1>
        <p style='color:#6b7094;margin:0;'>Staff Availability Portal</p>
    </div>
""", unsafe_allow_html=True)

# --- Data Loading ---
@st.cache_data
def get_staff():
    try:
        df = pd.read_csv("staff_profiles.csv")
        df.columns = [c.strip() for c in df.columns]
        active = df[df['Active'].astype(str).str.lower().isin(['true','yes','1'])]
        return active.sort_values("Name")
    except:
        st.error("Error: Could not find staff_profiles.csv in the repository.")
        return pd.DataFrame()

staff_df = get_staff()

if not staff_df.empty:
    # --- Form ---
    with st.form("avail_form", clear_on_submit=False):
        
        name = st.selectbox("Select Your Name", ["-- Choose --"] + staff_df["Name"].tolist())
        pin  = st.text_input("Security PIN", type="password", help="Enter your 4-digit code")
        
        st.markdown("---")
        st.subheader("Weekly Shifts")
        
        # Calculate target week
        today = datetime.now()
        days_to_mon = (7 - today.weekday()) % 7
        next_mon = today + timedelta(days=days_to_mon if days_to_mon else 7)
        next_sun = next_mon + timedelta(days=6)
        st.info(f"📅 Week: {next_mon.strftime('%d %b')} – {next_sun.strftime('%d %b %Y')}")

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        avail_data = {}
        
        opts = {
            "🟢 Any Shift": "any",
            "💗 Opening Only": "opening",
            "🔘 Closing Only": "closing",
            "🔴 Unavailable": "unavailable"
        }
        
        for day in days:
            st.markdown(f"**{day}**")
            sel = st.selectbox(f"Availability for {day}", options=list(opts.keys()), key=f"sel_{day}", label_visibility="collapsed")
            avail_data[day] = opts[sel]
        
        st.markdown("---")
        notes = st.text_input("Special Requests / Notes (optional)")
        
        submit = st.form_submit_button("🚀 Submit Availability")
        
        if submit:
            if name == "-- Choose --":
                st.warning("Please select your name.")
            elif not pin:
                st.warning("PIN is required.")
            elif GOOGLE_SCRIPT_URL == "YOUR_GOOGLE_SCRIPT_URL_HERE":
                st.error("Developer Error: Google Script URL not set. Please update GOOGLE_SCRIPT_URL in the code.")
            else:
                # Verify PIN
                row = staff_df[staff_df["Name"] == name].iloc[0]
                correct_pin = str(row["PIN"]).strip()
                
                if pin.strip() != correct_pin:
                    st.error("❌ Incorrect PIN. Please try again.")
                else:
                    # Send to Google Sheets
                    payload = {
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Name": name,
                        "Week_Start": next_mon.strftime("%Y-%m-%d"),
                        "Availability": json.dumps(avail_data),
                        "Notes": notes
                    }
                    
                    try:
                        response = requests.post(GOOGLE_SCRIPT_URL, json=payload)
                        if response.status_code == 200:
                            st.balloons()
                            st.success(f"✅ Thank you {name}! Your availability is recorded.")
                            st.markdown(f"""
                                <div style='background:#1a1c24;padding:20px;border-radius:10px;border:1px solid #3ecf8e;text-align:center'>
                                    <p>Your availability for <b>{next_mon.strftime('%d %b')}</b> has been synced to the cloud.</p>
                                </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.error(f"Cloud Error: {response.text}")
                    except Exception as e:
                        st.error(f"Connection Error: {e}")
else:
    st.info("Please upload your 'staff_profiles.csv' to this repository to activate the portal.")
