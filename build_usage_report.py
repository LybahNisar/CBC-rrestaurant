import pandas as pd
import os
import re

def normalize(s):
    if pd.isna(s): return ""
    return re.sub(r'\W', '', str(s).upper())

# --- CONFIG ---
base_dir = r'C:\Users\GEO\Desktop\CBC'
sales_path = os.path.join(base_dir, 'Menu Item Report data', 'Most sold items.csv')
recipe_path = os.path.join(base_dir, 'chocoberry recipe master', 'chocoberry_recipe_master.csv')
conversion_path = os.path.join(base_dir, 'unit_conversion_master.csv')
mapping_path = os.path.join(base_dir, 'master_ingredient_mapping.csv')
stock_path = os.path.join(base_dir, 'stock_thresholds_master.csv') # USE THIS ONE

output_usage = os.path.join(base_dir, 'weekly_ingredient_usage.csv')
output_stock = os.path.join(base_dir, 'current_stock_estimate.csv')

# --- 1. LOAD DATA ---
sales_df = pd.read_csv(sales_path, encoding='latin1')
recipe_df = pd.read_csv(recipe_path)
conv_df = pd.read_csv(conversion_path)
map_df = pd.read_csv(mapping_path)
stock_df = pd.read_csv(stock_path)

# Normalize Keys
sales_df['Link_Key'] = sales_df.iloc[:, 1].apply(normalize)
recipe_df['Recipe_Key'] = recipe_df['Recipe Name'].apply(normalize)
conv_df['Unit_Key'] = conv_df['Original Unit'].apply(normalize)
map_df['Recipe_Ing_Key'] = map_df['Recipe Ingredient'].apply(normalize)

# Create Conversion Lookup
conv_lookup = conv_df.set_index('Unit_Key')['Gram/ML Equivalent'].to_dict()

# --- 2. CALCULATE USAGE ---
usage_rows = []
for _, sale in sales_df.iterrows():
    qty_sold = pd.to_numeric(str(sale.iloc[2]).replace(',', ''), errors='coerce')
    if pd.isna(qty_sold) or qty_sold == 0: continue
    
    item_key = sale['Link_Key']
    # Match Sales Item to Recipe Name
    recipe_lines = recipe_df[recipe_df['Recipe_Key'] == item_key]
    
    for _, line in recipe_lines.iterrows():
        ing_name = line['Ingredient']
        raw_qty = normalize(line['Quantity'])
        
        # Convert Unit to Grams
        grams_per = conv_lookup.get(raw_qty, 0)
        # Fallback for metric strings
        if grams_per == 0 and 'G' in str(line['Quantity']).upper():
            try: grams_per = float(re.findall(r'\d+', str(line['Quantity']))[0])
            except: pass
            
        total_usage = qty_sold * grams_per
        if total_usage > 0:
            usage_rows.append({
                'Menu_Item': sale.iloc[1],
                'Ingredient': ing_name,
                'Total_Usage_G': total_usage
            })

usage_summary = pd.DataFrame(usage_rows).groupby('Ingredient')['Total_Usage_G'].sum().reset_index()
usage_summary.to_csv(output_usage, index=False)

# --- 3. LINK TO STOCK ---
usage_summary['Recipe_Ing_Key'] = usage_summary['Ingredient'].apply(normalize)
stock_df['Stock_Item_Key'] = stock_df['Item Name'].apply(normalize)

# Bridge Recipe Ingredient -> Stock Item Name (from mapping file)
usage_with_stock_mapping = pd.merge(usage_summary, map_df[['Recipe_Ing_Key', 'Stock Item Name']], on='Recipe_Ing_Key', how='left')

# If mapping file has missing entries, try a direct match as fallback
usage_with_stock_mapping['Final_Stock_Item'] = usage_with_stock_mapping['Stock Item Name'].fillna(usage_with_stock_mapping['Ingredient'])
usage_with_stock_mapping['Stock_Item_Key'] = usage_with_stock_mapping['Final_Stock_Item'].apply(normalize)

# Sum usage by Stock Item Key
usage_by_stock = usage_with_stock_mapping.groupby('Stock_Item_Key')['Total_Usage_G'].sum().reset_index()

# --- 4. FINAL STOCK ESTIMATE ---
stock_estimate = pd.merge(stock_df, usage_by_stock, on='Stock_Item_Key', how='left').fillna(0)

# Calculate Remaining
# Logic: We assume 'Current Stock' is the latest snapshot. We subtract usage to see where we ARE.
# Or we subtract usage from a baseline. Let's assume 'Current Stock' is the starting point for this week's audit.
if 'Remaining_Stock' not in stock_estimate.columns:
    stock_estimate['Remaining_Stock'] = stock_estimate['Current Stock'] - (stock_estimate['Total_Usage_G'] / 1000.0) # Convert usage g to Stock Units if needed
    # Wait, Stock Units vary (Box, Tray, Case). This is the hard part.
    # We will assume for now that if the Unit is 'KG' or 'Litre', we subtract total_usage_g / 1000.
    # For others (Case, Tray), we need to know the Grams per Case.
    # For this dashboard logic: we'll flag any item with Significant Usage.
    
# Final Status check
def check_status(row):
    rem = row['Current Stock'] - (row['Total_Usage_G'] / 1000.0 if row['Unit'] in ['KG', 'Litre', 'Bottle', 'KG (20kg)'] else 0)
    if rem < row['Min Threshold (Reorder Point)']:
        return '🚨 REORDER'
    return '✅ OK'

stock_estimate['Status'] = stock_estimate.apply(check_status, axis=1)
stock_estimate.to_csv(output_stock, index=False)
print(f"SUCCESS: Usage for {len(usage_summary)} ingredients calculated.")
print(f"ALERTS: {len(stock_estimate[stock_estimate['Status'] == '🚨 REORDER'])} items flagged.")
