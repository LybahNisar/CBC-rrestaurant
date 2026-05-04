import pandas as pd
import os
from datetime import datetime, timedelta

# --- CONFIG ---
BASE = r'C:\Users\GEO\Desktop\CBC'
MASTER_PATH = os.path.join(BASE, 'daily_sales_master.csv')
DETAIL_PATH = os.path.join(BASE, 'Sales Summary Data', 'sales_data.csv')
REPORT_OUTPUT = os.path.join(BASE, 'Chocoberry_Diagnostic_Report.txt')

def run_diagnostic():
    # 1. Load Data
    master = pd.read_csv(MASTER_PATH)
    master['date'] = pd.to_datetime(master['date'])
    master = master.sort_values('date')
    
    # 2. Timeline Analysis
    master['week'] = master['date'] - pd.to_timedelta(master['date'].dt.dayofweek, unit='d')
    weekly = master.groupby('week').agg(net=('net','sum'), orders=('orders','sum')).reset_index()
    weekly['aov'] = weekly['net'] / weekly['orders']
    weekly['wow'] = weekly['net'].pct_change() * 100
    
    peak_week = weekly.nlargest(1, 'net').iloc[0]
    last_4_weeks = weekly.tail(4)
    avg_recent = last_4_weeks['net'].mean()
    
    # 3. Monthly Comparison (March vs April)
    master['month'] = master['date'].dt.month
    mar = master[master['month'] == 3]
    apr = master[master['month'] == 4]
    
    mar_aov = mar['net'].sum() / mar['orders'].sum()
    apr_aov = apr['net'].sum() / apr['orders'].sum()
    
    # Day specific drops
    day_stats = []
    for day in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']:
        m_avg = master[(master['day']==day) & (master['month']==3)]['net'].mean()
        a_avg = master[(master['day']==day) & (master['month']==4)]['net'].mean()
        change = (a_avg/m_avg - 1) * 100 if m_avg > 0 else 0
        day_stats.append({'day': day, 'mar': m_avg, 'apr': a_avg, 'change': change})
        
    # 4. Detail Analysis (Channels & Hours)
    det = pd.read_csv(DETAIL_PATH)
    det = det.dropna(subset=['Order time'])
    det = det[det['Order time'].str.contains(r'\d{4}-\d{2}-\d{2}', na=False)]
    det['Order time'] = pd.to_datetime(det['Order time'])
    det['month'] = det['Order time'].dt.month
    det['hour'] = det['Order time'].dt.hour
    if 'Order ID' in det.columns: det = det.drop_duplicates(subset=['Order ID'])

    def std_ch(name):
        n = str(name).lower()
        if 'uber' in n: return 'Uber'
        if 'deliveroo' in n: return 'Deliveroo'
        return 'In-Store (POS)'
    det['channel'] = det['Sales channel name'].apply(std_ch)
    
    # Channel Share
    ch_mar = det[det['month'] == 3].groupby('channel')['Net sales'].sum()
    ch_apr = det[det['month'] == 4].groupby('channel')['Net sales'].sum()
    mar_pos = ch_mar.get('In-Store (POS)',0)/ch_mar.sum()*100
    apr_pos = ch_apr.get('In-Store (POS)',0)/ch_apr.sum()*100
    
    # Hourly Share
    h_mar = det[det['month'] == 3].groupby('hour')['Net sales'].sum()
    h_apr = det[det['month'] == 4].groupby('hour')['Net sales'].sum()
    mar_mid = h_mar.get(0,0)/h_mar.sum()*100
    apr_mid = h_apr.get(0,0)/h_apr.sum()*100

    # 5. Build Report
    lines = []
    lines.append("==================================================================")
    lines.append("CHOCOBERRY FORENSIC DIAGNOSTIC REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}")
    lines.append("==================================================================")
    lines.append("")
    lines.append("--- 1. EXECUTIVE SUMMARY ---")
    lines.append(f"PEAK REVENUE:  GBP {peak_week['net']:,.0f} (Week of {peak_week['week'].strftime('%d %b')})")
    lines.append(f"RECENT AVG:    GBP {avg_recent:,.0f} (Last 4 Weeks)")
    lines.append(f"REVENUE GAP:   GBP {peak_week['net'] - avg_recent:,.0f} per week")
    lines.append("")
    lines.append(f"MARCH AOV:     GBP {mar_aov:.2f}")
    lines.append(f"APRIL AOV:     GBP {apr_aov:.2f}  (Trend: UP - Pricing is healthy)")
    lines.append("")
    lines.append("--- 2. DAY-OF-WEEK COLLAPSE (MAR vs APR) ---")
    for d in day_stats:
        status = "CRITICAL" if d['change'] < -10 else "WATCH" if d['change'] < 0 else "GROWING"
        lines.append(f"{d['day']:<10}: Mar GBP {d['mar']:,.0f} -> Apr GBP {d['apr']:,.0f} ({d['change']:+.1f}%) {status}")
    
    lines.append("")
    lines.append("--- 3. CHANNEL & HOURLY SHIFTS ---")
    lines.append(f"IN-STORE SHARE:  {mar_pos:.1f}% -> {apr_pos:.1f}% (Loss to apps)")
    lines.append(f"MIDNIGHT SHARE:  {mar_mid:.1f}% -> {apr_mid:.1f}% (Loss of late-night)")
    
    lines.append("")
    lines.append("--- 4. WEEKLY TIMELINE ---")
    for _, row in weekly.tail(6).iterrows():
        lines.append(f"Week {row['week'].strftime('%d %b')}: GBP {row['net']:,.0f} ({int(row['orders'])} orders) WoW: {row['wow']:+.1f}%")

    report_text = "\n".join(lines)
    with open(REPORT_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(report_text)
    print(f"\nReport saved to: {REPORT_OUTPUT}")

if __name__ == "__main__":
    run_diagnostic()
