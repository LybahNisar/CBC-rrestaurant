"""
╔══════════════════════════════════════════════════════════════════╗
║         CHOCOBERRY — SUPABASE → DASHBOARD SYNC                  ║
║  Pulls pending invoice uploads from Supabase Cloud into         ║
║  your main dashboard database.                                  ║
║                                                                  ║
║  Run every Monday (or as needed):                               ║
║    python sync_portal_invoices.py                               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import datetime

load_dotenv()

# --- CONFIG ---
MAIN_DB      = Path(__file__).parent / "cbc_invoice_intelligence.db"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Supabase credentials missing in .env file!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def ensure_supplier(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM suppliers WHERE name=?", (name,)).fetchone()
    if row: return row[0]
    cur = conn.execute("INSERT INTO suppliers (name, category) VALUES (?,?)", (name, "Supplier"))
    return cur.lastrowid

def sync_from_supabase():
    print("\n" + "=" * 50)
    print("  CHOCOBERRY — SUPABASE CLOUD SYNC")
    print("=" * 50)

    # 1. Fetch pending from Supabase
    try:
        response = supabase.table("portal_uploads").select("*").eq("synced_to_main", False).execute()
        pending = response.data
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        return

    if not pending:
        print("\n  No new uploads to sync. (Everything is up to date)")
        return

    print(f"\n  Found {len(pending)} pending upload(s) in the cloud.\n")

    # 2. Sync to local Dashboard DB
    added_count = 0
    synced_ids = []

    with sqlite3.connect(MAIN_DB) as conn:
        for row in pending:
            supplier_id = ensure_supplier(conn, row["supplier"] or "Unknown")
            
            # Insert into local dashboard
            conn.execute("""
                INSERT INTO invoices
                  (invoice_number, supplier_id, invoice_date, total_amount,
                   payment_status, category, notes, image_path)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                f"CLOUD-{row['id']}", # Unique ID from cloud
                supplier_id,
                row.get("upload_date"),
                row["total_amount"],
                "UNPAID",
                "Food",
                f"Uploaded by {row.get('staff_name','?')} via Supabase Portal.",
                row.get("image_url", "")
            ))
            synced_ids.append(row["id"])
            added_count += 1
            print(f"  [OK] {row['supplier']} - Amount: {row['total_amount']:.2f} [{row.get('staff_name','?')}]")

        conn.commit()

    # 3. Mark as synced in Supabase
    if synced_ids:
        for sid in synced_ids:
            supabase.table("portal_uploads").update({"synced_to_main": True}).eq("id", sid).execute()
        print(f"\n  Successfully marked {len(synced_ids)} records as synced in the Cloud.")

    print(f"\n  Done. {added_count} invoice(s) moved to your local dashboard.")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    sync_from_supabase()
