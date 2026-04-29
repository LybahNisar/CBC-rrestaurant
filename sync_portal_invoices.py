"""
╔══════════════════════════════════════════════════════════════════╗
║         CHOCOBERRY — PORTAL → DASHBOARD SYNC                    ║
║  Pulls pending invoice uploads from the staff portal into       ║
║  your main invoices.db (used by the Streamlit dashboard).       ║
║                                                                  ║
║  Run every Monday (or as needed):                               ║
║    python sync_portal_invoices.py                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import json
import urllib.request
from datetime import datetime
from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()


PORTAL_SECRET = os.environ.get("PORTAL_SECRET", "chocoberry2026")
PORTAL_BASE   = os.environ.get("PORTAL_URL", "http://localhost:5050").rstrip("/")

PORTAL_DB  = Path(__file__).parent / "invoices.db"        # portal DB (staff uploads)
MAIN_DB    = Path(__file__).parent / "cbc_invoice_intelligence.db" # main dashboard DB

PORTAL_API = f"{PORTAL_BASE}/api/pending?secret={PORTAL_SECRET}"
MARK_API   = f"{PORTAL_BASE}/api/mark_synced"

# ── Supplier helpers ──────────────────────────────────────────────

def ensure_supplier(conn, name: str) -> int:
    row = conn.execute(
        "SELECT id FROM suppliers WHERE name=?", (name,)
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO suppliers (name, category) VALUES (?,?)",
        (name, "Supplier"),
    )
    return cur.lastrowid


def ensure_tables(conn):
    """Create tables if they don't exist (handles fresh installs)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT UNIQUE,
            category TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            supplier_id    INTEGER,
            invoice_date   TEXT,
            due_date       TEXT,
            total_amount   REAL,
            payment_status TEXT DEFAULT 'UNPAID',
            category       TEXT,
            notes          TEXT,
            image_path     TEXT
        )
    """)
    conn.commit()


# ── Main sync ─────────────────────────────────────────────────────

def sync_from_portal(portal_base=None, portal_secret=None):
    """Pull pending uploads from portal API and insert into main DB."""
    
    # Use provided args or fall back to environment
    p_secret = portal_secret if portal_secret else os.environ.get("PORTAL_SECRET", "chocoberry2026")
    p_base   = portal_base if portal_base else "https://invoiceappcbc-ng5tjkfaikn8wwstgybptu.streamlit.app"
    p_secret = portal_secret if portal_secret else "chocoberry2026"
    
    # Updated for Streamlit Query Param API
    p_api = f"{p_base}/?api=sync&secret={p_secret}"
    
    print("\n" + "=" * 50)
    print("  CHOCOBERRY — Cloud Invoice Sync")
    print(f"  Target: {p_base}")
    print("=" * 50)

    # Fetch from portal
    try:
        with urllib.request.urlopen(p_api) as response:
            if response.getcode() != 200:
                print(f"❌ Portal error: {response.getcode()}")
                return False
            raw_data = response.read().decode('utf-8')
            # Handle potential streamlit wrapping
            if "[" in raw_data:
                json_str = raw_data[raw_data.find("["):raw_data.rfind("]")+1]
                pending = json.loads(json_str)
            else:
                pending = []
    except Exception as e:
        print(f"\n  ERROR: Could not reach portal at {p_api}")
        print(f"  Make sure invoice_portal.py is running first.")
        print(f"  Detail: {e}")
        return

    if not pending:
        print("\n  No new uploads to sync.")
        return

    print(f"\n  Found {len(pending)} pending upload(s).\n")

    import shutil
    base_invoices_dir = Path(__file__).parent / "Invoices"

    with sqlite3.connect(MAIN_DB) as conn:
        ensure_tables(conn)
        synced_ids = []

        for row in pending:
            supplier_id = ensure_supplier(conn, row["supplier"] or "Unknown")
            
            # ── Organise File Structure ───────────────────────────────────
            original_filename = row.get("image_filename")
            new_relative_path = ""
            
            if original_filename:
                src_path = Path(__file__).parent / "invoice_uploads" / original_filename
                if src_path.exists():
                    # Parse date for folder structure
                    try:
                        inv_dt = datetime.strptime(row["invoice_date"] or row["upload_date"], "%Y-%m-%d")
                    except:
                        inv_dt = datetime.now()
                    
                    year_folder  = str(inv_dt.year)
                    month_folder = inv_dt.strftime("%m-%b")
                    supp_name    = "".join(c for c in (row["supplier"] or "Unknown") if c.isalnum() or c==' ').strip()
                    
                    target_dir = base_invoices_dir / year_folder / month_folder / supp_name
                    target_dir.mkdir(parents=True, exist_ok=True)
                    
                    target_path = target_dir / original_filename
                    shutil.move(src_path, target_path)
                    new_relative_path = str(target_path.relative_to(base_invoices_dir.parent))

            conn.execute("""
                INSERT INTO invoices
                  (invoice_number, supplier_id, invoice_date, total_amount,
                   payment_status, category, notes, image_path)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                row.get("invoice_number") or f"PORTAL-{row['id']}",
                supplier_id,
                row.get("invoice_date") or row["upload_date"],
                row["total_amount"],
                "UNPAID",
                row.get("category", "Food"),
                f"Uploaded by {row.get('staff_name','?')} via portal. {row.get('notes','')}".strip(),
                new_relative_path or original_filename or "",
            ))
            synced_ids.append(row["id"])
            print(f"  ✅  {row['supplier']} — £{row['total_amount']:.2f}"
                   f"  [{row.get('staff_name','?')}] -> {new_relative_path}")

        conn.commit()

    # Mark as synced in portal
    try:
        data = json.dumps({"ids": synced_ids}).encode()
        req  = urllib.request.Request(
            m_api,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {p_secret}"
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
        print(f"\n  Marked {result['synced']} upload(s) as synced in portal.")
    except Exception as e:
        print(f"\n  Warning: Could not mark synced in portal: {e}")

    print(f"\n  Done. {len(synced_ids)} invoice(s) added to main dashboard.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    sync_from_portal()
