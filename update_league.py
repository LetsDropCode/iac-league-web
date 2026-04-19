import pandas as pd
import os
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter


# ---------------------------
# Load category map
# ---------------------------
category_map = pd.read_csv("category_map.csv")

# ---------------------------
# Load points rules
# ---------------------------
rules = pd.read_csv("points_rules.csv")

rules["TimeFrom"] = pd.to_timedelta(rules["TimeFrom"])
rules["TimeTo"] = pd.to_timedelta(rules["TimeTo"])
rules["Distance"] = pd.to_numeric(rules["Distance"], errors="coerce")
rules["Distance"] = rules["Distance"].round().astype("Int64")

# ---------------------------
# Load all race files
# ---------------------------
results_folder = "results"
all_results = []

for file in os.listdir(results_folder):
    if file.endswith(".csv"):
        df = pd.read_csv(os.path.join(results_folder, file), sep=";")

        # Add race name
        race_name = file.replace(".csv", "")
        df["Race"] = race_name

        all_results.append(df)

# Combine all races
results = pd.concat(all_results, ignore_index=True)

# ---------------------------
# Convert Time column
# ---------------------------
# Auto-detect finish/time column
time_column = [col for col in results.columns if "time" in col.lower() or "finish" in col.lower()][0]
results["Time"] = pd.to_timedelta(results[time_column])

# ---------------------------
# Clean distance
# ---------------------------
results["Distance"] = (
    results["Distance"]
    .astype(str)
    .str.replace("km", "", regex=False)
)

results["Distance"] = pd.to_numeric(results["Distance"], errors="coerce")

# ---------------------------
# Map categories
# ---------------------------
results = results.merge(
    category_map,
    left_on="Category",
    right_on="FinishtimeCategory",
    how="left"
)

# ---------------------------
# Assign points
# ---------------------------
def assign_points(row):

    try:
        applicable = rules[
            (rules["Distance"] == row["Distance"]) &
            (rules["Gender"] == row["Gender"]) &
            (rules["Category"] == row["PointsCategory"]) &
            (row["Time"] >= rules["TimeFrom"]) &
            (
                (row["Time"] <= rules["TimeTo"]) |
                (rules["TimeTo"].isna())   # 🔥 handles Finisher
            )
        ]

        if not applicable.empty:
            return int(applicable.iloc[0]["Points"])

    except Exception as e:
        print("⚠️ Error:", e)

    # 🔍 DEBUG (temporary but VERY useful)
    print(
        "❌ No match:",
        row.get("Distance"),
        row.get("Gender"),
        row.get("PointsCategory"),
        row.get("Time")
    )

    return 1  # fallback

results["Points"] = results.apply(assign_points, axis=1)

# ---------------------------
# Build wide league table
# ---------------------------

# Stable athlete ID
results["AthleteID"] = (
    results["Name"].str.strip().str.lower() + "_" +
    results["Gender"].str.strip().str.lower() + "_" +
    results["PointsCategory"].str.strip().str.lower()
)

# ---------------------------
# Create race label
# ---------------------------
results["RaceLabel"] = (
    results["Race"]
    .str.replace("2026_", "", regex=False)
    .str.replace("_", " ", regex=False)
    + " " + results["Distance"].astype(str) + "km"
)

# ---------------------------
# Pivot into wide league table
# ---------------------------

race_table = (
    results
    .pivot_table(
        index=["AthleteID", "Name", "Gender", "PointsCategory"],
        columns="RaceLabel",
        values="Points",
        aggfunc="sum",
        fill_value=0
    )
    .reset_index()
)

# Confirm PointsCategory exists after pivot
if "PointsCategory" not in race_table.columns:
    raise ValueError("PointsCategory missing from race_table after pivot.")

# Identify race columns (only numeric race columns)
race_cols = [
    col for col in race_table.columns
    if col not in ["AthleteID", "Name", "Gender", "PointsCategory"]
]

# ---------------------------
# Calculate totals
# ---------------------------
race_table["TotalPoints"] = race_table[race_cols].sum(axis=1)

race_table["LeagueRaces"] = (
    race_table[race_cols] > 0
).sum(axis=1)

race_table["Rank"] = (
    race_table
    .groupby("Gender")["TotalPoints"]
    .rank(method="dense", ascending=False)
    .astype(int)
)
# Sort
race_table = race_table.sort_values(
    ["Gender", "Rank"],
    ascending=[True, True]
)

# ---------------------------
# Reorder columns
# ---------------------------
final_cols = ["Rank", "Name", "Gender", "PointsCategory", "LeagueRaces", "TotalPoints"] + race_cols
race_table = race_table[final_cols]

# ---------------------------
# Create Excel Multi-Sheet Output (Formatted)
# ---------------------------

with pd.ExcelWriter("league_tables.xlsx", engine="openpyxl") as writer:

    def format_sheet(ws):
        # Freeze header row
        ws.freeze_panes = "A2"

        # Bold headers
        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Auto column width
        for column_cells in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column_cells[0].column)

            for cell in column_cells:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass

            adjusted_width = max_length + 2
            ws.column_dimensions[column_letter].width = adjusted_width

        # Center Rank and LeagueRaces columns
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if ws.cell(row=1, column=cell.column).value in ["Rank", "LeagueRaces"]:
                    cell.alignment = Alignment(horizontal="center")

    # ---------------------------
    # Overall Sheet
    # ---------------------------
    race_table.to_excel(writer, sheet_name="Overall_Gender", index=False)
    format_sheet(writer.sheets["Overall_Gender"])

    # ---------------------------
    # Gender Sheets
    # ---------------------------
    for gender in race_table["Gender"].unique():
        gender_table = race_table[race_table["Gender"] == gender]
        sheet_name = gender[:30]
        gender_table.to_excel(writer, sheet_name=sheet_name, index=False)
        format_sheet(writer.sheets[sheet_name])

    # ---------------------------
    # Gender + Category Sheets
    # ---------------------------
    for gender in race_table["Gender"].unique():
        for category in race_table["PointsCategory"].unique():

            subset = race_table[
                (race_table["Gender"] == gender) &
                (race_table["PointsCategory"] == category)
            ]

            if not subset.empty:
                subset = subset.copy()

                subset["Rank"] = (
                    subset["TotalPoints"]
                    .rank(method="dense", ascending=False)
                    .astype(int)
                )

                sheet_name = f"{gender}_{category}"[:30]
                subset.to_excel(writer, sheet_name=sheet_name, index=False)
                format_sheet(writer.sheets[sheet_name])

print("League tables Excel file created successfully with formatting!")

# ---------------------------
# Generate Public HTML Leaderboard
# ---------------------------

import os

output_folder = "league_site"
os.makedirs(output_folder, exist_ok=True)

def df_to_html_table(df, table_id):
    return df.to_html(
        index=False,
        table_id=table_id,
        classes="display nowrap",
        border=0
    )

# Load main sheets into memory
sheets = {}

for gender in race_table["Gender"].unique():
    sheets[gender] = race_table[race_table["Gender"] == gender]

sheets["Overall"] = race_table

# Create HTML content
html_content = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Irene AC League Standings</title>

<link rel="stylesheet" 
href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>

<style>
body {
    font-family: Arial, sans-serif;
    margin: 20px;
}
h1 {
    color: #0047AB;
}
.tab {
    margin-right: 15px;
    cursor: pointer;
    font-weight: bold;
    display: inline-block;
}
.tab:hover {
    text-decoration: underline;
}
.tab-content {
    display: none;
}
.active {
    display: block;
}
</style>
</head>
<body>

<h1>Irene AC League Standings</h1>

<div id="tabs">
"""

# Add tabs
for name in sheets.keys():
    html_content += f'<span class="tab" onclick="showTab(\'{name}\')">{name}</span>'

html_content += "</div>"

# Add tables
for name, df in sheets.items():
    html_content += f'<div id="{name}" class="tab-content">'
    html_content += df_to_html_table(df, f"table_{name}")
    html_content += "</div>"

# Add JS
html_content += """
<script>
function showTab(name) {
    $('.tab-content').removeClass('active');
    $('#' + name).addClass('active');
}

$(document).ready(function() {
"""

for name in sheets.keys():
    html_content += f"$('#table_{name}').DataTable({{scrollX:true}});\n"

html_content += """
    showTab('Overall');
});
</script>

</body>
</html>
"""

# Write file
with open(os.path.join(output_folder, "index.html"), "w", encoding="utf-8") as f:
    f.write(html_content)

print("Public leaderboard website generated successfully!")