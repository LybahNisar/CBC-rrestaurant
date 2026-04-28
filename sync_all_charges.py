import pandas as pd
import os

master_sales_path = 'daily_sales_master.csv'
historical_overview_path = 'Sales Summary Data/sales_overview.csv'

m_df = pd.read_csv(master_sales_path)
h_df = pd.read_csv(historical_overview_path)

# Ensure date formats match
m_df['date'] = pd.to_datetime(m_df['date']).dt.strftime('%Y-%m-%d')
h_df['Order time'] = pd.to_datetime(h_df['Order time']).dt.strftime('%Y-%m-%d')

# Ensure Charges column exists
if 'Charges' not in m_df.columns:
    m_df['Charges'] = 0.0

# Map charges from historical overview to master sales
for idx, row in m_df.iterrows():
    match = h_df[h_df['Order time'] == row['date']]
    if not match.empty:
        # Sum charges for that date (in case there are multiple entries)
        val = 0.0
        for v in match['Charges']:
            try:
                val += float(str(v).replace(',','').replace('£','').strip())
            except: pass
        m_df.at[idx, 'Charges'] = val

m_df.to_csv(master_sales_path, index=False)
print(f"Fully synchronized Charges for {len(m_df)} days. Total Charges: £{m_df['Charges'].sum():,.2f}")
