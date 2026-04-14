"""
BI System Module 3: Staff Rota & Cost Analysis (FIXED v2)
Requirement 3.3: Labour cost vs revenue analysis per day
to reduce overstaffing and improve scheduling efficiency.

FIX LOG:
- Bug 1 Fixed: Now reads 'Wage (£)' column (was incorrectly reading 'Wage Pattern')
- Bug 2 Fixed: Removed day-column logic — rota CSV only has weekly totals per person
- Correct weekly labour: Sum of all Wage (£) rows = £3,606.34
"""

import csv
import os
from datetime import datetime

DATA_PATH = r'C:\Users\GEO\Desktop\CBC'
ROTA_PATH = os.path.join(DATA_PATH, 'Rota week 30 march - 05 april 2026', 'rota_week_30mar_05apr_2026.csv')
SALES_OVERVIEW = os.path.join(DATA_PATH, 'Sales Summary Data', 'sales_overview.csv')

# The rota week covers these 7 days
ROTA_WEEK_DATES = [
    '2026-03-30', '2026-03-31', '2026-04-01', '2026-04-02',
    '2026-04-03', '2026-04-04', '2026-04-05'
]

def parse_currency(val):
    if not val: return 0.0
    return float(str(val).replace(',', '').replace('"', '').replace('£', '').strip())

def generate_rota_analysis():
    # --- STEP 1: Read actual wages from rota (FIXED) ---
    staff_list = []
    total_labour = 0.0

    with open(ROTA_PATH, 'r', encoding='utf-8-sig', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('Name', '').strip()
            role = row.get('Role', '').strip()
            dept = row.get('Department', '').strip()
            # FIXED: correct column name is 'Wage (£)'
            wage_raw = row.get('Wage (£)', '0')
            wage = parse_currency(wage_raw)

            if name:
                staff_list.append({
                    'name': name,
                    'role': role,
                    'dept': dept,
                    'wage': wage
                })
                total_labour += wage

    # --- STEP 2: Get weekly revenue from sales data ---
    weekly_revenue = 0.0
    daily_data = {}

    with open(SALES_OVERVIEW, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get('Order time', '').strip()
            if date in ROTA_WEEK_DATES:
                rev = parse_currency(row.get('Revenue', '0'))
                orders = int(parse_currency(row.get('Orders', '0')))
                daily_data[date] = {'revenue': rev, 'orders': orders}
                weekly_revenue += rev

    # --- STEP 3: Labour ratio (weekly total) ---
    labour_ratio = (total_labour / weekly_revenue * 100) if weekly_revenue > 0 else 0

    # --- STEP 4: Build Report ---
    report = []
    report.append('=' * 65)
    report.append('  BI SYSTEM — LABOUR COST vs. REVENUE ANALYSIS (FIXED v2)')
    report.append('  Week Period: 30 March – 05 April 2026')
    report.append('=' * 65)

    # Staff breakdown
    report.append(f'\n  {"Name":<20} {"Dept":<10} {"Role":<22} {"Wage (£)":>9}')
    report.append(f'  {"-"*20} {"-"*10} {"-"*22} {"-"*9}')
    for s in staff_list:
        flag = ' ⚠️ (check)' if s['wage'] == 0.0 else ''
        report.append(f'  {s["name"]:<20} {s["dept"]:<10} {s["role"]:<22} £{s["wage"]:>7.2f}{flag}')

    report.append(f'\n  {"TOTAL WEEKLY LABOUR COST":<52} £{total_labour:>7.2f}')
    report.append('=' * 65)

    # Revenue vs Labour
    report.append(f'\n  WEEKLY SUMMARY')
    report.append(f'  {"-"*63}')
    report.append(f'  {"Date":<14} {"Day":<5} {"Revenue":>10} {"Labour Share":>14} {"Ratio %":>8}')
    report.append(f'  {"-"*14} {"-"*5} {"-"*10} {"-"*14} {"-"*8}')

    # Distribute labour evenly across 7 days for day-by-day view
    daily_labour_share = total_labour / 7

    available_dates = sorted(daily_data.keys())
    for date in available_dates:
        day_name = datetime.strptime(date, '%Y-%m-%d').strftime('%a')
        rev = daily_data[date]['revenue']
        ratio = (daily_labour_share / rev * 100) if rev > 0 else 0
        flag = ' 🔴 HIGH' if ratio > 35 else ' 🟡 OK' if ratio > 25 else ' 🟢 EFFICIENT'
        report.append(f'  {date:<14} {day_name:<5} £{rev:>9,.2f} £{daily_labour_share:>12,.2f} {ratio:>7.1f}%{flag}')

    report.append(f'  {"-"*63}')
    report.append(f'\n  Total Weekly Revenue  : £{weekly_revenue:,.2f}')
    report.append(f'  Total Weekly Labour   : £{total_labour:,.2f}')
    report.append(f'  Overall Labour Ratio  : {labour_ratio:.1f}%')

    if labour_ratio > 35:
        report.append('  ⚠️  RECOMMENDATION: Labour cost too high. Review staffing hours.')
    elif labour_ratio < 20:
        report.append('  ✅ EFFICIENT: Labour ratio is excellent. Monitor service quality.')
    else:
        report.append('  ✅ ON TARGET: Labour ratio is within the 20-35% healthy range.')

    report.append('=' * 65)
    return '\n'.join(report)

if __name__ == '__main__':
    print(generate_rota_analysis())
