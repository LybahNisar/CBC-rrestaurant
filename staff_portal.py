"""
╔══════════════════════════════════════════════════════════════════╗
║         CHOCOBERRY — DEDICATED STAFF AVAILABILITY PORTAL        ║
║   Phone-friendly web app — purely for staff shift preferences   ║
║                                                                  ║
║  HOW TO RUN:                                                     ║
║    python staff_portal.py                                        ║
║  Then open on any phone on the same WiFi:                        ║
║    http://<your-laptop-ip>:5051                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from pathlib import Path

app = Flask(__name__)

# ── Paths ─────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "availability.db"

AVAIL_FORM = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <title>Chocoberry — Submit Availability</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0a0b0f;
            color: #e8e9f0;
            padding: 20px;
            max-width: 500px;
            margin: 0 auto;
            line-height: 1.5;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px 0;
            border-bottom: 1px solid #252836;
        }
        .logo { font-size: 24px; font-weight: 800; color: #f5a623; }
        .logo span { color: #e8e9f0; }
        h2 { color: #f5a623; margin: 10px 0; font-size: 20px; }
        .week-label {
            color: #6b7094;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .day-card {
            background: #12141a;
            border: 1px solid #252836;
            border-radius: 12px;
            padding: 18px;
            margin: 12px 0;
            transition: border-color 0.2s;
        }
        .day-card:focus-within { border-color: #f5a623; }
        .day-name {
            font-weight: 700;
            font-size: 16px;
            margin-bottom: 12px;
            color: #f5a623;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        label { display: block; font-size: 12px; color: #6b7094; margin-bottom: 8px; }
        select, input {
            width: 100%;
            padding: 12px;
            background: #0d0f14;
            border: 1px solid #252836;
            color: #e8e9f0;
            border-radius: 8px;
            font-size: 15px;
            outline: none;
            -webkit-appearance: none;
        }
        select:focus, input:focus { border-color: #f5a623; }
        button {
            width: 100%;
            padding: 16px;
            background: #f5a623;
            color: #0a0b0f;
            font-weight: 800;
            font-size: 17px;
            border: none;
            border-radius: 12px;
            margin-top: 25px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(245,166,35,0.2);
        }
        button:active { transform: scale(0.98); }
        .footer { text-align: center; color: #6b7094; font-size: 11px; margin-top: 40px; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">Choco<span>berry</span></div>
        <h2>Shift Availability</h2>
        <div class="week-label">Week: {{ week_label }}</div>
    </div>
    
    <form method="POST" action="/submit-availability">
        
        <div class="day-card">
            <label>Select Your Name</label>
            <select name="staff_name" required>
                <option value="">-- Choose Name --</option>
                {% for name in staff_names %}
                <option value="{{ name }}">{{ name }}</option>
                {% endfor %}
            </select>
        </div>

        {% for day in days %}
        <div class="day-card">
            <div class="day-name">
                <span id="icon-{{ day }}">📅</span> {{ day }}
            </div>
            <select name="{{ day }}" onchange="updateIcon(this, '{{ day }}')">
                <option value="any">🟢 Any Shift</option>
                <option value="opening">💗 Opening Shift Only</option>
                <option value="closing">🔘 Closing Shift Only</option>
                <option value="unavailable">🔴 Unavailable</option>
            </select>
        </div>
        {% endfor %}

        <div class="day-card">
            <label>🔐 Security PIN</label>
            <input type="password" name="staff_pin" placeholder="Enter your 4-digit PIN" required pattern="[0-9]*" inputmode="numeric">
        </div>

        <div class="day-card">
            <label>Notes / Special Requests (optional)</label>
            <input type="text" name="notes" placeholder="e.g. Can only work after 5pm Friday">
        </div>

        <button type="submit">🚀 Submit My Availability</button>
    </form>

    <div class="footer">
        &copy; 2026 Chocoberry Intelligence Cardiff<br>
        Staff Portal v2.0 (Dedicated)
    </div>

    <script>
        function updateIcon(sel, day) {
            const icons = {
                'any': '🟢',
                'opening': '💗',
                'closing': '🔘',
                'unavailable': '🔴'
            };
            document.getElementById('icon-' + day).innerText = icons[sel.value];
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    # Get staff names from CSV
    import pandas as pd
    try:
        staff_df = pd.read_csv('staff_profiles.csv')
        # Filter for active staff
        names = sorted(staff_df[staff_df['Active'].astype(str).str.lower().isin(['true','yes','1'])]['Name'].tolist())
    except Exception as e:
        print(f"Error loading staff: {e}")
        names = []
    
    days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    
    # Calculate target week label
    today = datetime.now()
    days_to_monday = (7 - today.weekday()) % 7
    # If today is Monday-Thursday, show NEXT Monday. 
    # If today is Friday-Sunday, show the Monday coming up.
    next_monday = today + timedelta(days=days_to_monday if days_to_monday else 7)
    next_sunday = next_monday + timedelta(days=6)
    week_label = f"{next_monday.strftime('%d %b')} – {next_sunday.strftime('%d %b %Y')}"
    
    return render_template_string(
        AVAIL_FORM,
        staff_names=names,
        days=days,
        week_label=week_label
    )

@app.route('/submit-availability', methods=['POST'])
def submit_availability():
    import pandas as pd
    data = request.form
    name = data.get('staff_name')
    pin_attempt = data.get('staff_pin')
    days = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
    
    # ── PIN Verification ──
    try:
        staff_df = pd.read_csv('staff_profiles.csv')
        staff_df.columns = [c.strip() for c in staff_df.columns]
        # Find the row for this person
        staff_row = staff_df[staff_df['Name'] == name]
        if staff_row.empty:
            return "Error: Staff member not found.", 403
            
        correct_pin = str(staff_row.iloc[0]['PIN']).strip()
        if pin_attempt != correct_pin:
            return """
            <html>
            <body style="background:#0a0b0f;color:white;text-align:center;padding:50px;font-family:sans-serif">
                <h1 style="color:#e05c5c;font-size:40px">🔒</h1>
                <h2 style="color:#e05c5c">Security Alert</h2>
                <p>The PIN you entered for <b>""" + name + """</b> is incorrect.</p>
                <p style="color:#6b7094">Please go back and try again.</p>
                <br>
                <a href="/" style="color:#f5a623;text-decoration:none">← Try Again</a>
            </body>
            </html>
            """, 403
    except Exception as e:
        return f"System Error during verification: {e}", 500

    availability = {}
    for day in days:
        availability[day] = data.get(day, 'any')
    
    notes = data.get('notes', '')
    
    # Save to database
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS availability (
                id INTEGER PRIMARY KEY,
                staff_name TEXT,
                week_start TEXT,
                availability TEXT,
                notes TEXT,
                submitted_at TEXT
            )
        ''')
        
        today = datetime.now()
        days_ahead = (7 - today.weekday()) % 7
        next_monday = today + timedelta(days=days_ahead if days_ahead else 7)
        
        # INSERT OR REPLACE to handle re-submissions for the same week
        conn.execute('''
            INSERT OR REPLACE INTO availability
            (staff_name, week_start, availability, notes, submitted_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            name,
            next_monday.strftime('%Y-%m-%d'),
            json.dumps(availability),
            notes,
            datetime.now().isoformat()
        ))
        conn.commit()
    
    return """
    <html>
    <body style="background:#0a0b0f;color:white;text-align:center;padding:50px;font-family:sans-serif">
        <h1 style="color:#f5a623;font-size:40px">✅</h1>
        <h2 style="color:#f5a623">Submission Successful!</h2>
        <p>Thanks, <b>""" + name + """</b>. Your availability for next week is recorded.</p>
        <p style="color:#6b7094;margin-top:20px">The manager will now see your preferences in the dashboard.</p>
        <br><br>
        <div style="color:#444;font-size:12px">You can safely close this window now.</div>
    </body>
    </html>
    """

if __name__ == "__main__":
    from waitress import serve
    print("\n🚀 CHOCOBERRY STAFF PORTAL LIVE")
    print(f"📍 URL: http://0.0.0.0:5051")
    print("----------------------------------------")
    serve(app, host='0.0.0.0', port=5051)
