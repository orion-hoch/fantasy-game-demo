import pandas as pd
import glob
import os

folder = input("Enter folder path: ").strip()
output = os.path.join(folder, "combined.xlsx")

files = [
    f for f in
    glob.glob(os.path.join(folder, "*.xlsx")) + glob.glob(os.path.join(folder, "*.xls"))
    if os.path.abspath(f) != os.path.abspath(output)
]
if not files:
    print("No xlsx/xls files found.")
    exit()

dfs = []
for f in files:
    try:
        engine = "xlrd" if f.endswith(".xls") else "openpyxl"
        df = pd.read_excel(f, engine=engine)
    except Exception:
        # Sports Reference exports .xls files that are actually HTML tables
        df = pd.read_html(f)[0]

    # Flatten MultiIndex columns (Sports Reference HTML tables have multi-level headers)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(str(c) for c in col).strip() for col in df.columns]

    dfs.append(df)
    print(f"Loaded {os.path.basename(f)} — {len(df)} rows")

combined = pd.concat(dfs, ignore_index=True)

print(f"\nColumns: {list(combined.columns)}")

sort_col = "Fantasy PPR"
if sort_col in combined.columns:
    combined = combined.sort_values(sort_col, ascending=False, na_position="last").reset_index(drop=True)
else:
    print(f"Warning: '{sort_col}' column not found, skipping sort.")

combined.to_excel(output, index=False)
print(f"\nSaved {len(combined)} rows to {output}")
