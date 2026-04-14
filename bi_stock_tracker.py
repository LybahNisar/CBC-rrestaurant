"""
BI System Module 4: Stock Tracking System
Requirement 3.4: Ingredient-level usage tracking based on items sold.
Processes 'Most sold items.csv' and 'chocoberry_recipe_master.csv'.
"""

import csv
import os
import re
from collections import defaultdict

DATA_PATH = r'C:\Users\GEO\Desktop\CBC'
SALES_VOLUME_PATH = os.path.join(DATA_PATH, 'Menu Item Report data', 'Most sold items.csv')
RECIPE_MASTER_PATH = os.path.join(DATA_PATH, 'chocoberry recipe master', 'chocoberry_recipe_master.csv')

def parse_val(val):
    if not val: return 0.0
    return float(str(val).replace(',', '').replace('\"', '').strip())

def clean_name(s):
    # Normalize naming by stripping and removing 'BATCH:' markers
    return s.strip().upper().replace('BATCH:', '').replace('(', '').replace(')', '').strip()

def generate_stock_usage_report():
    # 1. Load Sales Volume
    sales_volume = {} # Item Name -> Count
    with open(SALES_VOLUME_PATH, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = row['Item'].strip()
            count = int(parse_val(row['Items sold']))
            sales_volume[item] = count

    # 2. Map Recipes to Ingredients
    recipes = defaultdict(list)
    with open(RECIPE_MASTER_PATH, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_name = clean_name(row.get('Recipe Name', ''))
            if p_name:
                recipes[p_name].append({
                    'ingredient': row.get('Ingredient', '').strip(),
                    'qty_text': row.get('Quantity', '').strip(),
                    'unit': row.get('Unit/Notes', '').strip()
                })

    # 3. Calculate Ingredient Usage
    ingredient_usage = defaultdict(float) 
    unit_map = {} 
    unmatched_items = []
    
    for item, volume in sales_volume.items():
        cn = clean_name(item)
        if cn in recipes:
            for ing in recipes[cn]:
                ing_name = ing['ingredient']
                qty_str = ing['qty_text']
                try:
                    match = re.search(r'([0-9.]+)', qty_str)
                    if match:
                        qty_num = float(match.group(1))
                        ingredient_usage[ing_name] += (qty_num * volume)
                        unit_map[ing_name] = ing['unit']
                    else:
                        ingredient_usage[ing_name] += volume
                        unit_map[ing_name] = qty_str
                except:
                    continue
        else:
            unmatched_items.append(item)

    # 4. Generate Report
    report = []
    report.append('=' * 60)
    report.append('  BI SYSTEM — ESTIMATED INGREDIENT USAGE (Quarterly)')
    report.append('=' * 60)
    report.append(f'  Analysis based on {len(sales_volume)} items sold.')
    report.append('-' * 60)
    
    report.append(f'  {"Ingredient":<30} {"Est. Usage":>15}')
    report.append(f'  {"-"*30} {"-"*15}')
    
    sorted_usage = sorted(ingredient_usage.items(), key=lambda x: -x[1])
    for ing, usage in sorted_usage[:40]:
        unit = unit_map.get(ing, '')
        report.append(f'  {ing[:30]:<30} {usage:>12,.1f}')

    report.append('-' * 60)
    report.append(f'  Unmatched: {len(unmatched_items)} items.')
    report.append('=' * 60)
    return "\n".join(report)

if __name__ == '__main__':
    print(generate_stock_usage_report())
