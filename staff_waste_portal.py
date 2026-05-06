import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.environ.get("WASTE_SUPABASE_URL", "https://hbdojsklhthrnvgyryzj.supabase.co")
SUPABASE_KEY = os.environ.get("WASTE_SUPABASE_KEY", "sb_publishable_CW3An_aWaqw5wQ_KC_6kbg_U8qEJoNU")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- PAGE CONFIG ---
st.set_page_config(page_title="Chocoberry Staff Portal", page_icon="🍫")

# --- CUSTOM CSS FOR BRANDING ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { background-color: #3ecf8e; color: white; border-radius: 8px; width: 100%; height: 3em; font-size: 1.2em; }
    h1 { color: #3ecf8e; text-align: center; }
    </style>
""", unsafe_allow_html=True)

st.title("🍫 Chocoberry Kitchen Portal")
st.markdown("### Log Kitchen Wastage")
st.info("✨ This data is now permanently saved in the Cloud.")

# --- DB CONNECTION ---
def get_ingredients():
    try:
        conn = sqlite3.connect('recipes.db')
        df = pd.read_sql("SELECT name FROM ingredients ORDER BY name ASC", conn)
        conn.close()
        return df['name'].tolist()
    except:
        return ["Milk", "Chocolate", "Fruit", "Waffles"]

# --- WASTE FORM ---
ingredients = get_ingredients()

with st.form("staff_waste_form", clear_on_submit=True):
    staff_name = st.text_input("Your Name", placeholder="e.g. Dhiraj, Sarah")
    item = st.selectbox("Select Item Wasted", ingredients)
    qty = st.number_input("Quantity (e.g. 1.0, 0.5)", min_value=0.1, step=0.1)
    reason = st.text_input("Reason (Optional)", placeholder="e.g. Dropped, Expired")
    
    submitted = st.form_submit_button("🚀 Log Waste Entry")
    
    if submitted:
        if not staff_name:
            st.error("Please enter your name!")
        else:
            try:
                # Prepare data for Supabase
                data = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "staff_name": staff_name,
                    "ingredient_name": item,
                    "quantity": qty,
                    "reason": reason,
                    "synced_to_main": False
                }
                
                # Save to Supabase
                response = supabase.table("waste_logs").insert(data).execute()
                
                st.success(f"✅ Success! {qty} of {item} has been logged by {staff_name}. It is safely in the Cloud.")
                st.balloons()
            except Exception as e:
                st.error(f"❌ Error saving to cloud: {str(e)}")

st.markdown("---")

# --- HISTORY & BACKUP (Plan B) ---
with st.expander("📂 View Waste History & Download CSV"):
    try:
        # Fetch data for preview
        history_resp = supabase.table("waste_logs").select("*").order("created_at", desc=True).execute()
        history_df = pd.DataFrame(history_resp.data)
        
        if not history_df.empty:
            st.dataframe(history_df[["date", "staff_name", "ingredient_name", "quantity", "reason"]], width="stretch")
            
            # CSV Download Button
            csv = history_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 DOWNLOAD ALL WASTE LOGS AS CSV",
                data=csv,
                file_name=f"chocoberry_waste_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
            )
        else:
            st.write("No waste records found in history yet.")
    except Exception as e:
        st.write("Could not load history.")

st.caption("Internal Chocoberry Staff System - V2.0 (Cloud Integrated)")
