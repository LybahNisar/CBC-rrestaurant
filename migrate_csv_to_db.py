import pandas as pd
from invoice_db import InvoiceDB
import os
from datetime import datetime

def migrate():
    csv_path = r'C:\Users\GEO\Desktop\CBC\Invoices\chocoberry_invoices_all_updated.csv'
    if not os.path.exists(csv_path):
        # Check root if not in Invoices folder
        csv_path = 'chocoberry_invoices_all_updated.csv'
        if not os.path.exists(csv_path):
            print(f"ERROR: Source CSV missing: {csv_path}")
            return

    print(f"Starting Historical Data Migration from {csv_path}...")
    db = InvoiceDB()
    
    # Load CSV
    df = pd.read_csv(csv_path)
    
    # Helper to clean currency strings
    def clean_money(val):
        if pd.isna(val): return 0.0
        return float(str(val).replace('£', '').replace(',', '').strip())

    # Group by (Supplier, Invoice Number) to aggregate line items
    # Columns expected: Supplier,Invoice Number,Invoice Date,Due Date,Item Description,Qty,Unit,Unit Rate (£),Line Total (£)
    
    invoices_processed = 0
    items_processed = 0
    
    grouped = df.groupby(['Supplier', 'Invoice Number'])
    
    for (supplier_name, inv_no), group in grouped:
        first_row = group.iloc[0]
        
        # 1. Ensure Supplier exists
        supp_id = db.add_supplier(supplier_name, category="General")
        
        # 2. Extract Master Data
        inv_date = first_row.get('Invoice Date', datetime.now().strftime('%Y-%m-%d'))
        due_date = first_row.get('Due Date', inv_date)
        
        # 3. Process Line Items
        items = []
        total_gross = 0.0
        for _, row in group.iterrows():
            desc = str(row.get('Item Description', 'Unknown Item'))
            if "TOTAL" in desc.upper(): continue # Skip summary rows
            
            qty = float(row.get('Qty', 1))
            rate = clean_money(row.get('Unit Rate (£)', 0))
            line_total = clean_money(row.get('Line Total (£)', 0))
            
            items.append({
                'item_description': desc,
                'quantity':         qty,
                'unit':             str(row.get('Unit', 'unit')),
                'unit_rate':        rate,
                'line_total':       line_total
            })
            total_gross += line_total
        
        # 4. Insert Master Record
        master_data = {
            'invoice_number': str(inv_no),
            'supplier_id':    supp_id,
            'invoice_date':   inv_date,
            'due_date':       due_date,
            'total_amount':   round(total_gross, 2),
            'payment_status': 'PAID', # Historical data is likely paid
            'category':       'Legacy Migration',
            'notes':          'Imported from historical CSV'
        }
        
        db.insert_invoice(master_data, items=items)
        invoices_processed += 1
        items_processed += len(items)

    print(f"SUCCESS: MIGRATION COMPLETE:")
    print(f"   - {invoices_processed} Invoices Created")
    print(f"   - {items_processed} Line Items Processed")

if __name__ == "__main__":
    migrate()
