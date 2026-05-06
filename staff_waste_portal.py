import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

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
waste_path = "daily_waste_log.csv"

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
            new_data = pd.DataFrame([{
                "date": datetime.now().strftime("%Y-%m-%d"),
                "staff_name": staff_name,
                "ingredient_name": item,
                "quantity": qty,
                "reason": reason
            }])
            # Append to CSV
            new_data.to_csv(waste_path, mode='a', header=not os.path.exists(waste_path), index=False)
            st.success(f"✅ Success! {qty} of {item} has been logged by {staff_name}.")
            st.balloons()

st.markdown("---")
st.caption("Internal Chocoberry Staff System - V1.0")
