"""
Data Cleanup Script — Run once to produce clean, production-ready CSV files.
Fixes:
  1. Best-selling categories — merges duplicates (Shakes + SHAKES → SHAKES)
  2. Menu with options — removes ** formatting artifacts from category names
  3. Prints recipe_correction_template status
"""

import csv
import os
from collections import defaultdict

BASE = r'C:\Users\GEO\Desktop\CBC'

# ─────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────
def clean_num(val):
    try:
        return float(str(val).replace(',', '').replace('"', '').strip())
    except:
        return 0.0

# ─────────────────────────────────────────────────────────
# FIX 1: Best-selling categories — merge duplicates
# ─────────────────────────────────────────────────────────
print("=" * 60)
print("FIX 1: Merging duplicate categories...")

CAT_IN  = os.path.join(BASE, 'Menu Item Report data', 'Best-selling categories.csv')
CAT_OUT = os.path.join(BASE, 'Menu Item Report data', 'Best-selling categories CLEAN.csv')

EXCLUDE = {'ANY ALLERGENS?', 'ADD ONS BREAKFAST', 'ADD ONS BREAKFAST',
           'HAPPY HOUR PROMOTIONS', '', 'NAN'}

merged = defaultdict(lambda: {'Sales': 0.0, 'Items sold': 0})

with open(CAT_IN, 'r', encoding='utf-8-sig', errors='replace') as f:
    reader = csv.DictReader(f)
    raw_rows = list(reader)

for row in raw_rows:
    cat = row.get('Category', '').strip().upper()
    if not cat or cat in EXCLUDE:
        continue
    merged[cat]['Sales']      += clean_num(row.get('Sales', 0))
    merged[cat]['Items sold'] += int(clean_num(row.get('Items sold', 0)))

# Sort by revenue descending
sorted_cats = sorted(merged.items(), key=lambda x: -x[1]['Sales'])

with open(CAT_OUT, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['Rank', 'Category', 'Sales (£)', 'Items Sold'])
    for i, (cat, vals) in enumerate(sorted_cats, 1):
        writer.writerow([i, cat, f"{vals['Sales']:.2f}", vals['Items sold']])

print(f"  Original rows  : {len(raw_rows)}")
print(f"  After merge    : {len(sorted_cats)} unique categories")
print(f"  Saved to       : {CAT_OUT}")
print("\n  Top 10 Categories (Merged):")
for i, (cat, vals) in enumerate(sorted_cats[:10], 1):
    print(f"    {i:>2}. {cat:<40} £{vals['Sales']:>9,.2f}  ({vals['Items sold']} items)")

# ─────────────────────────────────────────────────────────
# FIX 2: Menu with options — clean category names
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("FIX 2: Normalising menu category names...")

MENU_IN  = os.path.join(BASE, 'chocoberry menu with options', 'chocoberry_menu_with_options_v3.csv')
MENU_OUT = os.path.join(BASE, 'chocoberry menu with options', 'chocoberry_menu_CLEAN.csv')

def clean_category(cat):
    """Remove ** formatting, strip whitespace, title case."""
    cat = cat.strip().replace('**', '').strip()
    # Map header rows like '**DESSERTS [ALL DAY]**' to 'Desserts [All Day]'
    return cat

with open(MENU_IN, 'r', encoding='utf-8-sig', errors='replace') as f:
    menu_rows = list(csv.DictReader(f))

original_cats = set(r.get('Category', '').strip() for r in menu_rows)
fixed = 0

with open(MENU_OUT, 'w', newline='', encoding='utf-8-sig') as f:
    fieldnames = ['Category', 'Item Name', 'Price', 'Description', 'Options/Variants', 'Option Prices']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in menu_rows:
        orig_cat = row.get('Category', '').strip()
        new_cat  = clean_category(orig_cat)
        if new_cat != orig_cat:
            fixed += 1
        # Skip rows that are pure section headers (no item name)
        if not row.get('Item Name', '').strip():
            continue
        writer.writerow({
            'Category':        new_cat,
            'Item Name':       row.get('Item Name', '').strip(),
            'Price':           row.get('Price', '').strip(),
            'Description':     row.get('Description', '').strip(),
            'Options/Variants':row.get('Options/Variants', '').strip(),
            'Option Prices':   row.get('Option Prices', '').strip(),
        })

# Count clean stats
with open(MENU_OUT, 'r', encoding='utf-8-sig') as f:
    clean_rows = list(csv.DictReader(f))
clean_cats = set(r['Category'] for r in clean_rows)

print(f"  Categories before: {len(original_cats)} (with ** artifacts)")
print(f"  Categories after : {len(clean_cats)} (clean)")
print(f"  Rows fixed       : {fixed}")
print(f"  Items with no price: {sum(1 for r in clean_rows if not r['Price'].strip())}")
print(f"  Saved to         : {MENU_OUT}")

# ─────────────────────────────────────────────────────────
# REPORT 3: Recipe Correction Template — what needs filling
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("REPORT 3: Recipe Correction Template — items needing data")

TPL = os.path.join(BASE, 'recipe_correction_template.csv')
with open(TPL, 'r', encoding='utf-8-sig', errors='replace') as f:
    lines = f.readlines()

# Skip first header description line, then parse
import io
data_lines = ''.join(lines[1:])  # skip the comment line
reader = csv.DictReader(io.StringIO(data_lines))
tpl_rows = list(reader)

empty = [r for r in tpl_rows if not r.get('Base Ingredient', '').strip()
         or r.get('Base Ingredient', '').strip() == 'Enter details here...']

print(f"  Total items in template: {len(tpl_rows)}")
print(f"  Items NOT yet filled in: {len(empty)}")
print(f"\n  Items you need to fill in (with Q1 sales volume):")
print(f"  {'Item':<45} {'Sold Q1':>8}  {'Fields Needed'}")
print(f"  {'-'*45} {'-'*8}  {'-'*30}")

for r in tpl_rows[:20]:
    name = r.get('Flipdish Item Name', '').strip()
    sold = r.get('Q1 Units Sold', '').strip()
    base = r.get('Base Ingredient', '').strip()
    status = '[OK] Filled' if base and base != 'Enter details here...' else '[!!] EMPTY -- needs: Base Ingredient, Qty, Sauce, Price'
    print(f"  {name:<45} {sold:>8}  {status}")

print("\n  COLUMNS TO FILL PER ROW:")
print("    Qty (g/ml)       -> e.g.  '30g'")
print("    Est. Retail Price-> e.g.  '6.50'")
# ─────────────────────────────────────────────────────────
# FIX 4: Invoice Cleaning & Unit Normalization
# ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("FIX 4: Normalising supplier unit costs from invoices...")

INV_IN  = os.path.join(BASE, 'Invoices', 'chocoberry_invoices_all_updated.csv')
COST_OUT = os.path.join(BASE, 'Invoices', 'supplier_unit_costs.csv')

import re

def extract_weight_qty(desc):
    """
    Tries to find numeric weights in descriptions like '(15 KG)', '(2x3Kg)', '(24 Pcs)'.
    Returns (qty, unit)
    """
    desc = desc.upper()
    # Case 1: (2x3Kg) -> 6kg
    multi = re.search(r'\((\d+)X(\d+(\.\d+)?)\s*(KG|LTR|PCS)', desc)
    if multi:
        return float(multi.group(1)) * float(multi.group(2)), multi.group(4)
    
    # Case 2: (15 KG)
    single = re.search(r'\((\d+(\.\d+)?)\s*(KG|LTR|PCS|G|Pcs)', desc)
    if single:
        return float(single.group(1)), single.group(3)
        
    return 1.0, "UNIT"

with open(INV_IN, 'r', encoding='utf-8-sig', errors='replace') as f:
    inv_rows = list(csv.DictReader(f))

# We want unique item costs (taking the most recent rate)
supplier_master = {}

for row in inv_rows:
    item = row.get('Item Description', '').strip()
    rate = clean_num(row.get('Unit Rate (£)', 0))
    raw_unit = row.get('Unit', '').strip()
    
    if not item or rate <= 0:
        continue
        
    net_qty, base_unit = extract_weight_qty(item)
    if base_unit == "UNIT":
        base_unit = raw_unit.upper()
        
    price_per_base = rate / net_qty if net_qty > 0 else rate
    
    supplier_master[item] = {
        'Supplier': row.get('Supplier'),
        'Raw Unit': raw_unit,
        'Base Unit': base_unit,
        'Net Qty': net_qty,
        'Invoice Rate (£)': rate,
        'Price per Base (£)': price_per_base
    }

with open(COST_OUT, 'w', newline='', encoding='utf-8-sig') as f:
    fieldnames = ['Item Description', 'Supplier', 'Raw Unit', 'Net Qty', 'Base Unit', 'Invoice Rate (£)', 'Price per Base (£)']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for item, vals in supplier_master.items():
        writer.writerow({
            'Item Description': item,
            'Supplier':         vals['Supplier'],
            'Raw Unit':        vals['Raw Unit'],
            'Net Qty':         f"{vals['Net Qty']:.2f}",
            'Base Unit':       vals['Base Unit'],
            'Invoice Rate (£)': f"{vals['Invoice Rate (£)']:.2f}",
            'Price per Base (£)': f"{vals['Price per Base (£)']:.4f}"
        })

print(f"  Invoices processed: {len(inv_rows)}")
print(f"  Unique items found : {len(supplier_master)}")
print(f"  Saved to           : {COST_OUT}")

print("\n" + "=" * 60)
print("Done. All clean files saved and Supplier Master generated.")
