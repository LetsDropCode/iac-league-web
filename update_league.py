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

