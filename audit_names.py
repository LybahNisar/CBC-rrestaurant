import pandas as pd
s_df = pd.read_csv(r"C:\Users\GEO\Desktop\CBC\Menu Item Report data\Most sold items.csv")
r_df = pd.read_csv(r"C:\Users\GEO\Desktop\CBC\chocoberry recipe master\chocoberry_recipe_master.csv")
s_names = [str(x).strip().upper() for x in s_df.iloc[:, 1].unique()]
r_names = [str(x).strip().upper() for x in r_df['Recipe Name'].unique()]
missing = [n for n in s_names if n not in r_names]
print(f"TOTAL SALES ITEMS: {len(s_names)}")
print(f"MAPPED IN RECIPE: {len(s_names) - len(missing)}")
print(f"MISSING IN RECIPE: {len(missing)}")
print("\n--- EXAMPLES OF MISSING (Sales naming differs from Recipe) ---")
for m in sorted(missing)[:20]:
    print(f"  [!] {m}")
