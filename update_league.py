import pandas as pd
import os
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

# -----------------------------------
# IMPORT ENGINE (SINGLE SOURCE OF TRUTH)
# -----------------------------------
from update_engine import process_league

# -----------------------------------
# RUN ENGINE
# -----------------------------------
run_table, walk_table = process_league()

# Combine for overall (optional: keeps your current structure)
race_table = run_table.copy()

# -----------------------------------
# CREATE EXCEL OUTPUT
# -----------------------------------
with pd.ExcelWriter("league_tables.xlsx", engine="openpyxl") as writer:

    def format_sheet(ws):
        ws.freeze_panes = "A2"

        # Bold headers
        for cell in ws[1]:
            cell.font = Font(bold=True)

        # Auto width
        for column_cells in ws.columns:
            max_length = 0
            col_letter = get_column_letter(column_cells[0].column)

            for cell in column_cells:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass

            ws.column_dimensions[col_letter].width = max_length + 2

        # Center some cols
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if ws.cell(row=1, column=cell.column).value in ["Rank", "Races Completed"]:
                    cell.alignment = Alignment(horizontal="center")

    # ---------------------------
    # RUNNERS
    # ---------------------------
    race_table.to_excel(writer, sheet_name="Runners", index=False)
    format_sheet(writer.sheets["Runners"])

    # ---------------------------
    # WALKERS
    # ---------------------------
    if not walk_table.empty:
        walk_table.to_excel(writer, sheet_name="Walkers", index=False)
        format_sheet(writer.sheets["Walkers"])

    # ---------------------------
    # GENDER SPLIT (RUNNERS)
    # ---------------------------
    for gender in race_table["Gender"].unique():
        subset = race_table[race_table["Gender"] == gender]
        sheet_name = f"Run_{gender}"[:30]
        subset.to_excel(writer, sheet_name=sheet_name, index=False)
        format_sheet(writer.sheets[sheet_name])

    # ---------------------------
    # GENDER SPLIT (WALKERS)
    # ---------------------------
    if not walk_table.empty:
        for gender in walk_table["Gender"].unique():
            subset = walk_table[walk_table["Gender"] == gender]
            sheet_name = f"Walk_{gender}"[:30]
            subset.to_excel(writer, sheet_name=sheet_name, index=False)
            format_sheet(writer.sheets[sheet_name])

print("✅ Excel generated")

# -----------------------------------
# GENERATE HTML SITE
# -----------------------------------

output_folder = "league_site"
os.makedirs(output_folder, exist_ok=True)

def df_to_html(df, table_id):
    return df.to_html(
        index=False,
        table_id=table_id,
        classes="display nowrap",
        border=0
    )

sheets = {
    "Runners": race_table
}

if not walk_table.empty:
    sheets["Walkers"] = walk_table

html = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Irene AC League</title>

<link rel="stylesheet"
href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css"/>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>

<style>
body { font-family: Arial; margin:20px; }
h1 { color:#0047AB; }
.tab { margin-right:15px; cursor:pointer; font-weight:bold; display:inline-block; }
.tab-content { display:none; }
.active { display:block; }
</style>
</head>
<body>

<h1>Irene AC League Standings</h1>
<div id="tabs">
"""

# Tabs
for name in sheets.keys():
    html += f"<span class='tab' onclick=\"showTab('{name}')\">{name}</span>"

html += "</div>"

# Tables
for name, df in sheets.items():
    html += f"<div id='{name}' class='tab-content'>"
    html += df_to_html(df, f"table_{name}")
    html += "</div>"

# JS
html += """
<script>
function showTab(name){
    $('.tab-content').removeClass('active');
    $('#' + name).addClass('active');
}

$(document).ready(function(){
"""

for name in sheets.keys():
    html += f"$('#table_{name}').DataTable({{scrollX:true}});\n"

html += """
    showTab('Runners');
});
</script>

</body>
</html>
"""

with open(os.path.join(output_folder, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("✅ HTML site generated")