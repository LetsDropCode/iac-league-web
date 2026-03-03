import pandas as pd
import os

def process_league():

    os.makedirs("results", exist_ok=True)

    # =========================
    # LOAD RULES
    # =========================
    category_map = pd.read_csv("category_map.csv")
    rules = pd.read_csv("points_rules.csv")

    rules["TimeFrom"] = pd.to_timedelta(rules["TimeFrom"])
    rules["TimeTo"] = pd.to_timedelta(rules["TimeTo"])

    # =========================
    # LOAD RESULTS FILES
    # =========================
    results_folder = "results"
    all_results = []

    for file in os.listdir(results_folder):
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(results_folder, file), sep=";")
            df["Race"] = file.replace(".csv", "")
            all_results.append(df)

    # If no results yet
    if not all_results:
        return pd.DataFrame(columns=[
            "Name", "Gender", "Rank",
            "Races Completed", "Total Points"
        ])

    results = pd.concat(all_results, ignore_index=True)

    # =========================
    # TIME CONVERSION
    # =========================
    time_column = [
        col for col in results.columns
        if "time" in col.lower() or "finish" in col.lower()
    ][0]

    results["Time"] = pd.to_timedelta(results[time_column])

    # =========================
    # CLEAN DISTANCE
    # =========================
    results["Distance"] = (
        results["Distance"]
        .astype(str)
        .str.replace("km", "", regex=False)
    )

    results["Distance"] = pd.to_numeric(results["Distance"], errors="coerce")

    # =========================
    # MAP CATEGORY
    # =========================
    results = results.merge(
        category_map,
        left_on="Category",
        right_on="FinishtimeCategory",
        how="left"
    )

    # =========================
    # ASSIGN POINTS
    # =========================
    def assign_points(row):
        applicable = rules[
            (rules["Distance"] == row["Distance"]) &
            (rules["Gender"] == row["Gender"]) &
            (rules["Category"] == row["PointsCategory"]) &
            (row["Time"] >= rules["TimeFrom"]) &
            (row["Time"] <= rules["TimeTo"])
        ]

        if not applicable.empty:
            return applicable.iloc[0]["Points"]

        return 0

    results["Points"] = results.apply(assign_points, axis=1)

    # =========================
    # BUILD ATHLETE ID
    # =========================
    results["AthleteID"] = (
        results["Name"].str.strip().str.lower() + "_" +
        results["Gender"].str.strip().str.lower() + "_" +
        results["PointsCategory"].str.strip().str.lower()
    )

    results["RaceLabel"] = results["Race"] + " " + results["Distance"].astype(str) + "km"

    # =========================
    # PIVOT TABLE
    # =========================
    race_table = (
        results.pivot_table(
            index=["AthleteID", "Name", "Gender", "PointsCategory"],
            columns="RaceLabel",
            values="Points",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # =========================
    # REMOVE INTERNAL COLUMNS
    # =========================
    race_table = race_table.drop(
        columns=["AthleteID", "PointsCategory"],
        errors="ignore"
    )

    # =========================
    # CALCULATE TOTALS
    # =========================
    race_cols = [
        col for col in race_table.columns
        if col not in ["Name", "Gender"]
    ]

    race_table["Total Points"] = race_table[race_cols].sum(axis=1)
    race_table["Races Completed"] = (race_table[race_cols] > 0).sum(axis=1)

    # =========================
    # RANK PER GENDER
    # =========================
    race_table["Rank"] = (
        race_table.groupby("Gender")["Total Points"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    race_table = race_table.sort_values(["Gender", "Rank"])

    # =========================
    # ADD MEDALS
    # =========================
    def medal(rank):
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        return ""

    race_table["Rank"] = race_table["Rank"].apply(
        lambda r: f"{medal(r)} {r}" if r <= 3 else r
    )
    race_table["Rank"] = race_table["Rank"].apply(
        lambda r: f"{medal(r)} {r}" if r <= 3 else r
    )

    # =========================
    # FINAL COLUMN ORDER (STRICT)
    # =========================

    base_cols = ["Name", "Gender", "Rank", "Races Completed", "Total Points"]

    race_cols = [
        col for col in race_table.columns
        if col not in base_cols
    ]

    # Remove anything unexpected
    race_cols = [col for col in race_cols if col != "RaceLabel"]

    race_table = race_table[base_cols + race_cols]

    return race_table