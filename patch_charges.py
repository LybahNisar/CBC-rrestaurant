import pandas as pd
import os

path = 'daily_sales_master.csv'
df = pd.read_csv(path)
if 'Charges' not in df.columns:
    df['Charges'] = 0.0
    
# Also ensure we pull the actual charges for the existing April dates
new_overview = pd.read_csv('New_Sales_April/sales_overview.csv')
new_overview['Order time'] = pd.to_datetime(new_overview['Order time']).dt.strftime('%Y-%m-%d')

for idx, row in df.iterrows():
    match = new_overview[new_overview['Order time'] == row['date']]
    if not match.empty:
        # Clean currency
        charge_val = str(match.iloc[0].get('Charges', 0.0)).replace(',','').replace('£','').strip()
        df.at[idx, 'Charges'] = float(charge_val)

df.to_csv(path, index=False)
print("Updated Charges column in master CSV.")
