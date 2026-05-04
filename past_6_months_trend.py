import pandas as pd
import os
from datetime import datetime

BASE = r'C:\Users\GEO\Desktop\CBC'
MASTER_PATH = os.path.join(BASE, 'daily_sales_master.csv')

def show_6_month_trend():
    # Load master sales data
    master = pd.read_csv(MASTER_PATH)
    master['date'] = pd.to_datetime(master['date'])
    master = master.sort_values('date')
    
    # Group by month
    master['month_period'] = master['date'].dt.to_period('M')
    monthly = master.groupby('month_period').agg(
        net_sales=('net', 'sum'),
        orders=('orders', 'sum')
    ).reset_index()
    
    # Calculate AOV
    monthly['aov'] = monthly['net_sales'] / monthly['orders']
    
    # Calculate Month-on-Month Growth
    monthly['mom_growth'] = monthly['net_sales'].pct_change() * 100
    
    # Get last 6 months
    trend = monthly.tail(6)
    
    print("==================================================================")
    print("CHOCOBERRY 6-MONTH SALES TREND REPORT")
    print(f"Generated: {datetime.now().strftime('%d %b %Y')}")
    print("==================================================================")
    print(f"{'Month':<10} | {'Net Sales':<12} | {'Orders':<8} | {'AOV':<8} | {'Growth':<8}")
    print("-" * 60)
    
    for _, row in trend.iterrows():
        month_str = row['month_period'].strftime('%b %Y')
        growth_str = f"{row['mom_growth']:+.1f}%" if not pd.isna(row['mom_growth']) else "---"
        print(f"{month_str:<10} | GBP {row['net_sales']:>8,.0f} | {int(row['orders']):>8} | GBP {row['aov']:>4.2f} | {growth_str:>6}")
    
    print("==================================================================")
    print("KEY TRENDS:")
    best_month = trend.loc[trend['net_sales'].idxmax()]
    print(f"* BEST MONTH: {best_month['month_period'].strftime('%b %Y')} (GBP {best_month['net_sales']:,.0f})")
    
    latest_aov = trend.iloc[-1]['aov']
    start_aov = trend.iloc[0]['aov']
    aov_change = ((latest_aov / start_aov) - 1) * 100
    print(f"* AOV TREND:  {aov_change:+.1f}% change in customer spend per visit.")

if __name__ == "__main__":
    show_6_month_trend()
