import csv
import re
import os

def normalize(s):
    if not s: return ""
    return re.sub(r'\W', '', str(s).upper())

# Constants
COST_PATH = r'C:\Users\GEO\Desktop\CBC\bought_in_products_audit.csv'
SALES_PATH = r'C:\Users\GEO\Desktop\CBC\Menu Item Report data\Most sold items.csv'
BRIDGE_PATH = r'C:\Users\GEO\Desktop\CBC\sales_to_hq_mapping.csv'
OUTPUT_PATH = r'C:\Users\GEO\Desktop\CBC\master_profitability_lookup.csv'

# 1. Load Costs using standard CSV module (Latin-1 fallback)
cost_lookup = {}
try:
    f = open(COST_PATH, 'r', encoding='utf-8')
    data = list(csv.reader(f))
except:
    f = open(COST_PATH, 'r', encoding='latin1')
    data = list(csv.reader(f))
finally:
    f.close()

for i, row in enumerate(data):
    if i < 3 or len(row) < 7: continue
    name = row[2]
    # Cost can be at index 6 or 4 depending on format? No, we saw 6.
    # We will try Col 6, if fail try Col 4 (Box Cost) / Col 5 (Portions)
    try:
        raw_cost = row[6].strip()
        clean_cost = re.sub(r'[^\d.]', '', raw_cost)
        val = float(clean_cost) if clean_cost else 0
        
        # If Col 6 is 0 or empty, try Col 4 / Col 5
        if val <= 0:
            box_cost = float(re.sub(r'[^\d.]', '', row[4]))
            portions = float(re.sub(r'[^\d.]', '', row[5]))
            val = (box_cost / portions) if portions > 0 else 0
            
        if val > 0:
            cost_lookup[normalize(name)] = {'Cost': val, 'Supplier': row[7] if len(row) > 7 else "HQ"}
    except:
        continue

# 2. Build Naming Bridge
bridge_lookup = {}
with open(BRIDGE_PATH, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        if i == 0 or len(row) < 2: continue
        bridge_lookup[normalize(row[0])] = normalize(row[1])

# 3. Process Sales
results = []
try:
    with open(SALES_PATH, 'r', encoding='latin1') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) < 4: continue
            item_name = row[1]
            qty = float(row[2].replace(',', '')) if row[2] else 0
            rev = float(row[3].replace(',', '').replace('"', '')) if row[3] else 0
            if qty == 0: continue
            
            key = normalize(item_name)
            cost = None
            supplier = "TBC"
            
            # Bridge Match
            if key in bridge_lookup:
                hq_key = bridge_lookup[key]
                if hq_key in cost_lookup:
                    cost = cost_lookup[hq_key]['Cost']
                    supplier = cost_lookup[hq_key]['Supplier']
            
            # Direct Match
            if cost is None and key in cost_lookup:
                cost = cost_lookup[key]['Cost']
                supplier = cost_lookup[key]['Supplier']
                
            price = rev / qty
            results.append({
                'Item Name': item_name,
                'Units Sold': qty,
                'Retail Price (£)': round(price, 2),
                'Unit Cost (£)': cost,
                'Total COGS (£)': round(qty * cost, 2) if cost is not None else 0,
                'Gross Profit (£)': round(price - cost, 2) if cost is not None else 0,
                'GP (%)': round((price - cost) / price * 100, 2) if (cost is not None and price > 0) else 0,
                'Supplier': supplier
            })
except Exception as e:
    print(f"SALES READ ERROR: {e}")

# Save
keys = ['Item Name', 'Units Sold', 'Retail Price (£)', 'Unit Cost (£)', 'Total COGS (£)', 'Gross Profit (£)', 'GP (%)', 'Supplier']
with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=keys)
    writer.writeheader()
    writer.writerows(results)

# Summary
mapped = [r for r in results if r['Unit Cost (£)'] is not None]
total_cogs = sum(r['Total COGS (£)'] for r in mapped)
total_sales = sum(r['Units Sold'] * r['Retail Price (£)'] for r in mapped)
fc_perc = (total_cogs / total_sales * 100) if total_sales > 0 else 0

print(f"COST KEYS: {len(cost_lookup)} | MAPPED: {len(mapped)} / {len(results)}")
print(f"TOTAL WEEKLY COGS: £{total_cogs:,.2f} | FOOD COST %: {fc_perc:.2f}%")
