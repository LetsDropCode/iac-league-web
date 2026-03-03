import pandas as pd
import os

# -------------------------------
# Auto-detect Excel file
# -------------------------------
excel_files = [f for f in os.listdir() if f.endswith(".xlsx")]

if not excel_files:
    raise FileNotFoundError("❌ No Excel (.xlsx) file found in project folder.")

file_path = excel_files[0]

print(f"📂 Loading AGN file: {file_path}")

# -------------------------------
# Load using correct header row
# -------------------------------
rules = pd.read_excel(file_path, header=1)

# Clean headers
rules.columns = rules.columns.str.strip()

# Fix spelling
if "Catergory" in rules.columns:
    rules = rules.rename(columns={"Catergory": "Category"})

# -------------------------------
# Clean Distance
# -------------------------------
rules["Distance"] = (
    rules["Distance"]
    .astype(str)
    .str.replace("km", "", regex=False)
)

rules["Distance"] = pd.to_numeric(rules["Distance"], errors="coerce")

# -------------------------------
# Clean text columns
# -------------------------------
rules["Gender"] = rules["Gender"].astype(str).str.strip()
rules["Category"] = rules["Category"].astype(str).str.strip()

# -------------------------------
# Fix Excel 1900 date issue
# -------------------------------
def extract_time_only(value):
    if pd.isna(value):
        return None
    return pd.to_timedelta(value.time().strftime("%H:%M:%S"))

rules["TimeFrom"] = rules["TimeFrom"].apply(extract_time_only)
rules["TimeTo"] = rules["TimeTo"].apply(extract_time_only)

rules["Points"] = pd.to_numeric(rules["Points"], errors="coerce")

# -------------------------------
# Drop incomplete rows
# -------------------------------
rules = rules.dropna(subset=["Distance", "Gender", "Category", "TimeFrom", "TimeTo", "Points"])

# -------------------------------
# Save cleaned rules
# -------------------------------
rules.to_csv("points_rules.csv", index=False)

print("✅ AGN rules cleaned and saved successfully!")