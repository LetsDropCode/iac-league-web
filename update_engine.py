import pandas as pd
import os


# -----------------------------------
# MAIN ENTRY
# -----------------------------------

def process_league():

    os.makedirs("results", exist_ok=True)

    category_map = safe_read("category_map.csv", ["FinishtimeCategory", "PointsCategory"])
    rules_run = safe_read("points_rules.csv")
    rules_walk = safe_read("points_rules_walk.csv")

    if rules_walk.empty:
        print("⚠️ Walk rules missing — using run rules")
        rules_walk = rules_run.copy()

    clean_rules(rules_run)
    clean_rules(rules_walk)

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
    # NORMALISE CORE FIELDS
    # -----------------------------------

    # TIME
    time_col = next((c for c in results.columns if "time" in c.lower() or "finish" in c.lower()), None)
    results["Time"] = pd.to_timedelta(results[time_col], errors="coerce") if time_col else pd.NaT

    # DISTANCE
    results["Distance"] = results.get("Distance", None)
    results["Distance"] = results["Distance"].apply(clean_distance)
    results["Distance"] = pd.to_numeric(results["Distance"], errors="coerce").round().astype("Int64")

    # TEXT FIELDS
    results["Gender"] = results.get("Gender", "").astype(str).str.strip()
    results["Category"] = results.get("Category", "").astype(str).str.strip()

    # CATEGORY MAP
    if not category_map.empty:
        results = results.merge(
            category_map,
            left_on="Category",
            right_on="FinishtimeCategory",
            how="left"
        )

    results["PointsCategory"] = results.get("PointsCategory", "Senior").fillna("Senior")

    # -----------------------------------
    # SPLIT
    # -----------------------------------

    run_results = results[results["Discipline"] == "Run"].copy()
    walk_results = results[results["Discipline"] == "Walk"].copy()

    print(f"🏃 Run rows: {len(run_results)}")
    print(f"🚶 Walk rows: {len(walk_results)}")

    run_rivals = attach_rivals(run_table) if not run_table.empty else {}
    walk_rivals = attach_rivals(walk_table) if not walk_table.empty else {}

    return run_table, walk_table, run_rivals, walk_rivals

# -----------------------------------
# CORE ENGINE
# -----------------------------------

def build_league(results, rules, max_times):

    if results.empty:
        print("⚠️ No results for this discipline")
        return empty_table()

    if rules.empty:
        print("❌ No rules loaded")
        return empty_table()

    results = results.copy()

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

        # fallback = valid finisher
        if pd.notnull(row["Time"]):
            return 1

        return 0

    # ✅ THIS LINE WAS MISSING
    results.loc[:, "Points"] = results.apply(assign_points, axis=1)

    # -----------------------------------
    # VALIDATION (AFTER SCORING)
    # -----------------------------------
    total_points = results["Points"].sum()
    print("🏁 Total Points:", total_points)

    if total_points == 0:
        print("\n🚨 CRITICAL: ALL POINTS = 0")
        print("Likely rules mismatch\n")

        print("Sample results:")
        print(results[["Distance", "Gender", "PointsCategory"]].drop_duplicates())

        print("\nRules:")
        print(rules[["Distance", "Gender", "Category"]].drop_duplicates())

        return empty_table()

    # -----------------------------------
    # RACE LABEL
    # -----------------------------------
    results["RaceName"] = (
        results["Race"]
        .str.replace(r"\d+K_", "", regex=True)
        .str.replace("_", " ", regex=False)
    )

    results["RaceLabel"] = results.apply(
        lambda r: f"{r['RaceName']} {int(r['Distance'])}km"
        if pd.notnull(r["Distance"])
        else f"{r['RaceName']} Unknown",
        axis=1
    )
    # -----------------------------------
    # DEDUPLICATE RESULTS
    # -----------------------------------
    results = results.sort_values("Time")

    results = results.drop_duplicates(
        subset=["Name", "Race", "Distance"],
        keep="first"
    )

    # -----------------------------------
    # ATHLETE ID (FOR CLICKABLE UI)
    # -----------------------------------
    results["AthleteID"] = (
        results["Name"]
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "-", regex=True)
    )

    # -----------------------------------
    # PIVOT
    # -----------------------------------
    race_table = (
        results.pivot_table(
            index=["AthleteID", "Name", "Gender", "PointsCategory"],
            columns="RaceLabel",
            values="Points",
            aggfunc="max",   # 🔥 FIXED
            fill_value=0
        )
        .reset_index()
    )   
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

    base_cols = ["AthleteID", "Name", "Gender", "PointsCategory", "Rank", "Races Completed", "Total Points"]

    return race_table[base_cols + race_cols]

# -----------------------------------
# RIVALS (BY GENDER + CATEGORY)
# -----------------------------------
def attach_rivals(race_table):

    race_table = race_table.copy()

    # Extract numeric rank
    race_table["RankNum"] = race_table["Rank"].astype(str).str.extract(r"(\d+)").astype(int)

    rivals = {}

    for (gender, category), group in race_table.groupby(["Gender", "PointsCategory"]):

        group = group.sort_values("RankNum")

        for i in range(len(group)):

            athlete_id = group.iloc[i]["AthleteID"]
            rival = None

            if i > 0:
                rival = group.iloc[i - 1]["Name"]
            elif i < len(group) - 1:
                rival = group.iloc[i + 1]["Name"]

            rivals[athlete_id] = rival

    return rivals

# -----------------------------------
# ATHLETE PROFILES
# -----------------------------------

def build_athlete_profiles(results):

    results = results.copy()

    results["AthleteID"] = (
        results["Name"].str.strip().str.lower().str.replace(" ", "-")
    )

    profiles = {}

    for athlete, df in results.groupby("AthleteID"):

        profiles[athlete] = {
            "name": df["Name"].iloc[0],
            "gender": df["Gender"].iloc[0],
            "total_points": df["Points"].sum(),
            "races": df.shape[0],
            "history": df.sort_values("Time")[[
                "Race", "Distance", "Time", "Points"
            ]]
        }

    return profiles


# -----------------------------------
# HELPERS
# -----------------------------------

def safe_read(file, cols=None):
    try:
        df = pd.read_csv(file)
        return df
    except:
        return pd.DataFrame(columns=cols if cols else [])


def clean_rules(rules):
    if rules.empty:
        return

    rules["Distance"] = pd.to_numeric(rules["Distance"], errors="coerce").round().astype("Int64")
    rules["Gender"] = rules["Gender"].astype(str).str.strip()
    rules["Category"] = rules["Category"].astype(str).str.strip()
    rules["TimeFrom"] = pd.to_timedelta(rules["TimeFrom"], errors="coerce")
    rules["TimeTo"] = pd.to_timedelta(rules["TimeTo"], errors="coerce")


def build_max_times(rules):
    if rules.empty:
        return {}

    grouped = (
        rules.dropna(subset=["TimeTo"])
        .groupby(["Distance", "Gender", "Category"])["TimeTo"]
        .max()
    )

    return grouped.to_dict()


def clean_distance(val):
    try:
        val = str(val).lower().strip()

        if val in ["", "nan"]:
            return None

        if "km" in val:
            return float(val.replace("km", ""))

        if "m" in val:
            return round(float(val.replace("m", "")) * 1.609, 0)

        return float(val)

    except:
        return None


def empty_table():
    return pd.DataFrame(columns=[
        "Name",
        "Gender",
        "Rank",
        "Races Completed",
        "Total Points"
    ])