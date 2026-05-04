import pandas as pd
import os
from datetime import datetime

# Paths
BASE_DIR = r"C:\Users\GEO\Desktop\CBC"
NEW_DATA_DIR = os.path.join(BASE_DIR, "0_UPLOAD_HERE")
MASTER_SALES_FILE = os.path.join(BASE_DIR, "daily_sales_master.csv")
MASTER_SUMMARY_DIR = os.path.join(BASE_DIR, "Sales Summary Data")

def clean_currency(val):
    if pd.isna(val) or val == '':
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace(',', '').replace('£', '').strip())

def merge_daily_sales():
    print("Merging daily sales master (including Charges)...")
    master_df = pd.read_csv(MASTER_SALES_FILE)
    # Ensure master has Charges column
    if 'Charges' not in master_df.columns:
        master_df['Charges'] = 0.0
        
    last_date = pd.to_datetime(master_df['date']).max()

    new_overview = pd.read_csv(os.path.join(NEW_DATA_DIR, "sales_overview.csv"))
    new_overview = new_overview[new_overview['Order time'].notna()]
    new_overview = new_overview[new_overview['Order time'].str.contains(r'\d{4}-\d{2}-\d{2}')]
    new_overview['Order time'] = pd.to_datetime(new_overview['Order time'])
    
    new_data = new_overview[new_overview['Order time'] > last_date].copy()
    if new_data.empty:
        print("No new daily data to add to master.")
        return

    new_data = new_data.sort_values('Order time')
    new_rows = []
    for _, row in new_data.iterrows():
        dt = row['Order time']
        new_rows.append({
            'date': dt.strftime('%Y-%m-%d'),
            'label': dt.strftime('%d %b'),
            'day': dt.strftime('%A'),
            'net': clean_currency(row['Net sales']),
            'orders': int(row['Orders']),
            'revenue': clean_currency(row['Revenue']),
            'tax': clean_currency(row['Tax on net sales']),
            'refunds': clean_currency(row['Refunds']),
            'Charges': clean_currency(row.get('Charges', 0.0)),
            'rolling7': 0.0
        })

    final_df = pd.concat([master_df, pd.DataFrame(new_rows)], ignore_index=True)
    # Ensure all charges are numeric
    final_df['Charges'] = final_df['Charges'].apply(clean_currency)
    final_df['rolling7'] = final_df['net'].rolling(window=7).mean().fillna(final_df['net']).round(2)
    final_df.to_csv(MASTER_SALES_FILE, index=False)
    print(f"Added {len(new_rows)} days to master (with Charges).")

def merge_appended_files():
    print("\nAppending new records to historical files...")
    append_files = ["net_sales_per_day.csv", "sales_overview.csv", "sales_data.csv"]
    for filename in append_files:
        master_path = os.path.join(MASTER_SUMMARY_DIR, filename)
        new_path = os.path.join(NEW_DATA_DIR, filename)
        if not os.path.exists(new_path) or not os.path.exists(master_path): continue
        m_df = pd.read_csv(master_path)
        n_df = pd.read_csv(new_path)
        m_df = m_df[m_df.iloc[:,0].notna()]; n_df = n_df[n_df.iloc[:,0].notna()]
        if 'Total' in str(n_df.iloc[-1, 0]): n_df = n_df.iloc[:-1]
        final_df = pd.concat([m_df, n_df], ignore_index=True).drop_duplicates()
        final_df.to_csv(master_path, index=False)

def merge_sum_files():
    print("\nIncrementing summary totals...")
    sum_files = ["charges_summary.csv","net_sales_by_dispatch_type.csv","net_sales_by_hour_of_day.csv","net_sales_by_payment_method.csv","net_sales_by_property.csv","net_sales_by_sales_channel.csv","net_sales_per_day_of_week.csv","revenue_after_refunds.csv","revenue_summary.csv","total_charges.csv"]
    for filename in sum_files:
        master_path = os.path.join(MASTER_SUMMARY_DIR, filename); new_path = os.path.join(NEW_DATA_DIR, filename)
        if not os.path.exists(new_path) or not os.path.exists(master_path): continue
        master_raw = pd.read_csv(master_path, header=None); new_raw = pd.read_csv(new_path, header=None)
        max_cols = min(master_raw.shape[1], new_raw.shape[1])
        for col in range(max_cols):
            try:
                for row_idx in range(master_raw.shape[0]):
                    m_val = str(master_raw.iloc[row_idx, col]); n_val = str(new_raw.iloc[row_idx, col])
                    clean_m = m_val.replace(',','').replace('.','').replace('-',''); clean_n = n_val.replace(',','').replace('.','').replace('-','')
                    if clean_m.isdigit() and clean_n.isdigit():
                         mv = clean_currency(m_val); nv = clean_currency(n_val)
                         master_raw.iloc[row_idx, col] = f"{mv + nv:,.2f}"
            except: pass
        master_raw.to_csv(master_path, index=False, header=False)

if __name__ == "__main__":
    merge_daily_sales()
    merge_appended_files()
    merge_sum_files()
    print("\nAll Sales Summary Data Files Synchronized (with Charges)!")
