"""
CHOCOBERRY INTELLIGENCE — FULL SUMMARY DATA REBUILD
Rebuilds ALL Sales Summary Data CSVs from scratch using:
  1. daily_sales_master.csv (daily totals — ground truth)
  2. sales_data.csv (order-level detail — for hourly/channel/dispatch breakdown)
Date range: 2026-01-01 to 2026-04-22
"""
import pandas as pd
import os

BASE = r"C:\Users\GEO\Desktop\CBC"
SUMMARY_DIR = os.path.join(BASE, "Sales Summary Data")
MASTER_PATH = os.path.join(BASE, "daily_sales_master.csv")
DETAIL_PATH = os.path.join(SUMMARY_DIR, "sales_data.csv")

def clean_val(v):
    try:
        return float(str(v).replace(',','').replace('£','').strip())
    except:
        return 0.0

print("Loading ground truth data...")
master = pd.read_csv(MASTER_PATH)
master['date'] = pd.to_datetime(master['date'])
master['net']     = master['net'].apply(clean_val)
master['orders']  = master['orders'].apply(clean_val)
master['revenue'] = master['revenue'].apply(clean_val)
master['tax']     = master['tax'].apply(clean_val)
master['refunds'] = master['refunds'].apply(clean_val)
master['Charges'] = master['Charges'].apply(clean_val)

total_net     = master['net'].sum()
total_orders  = int(master['orders'].sum())
total_revenue = master['revenue'].sum()
total_tax     = master['tax'].sum()
total_refunds = master['refunds'].sum()
total_charges = master['Charges'].sum()

print(f"  Net Sales:  £{total_net:,.2f}")
print(f"  Orders:     {total_orders:,}")
print(f"  Revenue:    £{total_revenue:,.2f}")
print(f"  Tax:        £{total_tax:,.2f}")
print(f"  Refunds:    £{total_refunds:,.2f}")
print(f"  Charges:    £{total_charges:,.2f}")
print()

# ── Load detail file (order-level) ────────────────────────────────────────────
detail_cols = None
detail = None
if os.path.exists(DETAIL_PATH):
    detail = pd.read_csv(DETAIL_PATH)
    detail.columns = [c.strip() for c in detail.columns]
    # Deduplicate on Order ID
    if 'Order ID' in detail.columns:
        detail = detail.drop_duplicates(subset=['Order ID'])
    # Parse datetime
    time_col = 'Order time' if 'Order time' in detail.columns else detail.columns[4]
    detail['_dt'] = pd.to_datetime(detail[time_col], errors='coerce')
    detail = detail.dropna(subset=['_dt'])
    detail = detail[(detail['_dt'] >= '2026-01-01') & (detail['_dt'] <= '2026-04-22 23:59:59')]
    print(f"Detail orders loaded: {len(detail):,} unique orders")

# ══════════════════════════════════════════════════════════════════
# 1. REBUILD sales_overview.csv (daily aggregates from master)
# ══════════════════════════════════════════════════════════════════
print("\n[1] Rebuilding sales_overview.csv...")
ov_rows = []
for _, row in master.sort_values('date').iterrows():
    ov_rows.append({
        'Order time':           row['date'].strftime('%Y-%m-%d'),
        'Net sales':            f"{row['net']:,.2f}",
        'Tax on net sales':     f"{row['tax']:,.2f}",
        'Tips':                 '0.00',
        'Charges':              f"{row['Charges']:,.2f}",
        'Refunds':              f"{row['refunds']:,.2f}",
        'Revenue':              f"{row['revenue']:,.2f}",
        'Revenue via Flipdish': f"{row['revenue']:,.2f}",
        'Orders':               int(row['orders']),
    })
# Add total row
ov_rows.append({
    'Order time':           'Total',
    'Net sales':            f"{total_net:,.2f}",
    'Tax on net sales':     f"{total_tax:,.2f}",
    'Tips':                 '0.00',
    'Charges':              f"{total_charges:,.2f}",
    'Refunds':              f"{total_refunds:,.2f}",
    'Revenue':              f"{total_revenue:,.2f}",
    'Revenue via Flipdish': f"{total_revenue:,.2f}",
    'Orders':               total_orders,
})
pd.DataFrame(ov_rows).to_csv(os.path.join(SUMMARY_DIR, 'sales_overview.csv'), index=False)
print(f"  Done: {len(ov_rows)-1} daily rows + 1 total row")

# ══════════════════════════════════════════════════════════════════
# 2. REBUILD revenue_summary.csv
# ══════════════════════════════════════════════════════════════════
print("\n[2] Rebuilding revenue_summary.csv...")
rev_df = pd.DataFrame([{
    'Net sales':            f"{total_net:,.2f}",
    'Tax on net sales':     f"{total_tax:,.2f}",
    'Tips':                 '0.00',
    'Charges':              f"{total_charges:,.2f}",
    'Revenue':              f"{total_revenue:,.2f}",
    'Refunds':              f"{-abs(total_refunds):,.2f}",
    'Revenue after refunds': f"{total_revenue - abs(total_refunds):,.2f}",
}])
rev_df.to_csv(os.path.join(SUMMARY_DIR, 'revenue_summary.csv'), index=False)
print(f"  Net Sales: £{total_net:,.2f}, Revenue: £{total_revenue:,.2f}")

# ══════════════════════════════════════════════════════════════════
# 3. REBUILD net_sales_per_day.csv (daily net sales)
# ══════════════════════════════════════════════════════════════════
print("\n[3] Rebuilding net_sales_per_day.csv...")
per_day_rows = []
for _, row in master.sort_values('date').iterrows():
    per_day_rows.append({
        'Order time': row['date'].strftime('%Y-%m-%d'),
        'Net sales':  f"{row['net']:,.2f}",
        'Orders':     int(row['orders']),
    })
pd.DataFrame(per_day_rows).to_csv(os.path.join(SUMMARY_DIR, 'net_sales_per_day.csv'), index=False)
print(f"  Done: {len(per_day_rows)} rows")

# ══════════════════════════════════════════════════════════════════
# 4. REBUILD net_sales_per_day_of_week.csv
# ══════════════════════════════════════════════════════════════════
print("\n[4] Rebuilding net_sales_per_day_of_week.csv...")
master['day_num'] = master['date'].dt.dayofweek  # 0=Mon
master['day_name'] = master['date'].dt.day_name()
dow = master.groupby(['day_num','day_name']).agg(
    net_sales=('net','sum'),
    avg_order_value=('net', lambda x: x.sum() / master.loc[x.index,'orders'].sum() if master.loc[x.index,'orders'].sum() > 0 else 0)
).reset_index().sort_values('day_num')
dow_out = pd.DataFrame({
    '': list(range(1, len(dow)+1)),
    'Day of week': dow['day_name'].values,
    'Net sales': [f"{v:,.2f}" for v in dow['net_sales'].values],
    'Avg order value': [f"{v:,.2f}" for v in dow['avg_order_value'].values],
})
dow_out.to_csv(os.path.join(SUMMARY_DIR, 'net_sales_per_day_of_week.csv'), index=False)
print(f"  Done: {len(dow_out)} days of week")

# ══════════════════════════════════════════════════════════════════
# 5. REBUILD charges_summary.csv & total_charges.csv
# ══════════════════════════════════════════════════════════════════
print("\n[5] Rebuilding charges_summary.csv & total_charges.csv...")
delivery_c   = 320.64  # User verified ground truth
additional_c = 16.00   # User verified ground truth
total_c      = delivery_c + additional_c

ch_df = pd.DataFrame([{
    'Delivery charges':   f"{delivery_c:,.2f}",
    'Service charges':    '0.00',
    'DRS charges':        '0.00',
    'Packaging charges':  '0.00',
    'Additional charges': f"{additional_c:,.2f}",
    'Total charges':      f"{total_c:,.2f}",
}])
ch_df.to_csv(os.path.join(SUMMARY_DIR, 'charges_summary.csv'), index=False)
# total_charges.csv
tc_df = pd.DataFrame([['This Period','This Period','Last Period','Last Period'],
                       ['Total charges','Percentage change','Total charges','Percentage change'],
                       [f"{total_c:,.2f}", '', '', '']])
tc_df.to_csv(os.path.join(SUMMARY_DIR, 'total_charges.csv'), index=False, header=False)
print(f"  Charges total: {total_c:,.2f}")

# ══════════════════════════════════════════════════════════════════
# 6. REBUILD dispatch, channel, payment, hourly from DETAIL
# ══════════════════════════════════════════════════════════════════
if detail is not None:
    net_col = 'Net sales' if 'Net sales' in detail.columns else detail.columns[11]
    detail['_net'] = detail[net_col].apply(clean_val)

    # 6a. Dispatch type
    print("\n[6a] Rebuilding net_sales_by_dispatch_type.csv...")
    if 'Dispatch type' in detail.columns:
        disp = detail.groupby('Dispatch type')['_net'].sum()
        dispatch_order = ['Collection','Delivery','Dine In','Take Away']
        disp_row = {'Dispatch type': '', **{d: f"{disp.get(d,0):,.2f}" for d in dispatch_order}}
        disp_header = {'Dispatch type': 'Dispatch type', **{d: 'Net sales' for d in dispatch_order}}
        pd.DataFrame([disp_header, disp_row]).to_csv(
            os.path.join(SUMMARY_DIR, 'net_sales_by_dispatch_type.csv'), index=False, header=False)
        for k,v in disp.items(): print(f"  {k}: £{v:,.2f}")

    # 6b. Sales channel
    print("\n[6b] Rebuilding net_sales_by_sales_channel.csv...")
    ch_col = 'Sales channel name' if 'Sales channel name' in detail.columns else None
    if ch_col:
        chan = detail.groupby(ch_col)['_net'].sum()
        ch_names = list(chan.index)
        ch_header = {c: c for c in ch_names}
        ch_row    = {c: f"{v:,.2f}" for c,v in chan.items()}
        pd.DataFrame([ch_header, {'':''}, ch_row]).to_csv(
            os.path.join(SUMMARY_DIR, 'net_sales_by_sales_channel.csv'), index=False, header=False)
        for k,v in chan.items(): print(f"  {k}: £{v:,.2f}")

    # 6c. Payment method
    print("\n[6c] Rebuilding net_sales_by_payment_method.csv...")
    pay_col = 'Payment type' if 'Payment type' in detail.columns else None
    if pay_col:
        pay = detail.groupby(pay_col)['_net'].sum()
        pd.DataFrame([pay.to_dict()]).to_csv(
            os.path.join(SUMMARY_DIR, 'net_sales_by_payment_method.csv'), index=False)
        for k,v in pay.items(): print(f"  {k}: £{v:,.2f}")

    # 6d. Hourly
    print("\n[6d] Rebuilding net_sales_by_hour_of_day.csv...")
    detail['_hour'] = detail['_dt'].dt.hour
    hourly = detail.groupby('_hour')['_net'].sum()
    hr_rows = []
    for h in range(24):
        label = f"{h:02d}:00 - {(h+1)%24:02d}:00"
        hr_rows.append({'Hour': label, 'Net sales': f"{hourly.get(h,0):,.2f}"})
    pd.DataFrame(hr_rows).to_csv(os.path.join(SUMMARY_DIR, 'net_sales_by_hour_of_day.csv'), index=False)
    print(f"  Peak hour: {hourly.idxmax():02d}:00 (£{hourly.max():,.2f})")

    # 6e. net_sales_by_property
    print("\n[6e] Rebuilding net_sales_by_property.csv...")
    prop_col = 'Property name' if 'Property name' in detail.columns else 'Restaurant name' if 'Restaurant name' in detail.columns else None
    if prop_col:
        prop = detail.groupby(prop_col)['_net'].sum()
    else:
        prop = pd.Series({'Chocoberry Cardiff': total_net})
    pd.DataFrame([prop.to_dict()]).to_csv(
        os.path.join(SUMMARY_DIR, 'net_sales_by_property.csv'), index=False)
    for k,v in prop.items(): print(f"  {k}: £{v:,.2f}")

    # 6f. revenue_after_refunds.csv
    print("\n[6f] Rebuilding revenue_after_refunds.csv...")
    raf_df = pd.DataFrame([{
        'Revenue':               f"{total_revenue:,.2f}",
        'Refunds':               f"{-abs(total_refunds):,.2f}",
        'Revenue after refunds': f"{total_revenue - abs(total_refunds):,.2f}",
    }])
    raf_df.to_csv(os.path.join(SUMMARY_DIR, 'revenue_after_refunds.csv'), index=False)
    print(f"  Revenue after refunds: £{total_revenue - abs(total_refunds):,.2f}")

print("\n" + "="*60)
print("ALL SUMMARY FILES REBUILT FROM SCRATCH")
print(f"  Date range: 2026-01-01 to 2026-04-22")
print(f"  Net Sales:  {total_net:,.2f}")
print(f"  Orders:     {total_orders:,}")
print(f"  Tax:        {total_tax:,.2f}")
print("="*60)
