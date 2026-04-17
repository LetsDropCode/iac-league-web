import pandas as pd
import os


# -----------------------------------
# MAIN ENTRY POINT
# -----------------------------------

def process_league():

    os.makedirs("results", exist_ok=True)

    # ---------------------------
    # LOAD CATEGORY MAP
    # ---------------------------
    category_map = pd.read_csv("category_map.csv")

    # ---------------------------
    # LOAD RULES
    # ---------------------------
    rules_run = pd.read_csv("points_rules.csv")
    rules_walk = pd.read_csv("points_rules_walk.csv")

    for rules in [rules_run, rules_walk]:
        rules["TimeFrom"] = pd.to_timedelta(rules["TimeFrom"])
        rules["TimeTo"] = pd.to_timedelta(rules["TimeTo"])

    # ---------------------------
    # LOAD RESULTS FILES
    # ---------------------------
    results_folder = "results"
    all_results = []

    for file in os.listdir(results_folder):
        if file.endswith(".csv"):

            df = pd.read_csv(os.path.join(results_folder, file), sep=";")

            df["Race"] = file.replace(".csv", "")

            # 🧠 Detect discipline
            if "walk" in file.lower():
                df["Discipline"] = "Walk"
            else:
                df["Discipline"] = "Run"

            all_results.append(df)

    if not all_results:
        empty = pd.DataFrame(columns=["Name", "Gender", "Rank", "Races Completed", "Total Points"])
        return empty, empty

    results = pd.concat(all_results, ignore_index=True)

    # ---------------------------
    # CLEAN TIME
    # ---------------------------
    time_column = [
        col for col in results.columns
        if "time" in col.lower() or "finish" in col.lower()
    ][0]

    results["Time"] = pd.to_timedelta(results[time_column], errors="coerce")

    # ---------------------------
    # CLEAN DISTANCE
    # ---------------------------
    results["Distance"] = (
        results["Distance"]
        .astype(str)
        .str.replace("km", "", regex=False)
    )

    results["Distance"] = pd.to_numeric(results["Distance"], errors="coerce")
    results["Distance"] = results["Distance"].round().astype("Int64")

    # ---------------------------
    # MAP CATEGORY
    # ---------------------------
    results = results.merge(
        category_map,
        left_on="Category",
        right_on="FinishtimeCategory",
        how="left"
    )

    # ---------------------------
    # BUILD TABLES
    # ---------------------------
    run_results = results[results["Discipline"] == "Run"]
    walk_results = results[results["Discipline"] == "Walk"]

    run_table = build_league(run_results, rules_run)
    walk_table = build_league(walk_results, rules_walk)

    return run_table, walk_table


# -----------------------------------
# CORE ENGINE (REUSABLE)
# -----------------------------------

def build_league(results, rules):

    if results.empty:
        return pd.DataFrame(columns=["Name", "Gender", "Rank", "Races Completed", "Total Points"])

    # ---------------------------
    # ASSIGN POINTS
    # ---------------------------
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

        # 🔥 NEW RULE: 1 point for finishers
        if pd.notnull(row["Time"]):
            return 1

        return 0

    results["Points"] = results.apply(assign_points, axis=1)

    # ---------------------------
    # ATHLETE ID
    # ---------------------------
    results["AthleteID"] = (
        results["Name"].str.strip().str.lower() + "_" +
        results["Gender"].str.strip().str.lower() + "_" +
        results["PointsCategory"].str.strip().str.lower()
    )

    # ---------------------------
    # CLEAN RACE NAME
    # ---------------------------
    results["RaceName"] = (
        results["Race"]
        .str.replace("10K_", "", regex=False)
        .str.replace("21K_", "", regex=False)
        .str.replace("32K_", "", regex=False)
        .str.replace("_", " ", regex=False)
    )

    results["RaceLabel"] = results["RaceName"] + " " + results["Distance"].astype(str) + "km"

    # ---------------------------
    # PIVOT
    # ---------------------------
    race_table = (
        results.pivot_table(
            index=["Name", "Gender"],
            columns="RaceLabel",
            values="Points",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    # ---------------------------
    # CALCULATE TOTALS
    # ---------------------------
    race_cols = [c for c in race_table.columns if "km" in c]

    race_table["Total Points"] = race_table[race_cols].sum(axis=1)
    race_table["Races Completed"] = (race_table[race_cols] > 0).sum(axis=1)

    # ---------------------------
    # RANK BY GENDER
    # ---------------------------
    race_table["Rank"] = (
        race_table.groupby("Gender")["Total Points"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    race_table = race_table.sort_values(["Gender", "Rank"])

    # ---------------------------
    # MEDALS
    # ---------------------------
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

    # ---------------------------
    # ORDER RACES (GM REQUIREMENT)
    # ---------------------------
    race_priority = ["Intercare", "Ace", "Bobbies 3-in-1"]

    def race_sort(col):
        race, dist = col.rsplit(" ", 1)
        dist = int(dist.replace("km", ""))
        race_index = race_priority.index(race) if race in race_priority else 999
        return (race_index, dist)

    race_cols = sorted(race_cols, key=race_sort)

    # ---------------------------
    # FINAL ORDER
    # ---------------------------
    base_cols = ["Name", "Gender", "Rank", "Races Completed", "Total Points"]

    race_table = race_table[base_cols + race_cols]

    return race_table