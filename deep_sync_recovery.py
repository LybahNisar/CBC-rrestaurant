import sqlite3
import json
import urllib.request
from datetime import datetime
from pathlib import Path
import os

# --- CONFIG ---
PORTAL_SECRET = "CBC!18"
PORTAL_BASE   = "https://invoiceappcbc-ng5tjkfaikn8wwstgybptu.streamlit.app"
MAIN_DB       = Path(__file__).parent / "cbc_invoice_intelligence.db"
API_URL       = f"{PORTAL_BASE}/?api=sync&mode=history&secret={PORTAL_SECRET}"

def ensure_supplier(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM suppliers WHERE name=?", (name,)).fetchone()
    if row: return row[0]
    cur = conn.execute("INSERT INTO suppliers (name, category) VALUES (?,?)", (name, "Supplier"))
    return cur.lastrowid

def run_deep_recovery():
    print("\n" + "=" * 50)
    print("  CHOCOBERRY - DEEP DATA RECOVERY")
    print(f"  Target: {PORTAL_BASE}")
    print("=" * 50)

    # 1. Fetch ALL data via browser-mimicking request
    try:
        req = urllib.request.Request(
            API_URL, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        )
        with urllib.request.urlopen(req) as response:
            raw_data = response.read().decode('utf-8')
            if "[" in raw_data:
                json_str = raw_data[raw_data.find("["):raw_data.rfind("]")+1]
                all_invoices = json.loads(json_str)
            else:
                print("ERROR: No data found on portal.")
                return
    except Exception as e:
        print(f"ERROR: Connection Error: {e}")
        return

    if not all_invoices:
        print("No invoices found to recover.")
        return

    print(f"Found {len(all_invoices)} invoices in cloud. Synchronizing...")

    # 2. Sync to local DB
    added_count = 0
    skipped_count = 0
    
    with sqlite3.connect(MAIN_DB) as conn:
        for row in all_invoices:
            # Check if already exists by number and date
            inv_num = row.get("invoice_number") or f"PORTAL-{row['id']}"
            inv_date = row.get("invoice_date") or row["upload_date"]
            
            exists = conn.execute("SELECT id FROM invoices WHERE invoice_number=? AND invoice_date=?", 
                                 (inv_num, inv_date)).fetchone()
            
            if exists:
                skipped_count += 1
                continue
                
            supplier_id = ensure_supplier(conn, row["supplier"] or "Unknown")
            conn.execute("""
                INSERT INTO invoices
                  (invoice_number, supplier_id, invoice_date, total_amount, payment_status, category, notes)
                VALUES (?,?,?,?,?,?,?)
            """, (
                inv_num,
                supplier_id,
                inv_date,
                row["total_amount"],
                "UNPAID",
                row.get("category", "Food"),
                f"Recovered via Deep Sync. {row.get('notes','')}".strip()
            ))
            added_count += 1
            print(f"  OK Recovered: {row['supplier']} - £{row['total_amount']}")

        conn.commit()

    print("\n" + "=" * 50)
    print(f"  RECOVERY COMPLETE")
    print(f"  Added: {added_count} | Skipped: {skipped_count}")
    print("=" * 50 + "\n")

if __name__ == "__main__":
    run_deep_recovery()
