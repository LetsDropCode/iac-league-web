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

    # -----------------------------------
    # FALLBACK: WALK RULES
    # -----------------------------------
    if rules_walk.empty:
        print("⚠️ Walk rules missing — using run rules")
        rules_walk = rules_run.copy()

    # -----------------------------------
    # CLEAN RULES
    # -----------------------------------
    for rules in [rules_run, rules_walk]:
        if not rules.empty:
            rules["Distance"] = pd.to_numeric(rules["Distance"], errors="coerce").round().astype("Int64")
            rules["TimeFrom"] = pd.to_timedelta(rules["TimeFrom"], errors="coerce")
            rules["TimeTo"] = pd.to_timedelta(rules["TimeTo"], errors="coerce")

    # -----------------------------------
    # BUILD MAX TIMES (FINISHER RULE)
    # -----------------------------------
    def build_max_times(rules):
        if rules.empty:
            return {}

        grouped = (
            rules
            .dropna(subset=["TimeTo"])
            .groupby(["Distance", "Gender", "Category"])["TimeTo"]
            .max()
        )

        return grouped.to_dict()

    max_times_run = build_max_times(rules_run)
    max_times_walk = build_max_times(rules_walk)

    # -----------------------------------
    # LOAD RESULTS
    # -----------------------------------
    all_results = []

    for file in os.listdir("results"):
        if file.endswith(".csv"):
            try:
                df = pd.read_csv(os.path.join("results", file), sep=";")
            except Exception as e:
                print(f"❌ Skipping {file}: {e}")
                continue

            df["Race"] = file.replace(".csv", "")
            df["Discipline"] = "Walk" if "walk" in file.lower() else "Run"

            all_results.append(df)

    if not all_results:
        return empty_table(), empty_table()

    results = pd.concat(all_results, ignore_index=True)

    # -----------------------------------
    # CLEAN TIME
    # -----------------------------------
    time_col = next(
        (c for c in results.columns if "time" in c.lower() or "finish" in c.lower()),
        None
    )

    if time_col:
        results["Time"] = pd.to_timedelta(results[time_col], errors="coerce")
    else:
        results["Time"] = pd.NaT

    # -----------------------------------
    # CLEAN DISTANCE
    # -----------------------------------
    def clean_distance(val):
        try:
            val = str(val).lower().strip()

            if val in ["", "nan"]:
                return None

            if "km" in val:
                return float(val.replace("km", "").strip())

            if "m" in val:  # miles → km
                miles = float(val.replace("m", "").strip())
                return round(miles * 1.609, 0)

            return float(val)

        except:
            return None

    if "Distance" in results.columns:
        results["Distance"] = results["Distance"].apply(clean_distance)
        results["Distance"] = pd.to_numeric(results["Distance"], errors="coerce").round().astype("Int64")
    else:
        results["Distance"] = pd.NA

    # -----------------------------------
    # CATEGORY MAP
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
    run_results = results[results["Discipline"] == "Run"].copy()
    walk_results = results[results["Discipline"] == "Walk"].copy()

    print(f"🏃 Run rows: {len(run_results)}")
    print(f"🚶 Walk rows: {len(walk_results)}")

    run_table = build_league(run_results, rules_run, max_times_run)
    walk_table = build_league(walk_results, rules_walk, max_times_walk)

    return run_table, walk_table


# -----------------------------------
# CORE ENGINE
# -----------------------------------

def build_league(results, rules, max_times):

    results = results.copy()

    if results.empty or rules.empty:
        return empty_table()

    # -----------------------------------
    # CLEAN TEXT
    # -----------------------------------
    results["Name"] = results.get("Name", "").astype(str).str.strip()
    results["Gender"] = results.get("Gender", "").astype(str).str.strip()

    # -----------------------------------
    # ASSIGN POINTS (CRITICAL FIX)
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

            if not applicable.empty:
                return int(applicable.iloc[0]["Points"])

            # FINISHER RULE
            key = (row["Distance"], row["Gender"], row["PointsCategory"])
            max_time = max_times.get(key)

            if max_time is not None and pd.notnull(row["Time"]) and row["Time"] > max_time:
                return 1

        except Exception as e:
            print("⚠️ Scoring error:", e)

        return 0

    # 🔥 GUARANTEED COLUMN CREATION
    results.loc[:, "Points"] = results.apply(assign_points, axis=1)

    # -----------------------------------
    # RACE LABEL
    # -----------------------------------
    results["RaceName"] = (
        results["Race"]
        .str.replace("10K_", "", regex=False)
        .str.replace("21K_", "", regex=False)
        .str.replace("26K_", "", regex=False)
        .str.replace("32K_", "", regex=False)
        .str.replace("_", " ", regex=False)
    )

    results["RaceLabel"] = results.apply(
        lambda r: f"{r['RaceName']} {int(r['Distance'])}km"
        if pd.notnull(r["Distance"])
        else f"{r['RaceName']} Unknown",
        axis=1
    )

    # -----------------------------------
    # PIVOT
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
    except Exception as e:
        print("❌ Pivot failed:", e)
        return empty_table()

    race_cols = [c for c in race_table.columns if "km" in str(c)]

    # -----------------------------------
    # TOTALS
    # -----------------------------------
    race_table["Total Points"] = race_table[race_cols].sum(axis=1)
    race_table["Races Completed"] = (race_table[race_cols] > 0).sum(axis=1)

    # -----------------------------------
    # RANK
    # -----------------------------------
    race_table["Rank"] = (
        race_table.groupby("Gender")["Total Points"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    race_table = race_table.sort_values(["Gender", "Rank"])

    # -----------------------------------
    # MEDALS
    # -----------------------------------
    def medal(rank):
        return "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""

    race_table["Rank"] = race_table["Rank"].apply(
        lambda r: f"{medal(r)} {r}" if isinstance(r, int) and r <= 3 else r
    )

    # -----------------------------------
    # FINAL STRUCTURE
    # -----------------------------------
    base_cols = ["Name", "Gender", "Rank", "Races Completed", "Total Points"]

    return race_table[base_cols + race_cols]


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