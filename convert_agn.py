import pandas as pd
import os

# -------------------------------
# FIND EXCEL FILE
# -------------------------------
excel_files = [f for f in os.listdir() if f.endswith(".xlsx")]

if not excel_files:
    print("❌ No Excel file found.")
    exit()

file_path = excel_files[0]
print(f"📂 Loading: {file_path}")

# -------------------------------
# LOAD FILE SAFELY
# -------------------------------
try:
    rules = pd.read_excel(file_path, header=1)
except Exception as e:
    print("❌ Failed to read Excel:", e)
    exit()

# -------------------------------
# CLEAN HEADERS
# -------------------------------
rules.columns = rules.columns.astype(str).str.strip()

# Fix common typo
if "Catergory" in rules.columns:
    rules = rules.rename(columns={"Catergory": "Category"})

# -------------------------------
# REQUIRED COLUMNS CHECK
# -------------------------------
required = ["Distance", "Gender", "Category", "TimeFrom", "TimeTo", "Points"]

missing = [col for col in required if col not in rules.columns]

if missing:
    print(f"❌ Missing columns: {missing}")
    exit()

# -------------------------------
# CLEAN DISTANCE
# -------------------------------
rules["Distance"] = (
    rules["Distance"]
    .astype(str)
    .str.replace("km", "", regex=False)
)

rules["Distance"] = pd.to_numeric(rules["Distance"], errors="coerce")

# -------------------------------
# CLEAN TEXT
# -------------------------------
rules["Gender"] = rules["Gender"].astype(str).str.strip()
rules["Category"] = rules["Category"].astype(str).str.strip()

# -------------------------------
# SAFE TIME EXTRACTION
# -------------------------------
def extract_time(value):
    try:
        if pd.isna(value):
            return None

        value_str = str(value).strip().lower()

        if value_str == "finisher":
            return pd.Timedelta.max   # ✅ KEY FIX

        if hasattr(value, "time"):
            return pd.to_timedelta(value.time().strftime("%H:%M:%S"))

        return pd.to_timedelta(value)

    except:
        return None
        
rules["TimeFrom"] = rules["TimeFrom"].apply(extract_time)
rules["TimeTo"] = rules["TimeTo"].apply(extract_time)

# -------------------------------
# CLEAN POINTS
# -------------------------------
rules["Points"] = pd.to_numeric(rules["Points"], errors="coerce")

# -------------------------------
# DROP BAD ROWS
# -------------------------------
before = len(rules)

rules = rules.dropna(subset=["Distance", "Gender", "Category", "TimeFrom", "Points"])

after = len(rules)

print(f"🧹 Cleaned {before - after} invalid rows")

# -------------------------------
# SAVE
# -------------------------------
rules.to_csv("points_rules.csv", index=False)

print("✅ Rules successfully converted!")