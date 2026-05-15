import pandas as pd

input_file = "enrichi.xlsx"
output_file = "output_split.xlsx"

# Read Excel (keep values as text)
df = pd.read_excel(input_file, dtype=str)

rows = len(df)
parts = 5
rows_per_part = rows // parts + 1

writer = pd.ExcelWriter(output_file, engine="openpyxl")

for i in range(parts):
    start = i * rows_per_part
    end = start + rows_per_part
    chunk = df.iloc[start:end]

    if not chunk.empty:
        chunk.to_excel(writer, sheet_name=f"Page_{i+1}", index=False)

writer.close()

print("Split completed.")
