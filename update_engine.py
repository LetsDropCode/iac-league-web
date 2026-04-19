import pandas as pd
import os


# -----------------------------------
# MAIN ENTRY
# -----------------------------------

def process_league():

    os.makedirs("results", exist_ok=True)

    try:
        category_map = pd.read_csv("category_map.csv")
    except:
        category_map = pd.DataFrame(columns=["FinishtimeCategory", "PointsCategory"])

    try:
        rules_run = pd.read_csv("points_rules.csv")
    except:
        rules_run = pd.DataFrame()

    try:
        rules_walk = pd.read_csv("points_rules_walk.csv")
    except:
        rules_walk = pd.DataFrame()

    # 🔧 FIX DISTANCE FORMAT (VERY IMPORTANT)
    for rules in [rules_run, rules_walk]:
        if not rules.empty:
            rules["Distance"] = pd.to_numeric(rules["Distance"], errors="coerce")
            rules["Distance"] = rules["Distance"].round().astype("Int64")

    # Convert rule times safely
    for rules in [rules_run, rules_walk]:
        if not rules.empty:
            rules["TimeFrom"] = pd.to_timedelta(rules.get("TimeFrom"), errors="coerce")
            rules["TimeTo"] = pd.to_timedelta(rules.get("TimeTo"), errors="coerce")

    # -----------------------------------
    # LOAD FILES
    # -----------------------------------

    results_folder = "results"
    all_results = []

    for file in os.listdir(results_folder):
        if file.endswith(".csv"):

            try:
                df = pd.read_csv(os.path.join(results_folder, file), sep=";")
            except:
                continue  # skip broken files

            df["Race"] = file.replace(".csv", "")

            # Detect discipline
            df["Discipline"] = "Walk" if "walk" in file.lower() else "Run"

            all_results.append(df)

    if not all_results:
        empty = empty_table()
        return empty, empty

    results = pd.concat(all_results, ignore_index=True)

    # -----------------------------------
    # CLEAN TIME
    # -----------------------------------

    time_col = next(
        (col for col in results.columns if "time" in col.lower() or "finish" in col.lower()),
        None
    )

    if time_col:
        results["Time"] = pd.to_timedelta(results[time_col], errors="coerce")
    else:
        results["Time"] = pd.NaT

    # -----------------------------------
    # CLEAN DISTANCE
    # -----------------------------------

    if "Distance" in results.columns:
        results["Distance"] = (
            results["Distance"]
            .astype(str)
            .str.replace("km", "", regex=False)
        )
        results["Distance"] = pd.to_numeric(results["Distance"], errors="coerce")
        results["Distance"] = results["Distance"].round().astype("Int64")
    else:
        results["Distance"] = pd.NA

    # -----------------------------------
    # CATEGORY MAP (SAFE)
    # -----------------------------------

    if "Category" in results.columns and not category_map.empty:
        results = results.merge(
            category_map,
            left_on="Category",
            right_on="FinishtimeCategory",
            how="left"
        )
    else:
        results["PointsCategory"] = "Senior"

    results["PointsCategory"] = results["PointsCategory"].fillna("Senior")

    # -----------------------------------
    # SPLIT
    # -----------------------------------

    run_results = results[results["Discipline"] == "Run"]
    walk_results = results[results["Discipline"] == "Walk"]

    run_table = build_league(run_results, rules_run)
    walk_table = build_league(walk_results, rules_walk)

    return run_table, walk_table


# -----------------------------------
# CORE ENGINE
# -----------------------------------

def build_league(results, rules):

    if results.empty:
        return empty_table()

    # -----------------------------------
    # ASSIGN POINTS (SAFE)
    # -----------------------------------

    def assign_points(row):

        try:
            applicable = rules[
                (rules["Distance"] == row["Distance"]) &
                (rules["Gender"] == row["Gender"]) &
                (rules["Category"] == row["PointsCategory"]) &
                (row["Time"] >= rules["TimeFrom"]) &
                (row["Time"] <= rules["TimeTo"])
            ]

            if len(applicable) > 0:
                return applicable.iloc[0]["Points"]

        except Exception as e:
            print("⚠️ Scoring error:", e)

        # fallback
        if pd.notnull(row.get("Time")):
            return 1

        return 0

    results["Points"] = results.apply(assign_points, axis=1)

    # -----------------------------------
    # CLEAN TEXT FIELDS
    # -----------------------------------

    results["Name"] = results.get("Name", "").astype(str).str.strip()
    results["Gender"] = results.get("Gender", "").astype(str).str.strip()

    # -----------------------------------
    # CLEAN RACE NAME
    # -----------------------------------

    results["RaceName"] = (
        results["Race"]
        .str.replace("10K_", "", regex=False)
        .str.replace("21K_", "", regex=False)
        .str.replace("32K_", "", regex=False)
        .str.replace("_", " ", regex=False)
    )

    results["RaceLabel"] = results["RaceName"] + " " + results["Distance"].astype(str) + "km"

    # -----------------------------------
    # PIVOT (SAFE)
    # -----------------------------------

    try:
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
    except:
        return empty_table()

    # -----------------------------------
    # RACE COLUMNS
    # -----------------------------------

    race_cols = [c for c in race_table.columns if "km" in str(c)]

    # -----------------------------------
    # TOTALS
    # -----------------------------------

    race_table["Total Points"] = race_table[race_cols].sum(axis=1)
    race_table["Races Completed"] = (race_table[race_cols] > 0).sum(axis=1)

    # -----------------------------------
    # RANK
    # -----------------------------------

    try:
        race_table["Rank"] = (
            race_table.groupby("Gender")["Total Points"]
            .rank(method="dense", ascending=False)
            .astype(int)
        )
    except:
        race_table["Rank"] = 0

    race_table = race_table.sort_values(["Gender", "Rank"])

    # -----------------------------------
    # MEDALS (SAFE)
    # -----------------------------------

    def medal(rank):
        return "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""

    race_table["Rank"] = race_table["Rank"].apply(
        lambda r: f"{medal(r)} {r}" if isinstance(r, int) and r <= 3 else r
    )

    # -----------------------------------
    # SORT RACES (SAFE)
    # -----------------------------------

    race_priority = ["Intercare", "Ace", "Bobbies 3-in-1"]

    def race_sort(col):
        try:
            race, dist = col.rsplit(" ", 1)
            dist = int(dist.replace("km", ""))
            race_index = race_priority.index(race) if race in race_priority else 999
            return (race_index, dist)
        except:
            return (999, 999)

    race_cols = sorted(race_cols, key=race_sort)

    # -----------------------------------
    # FINAL STRUCTURE
    # -----------------------------------

    base_cols = ["Name", "Gender", "Rank", "Races Completed", "Total Points"]

    race_table = race_table[base_cols + race_cols]

    return race_table


# -----------------------------------
# EMPTY TABLE
# -----------------------------------

def empty_table():
    return pd.DataFrame(columns=[
        "Name",
        "Gender",
        "Rank",
        "Races Completed",
        "Total Points"
    ])