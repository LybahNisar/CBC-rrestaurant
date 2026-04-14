import csv
import os

path = r'C:\Users\GEO\Desktop\CBC\bought_in_products_audit.csv'
with open(path, 'r', encoding='latin1') as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        if i == 1: # Header row
            print(f"HEADER: {row}")
        if 'Lotus Biscoff Milk Cake' in str(row):
            print(f"MATCH FOUND AT ROW {i}:")
            for j, cell in enumerate(row):
                print(f"  Col {j}: {repr(cell)}")
