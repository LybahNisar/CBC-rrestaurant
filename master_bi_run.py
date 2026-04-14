"""
CHOCOBERRY CARDIFF: Unified BI Operations Dashboard v2.0
This script generates a SINGLE master dashboard combining:
1. Weekly Sales Performance & Forecasting
2. Staff Labour Cost Analysis
3. Theoretical Stock Consumption
"""

import os
from bi_sales_report import generate_weekly_report
from bi_operations_rota import generate_rota_analysis
from bi_stock_tracker import generate_stock_usage_report

# Use relative paths for portability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'Final_BI_System')

def run_unified_bi():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print('Generating Unified BI Dashboard...')
    
    # 1. Gather all individual report contents
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    sales_rep = generate_weekly_report(today_str)
    rota_rep = generate_rota_analysis()
    stock_rep = generate_stock_usage_report()
    
    # 2. Combine into ONE single master string
    combined_report = []
    combined_report.append("="*80)
    combined_report.append(" " * 25 + "CHOCOBERRY CARDIFF MASTER BI SYSTEM")
    combined_report.append(" " * 30 + "UNIFIED PERFORMANCE DASHBOARD")
    combined_report.append("="*80)
    
    combined_report.append("\n" + "[ PHASE 1: WEEKLY SALES PERFORMANCE ]")
    combined_report.append(sales_rep)
    
    combined_report.append("\n" + "="*80)
    combined_report.append("[ PHASE 2: STAFF LABOUR EFFICIENCY ]")
    combined_report.append(rota_rep)
    
    combined_report.append("\n" + "="*80)
    combined_report.append("[ PHASE 3: THEORETICAL STOCK TRACKING ]")
    combined_report.append(stock_rep)
    
    combined_report.append(f"\nREPORT GENERATED ON: {today_str}")
    combined_report.append("="*80)
    
    # 3. Save to the new folder
    final_output_path = os.path.join(OUTPUT_DIR, 'CHOCOBERRY_MASTER_DASHBOARD.txt')
    with open(final_output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(combined_report))
    
    print(f'[SUCCESS] Unified Dashboard Created: {final_output_path}')
    print('You can now view all business metrics in ONE single file.')

if __name__ == '__main__':
    run_unified_bi()
