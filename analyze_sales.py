"""
Chocoberry Cardiff - Full Sales Data Analysis
Columns (0-indexed, 25 total):
  0  = row id
  1  = Property name
  2  = Order ID
  3  = Sale number
  4  = Order time
  5  = Source
  6  = Dispatch type
  7  = Sales channel name
  8  = Sales channel type
  9  = Payment method
  10 = Is preorder
  11 = Refund status
  12 = Net sales
  13 = Tax on net sales
  14 = Tips
  15 = Delivery charges
  16 = Service charges
  17 = DRS charges
  18 = Packaging charges
  19 = Additional charges
  20 = Charges
  21 = Revenue
  22 = Refunds
  23 = Revenue after refunds
  24 = Discounts
"""

from collections import defaultdict

file_path = r'C:\Users\GEO\Desktop\CBC\sales_data_dump.txt'

revenue_by_source       = defaultdict(float)
orders_by_source        = defaultdict(int)
revenue_by_dispatch     = defaultdict(float)
orders_by_dispatch      = defaultdict(int)
payment_counts          = defaultdict(int)
daily_revenue           = defaultdict(float)
daily_orders            = defaultdict(int)
weekly_revenue          = defaultdict(float)
refunds_by_source       = defaultdict(float)
net_by_source           = defaultdict(float)
discount_count          = 0
refund_count            = 0
refund_total            = 0.0
total_rows              = 0
skipped                 = 0
zero_value_rows         = 0

with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        if i == 0:   # skip header
            continue
        parts = line.split(',')
        if len(parts) < 25:
            skipped += 1
            continue
        total_rows += 1
        try:
            source        = parts[5].strip()
            dispatch      = parts[6].strip()
            payment       = parts[9].strip()
            order_time    = parts[4].strip()
            net_sales     = float(parts[12]) if parts[12].strip() else 0.0
            revenue       = float(parts[21]) if parts[21].strip() else 0.0
            rev_after_ref = float(parts[23]) if parts[23].strip() else 0.0
            discounts     = float(parts[24]) if parts[24].strip() else 0.0

            date_str = order_time[:10]  # YYYY-MM-DD
            year, month, day = date_str.split('-')
            # ISO week
            from datetime import date as dt
            d = dt(int(year), int(month), int(day))
            week_key = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"

            revenue_by_source[source]   += revenue
            orders_by_source[source]    += 1
            revenue_by_dispatch[dispatch] += revenue
            orders_by_dispatch[dispatch]  += 1
            payment_counts[payment]     += 1
            daily_revenue[date_str]     += revenue
            daily_orders[date_str]      += 1
            weekly_revenue[week_key]    += revenue
            net_by_source[source]       += net_sales

            if discounts < 0:
                discount_count += 1

            if parts[11].strip():  # Refund status not empty
                refund_count    += 1
                refund_total    += float(parts[22]) if parts[22].strip() else 0.0

            if revenue == 0.0:
                zero_value_rows += 1

        except Exception:
            skipped += 1

# ── Output ──────────────────────────────────────────────────
grand_revenue  = sum(revenue_by_source.values())
grand_orders   = sum(orders_by_source.values())
avg_order_val  = grand_revenue / grand_orders if grand_orders else 0

sep = '-' * 60

print('=' * 60)
print('  CHOCOBERRY CARDIFF — COMPLETE SALES DATA ANALYSIS')
print('=' * 60)
print(f'  Total data rows      : {total_rows:,}')
print(f'  Skipped / bad lines  : {skipped}')
print(f'  Zero-value orders    : {zero_value_rows}  (unpaid / comped)')
print(f'  Orders with discounts: {discount_count}')
print(f'  Orders with refunds  : {refund_count}')
print(f'  Total refund amount  : £{refund_total:,.2f}')
print()

print(sep)
print('  REVENUE BY ORDER SOURCE')
print(sep)
print(f"  {'Source':<18} {'Revenue':>10}  {'Orders':>6}  {'Avg £':>7}  {'Share':>6}")
print(f"  {'-'*18} {'-'*10}  {'-'*6}  {'-'*7}  {'-'*6}")
for src, rev in sorted(revenue_by_source.items(), key=lambda x: -x[1]):
    n   = orders_by_source[src]
    avg = rev / n if n else 0
    pct = rev / grand_revenue * 100 if grand_revenue else 0
    print(f"  {src:<18} £{rev:>9,.2f}  {n:>6}  £{avg:>6.2f}  {pct:>5.1f}%")
print(f"  {'TOTAL':<18} £{grand_revenue:>9,.2f}  {grand_orders:>6}  £{avg_order_val:>6.2f}  100.0%")
print()

print(sep)
print('  REVENUE BY DISPATCH TYPE')
print(sep)
print(f"  {'Type':<15} {'Revenue':>10}  {'Orders':>6}  {'Avg £':>7}  {'Share':>6}")
print(f"  {'-'*15} {'-'*10}  {'-'*6}  {'-'*7}  {'-'*6}")
for dt_type, rev in sorted(revenue_by_dispatch.items(), key=lambda x: -x[1]):
    n   = orders_by_dispatch[dt_type]
    avg = rev / n if n else 0
    pct = rev / grand_revenue * 100 if grand_revenue else 0
    print(f"  {dt_type:<15} £{rev:>9,.2f}  {n:>6}  £{avg:>6.2f}  {pct:>5.1f}%")
print()

print(sep)
print('  PAYMENT METHODS')
print(sep)
for pm, cnt in sorted(payment_counts.items(), key=lambda x: -x[1]):
    pct = cnt / grand_orders * 100 if grand_orders else 0
    print(f"  {pm:<22} {cnt:>5}  ({pct:.1f}%)")
print()

print(sep)
print('  TOP 20 REVENUE DAYS')
print(sep)
for d, rev in sorted(daily_revenue.items(), key=lambda x: -x[1])[:20]:
    n = daily_orders[d]
    print(f"  {d}   £{rev:>8,.2f}   ({n} orders)")
print()

print(sep)
print('  WEEKLY REVENUE SUMMARY')
print(sep)
for wk, rev in sorted(weekly_revenue.items()):
    print(f"  {wk}   £{rev:>8,.2f}")
print()

print(sep)
print('  DATE RANGE')
print(sep)
dates = sorted(daily_revenue.keys())
print(f"  Earliest : {dates[0]}")
print(f"  Latest   : {dates[-1]}")
print(f"  Unique days traded: {len(dates)}")
print()

print('=' * 60)
print(f'  GRAND TOTAL REVENUE       : £{grand_revenue:,.2f}')
print(f'  TOTAL ORDERS              : {grand_orders:,}')
print(f'  OVERALL AVG ORDER VALUE   : £{avg_order_val:.2f}')
print('=' * 60)
