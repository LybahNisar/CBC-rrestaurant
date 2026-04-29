"""
╔══════════════════════════════════════════════════════════════════╗
║         CHOCOBERRY — PRIVATE INVOICE UPLOAD PORTAL              ║
║   Dedicated portal for management/owners to upload receipts      ║
║                                                                  ║
║  HOW TO RUN:                                                     ║
║    python invoice_portal.py                                      ║
║  Then open on your phone:                                        ║
║    http://<your-laptop-ip>:5050                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import base64
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "chocoberry-invoice-2026"

# ── API Key Verification ──────────────────────────────────────────
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
PORTAL_SECRET = os.environ.get("PORTAL_SECRET", "chocoberry2026")

# ── Paths ─────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
UPLOADS_DIR  = BASE_DIR / "invoice_uploads"
DB_PATH      = BASE_DIR / "invoices.db"
UPLOADS_DIR.mkdir(exist_ok=True)

# ── Setup ─────────────────────────────────────────────────────────
SUPPLIERS = ["Cr8 Foods", "Freshways", "Bookers", "Brakes", "Sysco", "Fresh Direct", "Bestway", "Muller", "T.Quality", "Other"]
CATEGORIES = ["Food", "Packaging", "Cleaning", "Utilities", "Maintenance", "Other"]

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portal_uploads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_date   TEXT    NOT NULL,
                staff_name    TEXT,
                supplier      TEXT,
                invoice_date  TEXT,
                total_amount  REAL,
                category      TEXT,
                invoice_number TEXT,
                notes         TEXT,
                image_filename TEXT,
                ai_parsed     INTEGER DEFAULT 0,
                synced_to_main INTEGER DEFAULT 0,
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

# ── AI Invoice Parsing ─────────────────────────────────────────────
def ai_parse_invoice(image_b64: str, mime_type: str) -> dict:
    try:
        import urllib.request
        payload = json.dumps({
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}}, {"type": "text", "text": "Extract invoice data. Reply ONLY with JSON: {\"supplier\":\"\",\"invoice_number\":\"\",\"invoice_date\":\"YYYY-MM-DD\",\"total_amount\":0.00}"}]}]
        }).encode()
        if not ANTHROPIC_KEY: return {}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return json.loads(data["content"][0]["text"].strip().replace("```json", "").replace("```", ""))
    except: return {}

@app.route("/")
def index():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Chocoberry — Private Invoice Portal</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0a0b0f;color:#e8e9f0;font-family:sans-serif;min-height:100vh;padding:20px}
  .header{text-align:center;margin-bottom:20px}
  .logo{font-size:24px;font-weight:800;color:#f5a623}
  .logo span{color:#e8e9f0}
  .card{background:#12141a;border:1px solid #252836;border-radius:12px;padding:20px;margin-bottom:16px}
  .card-title{font-size:12px;font-weight:700;color:#f5a623;text-transform:uppercase;margin-bottom:15px}
  label{display:block;font-size:12px;color:#6b7094;margin-bottom:5px;margin-top:10px}
  input,select,textarea{width:100%;background:#0d0f14;border:1px solid #252836;border-radius:8px;padding:12px;color:#e8e9f0;font-size:15px;outline:none}
  .submit-btn{width:100%;background:#f5a623;color:#0a0b0f;border:none;border-radius:10px;padding:16px;font-size:16px;font-weight:700;cursor:pointer;margin-top:10px}
  #preview{width:100%;border-radius:8px;margin-top:10px;display:none;max-height:200px;object-fit:contain}
  .ai-badge{background:rgba(245,166,35,0.1);border:1px solid rgba(245,166,35,0.3);padding:8px;border-radius:8px;font-size:11px;color:#f5a623;margin-bottom:15px;text-align:center}
</style>
</head>
<body>
<div class="header">
  <div class="logo">Choco<span>berry</span></div>
  <div style="font-size:12px;color:#6b7094">INVOICE PORTAL (PORT 5050)</div>
</div>

<div class="ai-badge">✨ AI will auto-extract totals from your photo</div>

<form id="uploadForm">
  <div class="card">
    <div class="card-title">📸 Take Photo</div>
    <input type="file" id="fileInput" name="invoice_image" accept="image/*" capture="environment" required>
    <img id="preview">
  </div>

  <div class="card">
    <div class="card-title">📝 Details</div>
    <label>Supplier</label>
    <select name="supplier" id="sup" required><option value="">Select...</option>""" + "".join(f'<option value="{s}">{s}</option>' for s in SUPPLIERS) + r"""</select>
    <label>Amount (£)</label>
    <input type="number" name="total_amount" id="amt" step="0.01" required>
    <label>Date</label>
    <input type="date" name="invoice_date" id="dt">
    <label>Notes</label>
    <textarea name="notes" rows="2"></textarea>
  </div>

  <button type="submit" class="submit-btn" id="sub">Upload Invoice</button>
</form>

<script>
const file = document.getElementById('fileInput');
const preview = document.getElementById('preview');
file.onchange = async () => {
  const f = file.files[0];
  const reader = new FileReader();
  reader.onload = e => { preview.src = e.target.result; preview.style.display = 'block'; };
  reader.readAsDataURL(f);
  
  const fd = new FormData(); fd.append('invoice_image', f);
  const res = await fetch('/parse', {method:'POST', body:fd});
  const data = await res.json();
  if(data.total_amount) document.getElementById('amt').value = data.total_amount;
  if(data.invoice_date) document.getElementById('dt').value = data.invoice_date;
  if(data.supplier) document.getElementById('sup').value = data.supplier;
};

document.getElementById('uploadForm').onsubmit = async (e) => {
  e.preventDefault();
  const btn = document.getElementById('sub');
  btn.disabled = true; btn.innerText = 'Uploading...';
  const fd = new FormData(e.target);
  const res = await fetch('/upload', {method:'POST', body:fd});
  const data = await res.json();
  if(data.success) { alert('Uploaded successfully!'); location.reload(); }
  else { alert('Error: ' + data.error); btn.disabled = false; }
};
</script>
</body></html>"""

@app.route("/parse", methods=["POST"])
def parse():
    f = request.files.get("invoice_image")
    if not f: return jsonify({})
    b64 = base64.b64encode(f.read()).decode()
    return jsonify(ai_parse_invoice(b64, f.content_type or "image/jpeg"))

@app.route("/upload", methods=["POST"])
def upload():
    try:
        f = request.files.get("invoice_image")
        sup = request.form.get("supplier")
        amt = float(request.form.get("total_amount", 0))
        dt = request.form.get("invoice_date")
        
        fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sup[:10]}.jpg"
        f.seek(0); f.save(UPLOADS_DIR / fname)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO portal_uploads (upload_date, staff_name, supplier, invoice_date, total_amount, category, image_filename) VALUES (?,?,?,?,?,?,?)",
                         (datetime.now().strftime("%Y-%m-%d"), "Admin", sup, dt, amt, "Food", fname))
        return jsonify({"success": True})
    except Exception as e: return jsonify({"success": False, "error": str(e)})

@app.route("/api/pending")
def pending():
    auth = request.headers.get("Authorization", "")
    if auth.replace("Bearer ", "") != PORTAL_SECRET: return jsonify([]), 401
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT id, upload_date, staff_name, supplier, invoice_date, total_amount, category, invoice_number, notes, image_filename FROM portal_uploads WHERE synced_to_main = 0").fetchall()
    cols = ["id","upload_date","staff_name","supplier","invoice_date","total_amount","category","invoice_number","notes","image_filename"]
    return jsonify([dict(zip(cols, r)) for r in rows])

@app.route("/api/mark_synced", methods=["POST"])
def mark_synced():
    auth = request.headers.get("Authorization", "")
    if auth.replace("Bearer ", "") != PORTAL_SECRET: return jsonify([]), 401
    ids = request.json.get("ids", [])
    with sqlite3.connect(DB_PATH) as conn:
        for id in ids: conn.execute("UPDATE portal_uploads SET synced_to_main = 1 WHERE id = ?", (id,))
    return jsonify({"success": True})

if __name__ == "__main__":
    from waitress import serve
    print("🚀 INVOICE PORTAL LIVE ON PORT 5050")
    serve(app, host='0.0.0.0', port=5050)
