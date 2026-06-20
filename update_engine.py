import pandas as pd
import os


RESULT_EXTENSIONS = (".csv", ".xlsx")


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
        if file.lower().endswith(RESULT_EXTENSIONS):

            try:
                df = read_result_file(os.path.join("results", file))
            except Exception as e:
                print(f"❌ Skipping {file}: {e}")
                continue

            df["Race"] = os.path.splitext(file)[0]
            df["Discipline"] = "Walk" if "walk" in file.lower() else "Run"

            all_results.append(df)

    if not all_results:
        return empty_table(), empty_table(), {}, {}

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

    # TEXT
    results["Name"] = results.get("Name", "").astype(str).str.strip()
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

    run_table = build_league(run_results, rules_run, max_times_run)
    walk_table = build_league(walk_results, rules_walk, max_times_walk)

    run_rivals = attach_rivals(run_table) if not run_table.empty else {}
    walk_rivals = attach_rivals(walk_table) if not walk_table.empty else {}

    return run_table, walk_table, run_rivals, walk_rivals


# -----------------------------------
# CORE ENGINE
# -----------------------------------

def build_league(results, rules, max_times):

    if results.empty:
        return empty_table()

    if rules.empty:
        print("❌ No rules loaded")
        return empty_table()

    results = results.copy()

    # -----------------------------------
    # ASSIGN POINTS
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

        if pd.notnull(row["Time"]):
            return 1

        return 0

    results.loc[:, "Points"] = results.apply(assign_points, axis=1)

    # -----------------------------------
    # VALIDATION
    # -----------------------------------
    total_points = results["Points"].sum()
    print("🏁 Total Points:", total_points)

    if total_points == 0:
        print("🚨 All points = 0 → rules mismatch")
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
        else f"{r['RaceName']}",
        axis=1
    )

    print("🟢 RACES FOUND:", results["RaceLabel"].unique())

    # -----------------------------------
    # DEDUPLICATE
    # -----------------------------------
    results = results.sort_values("Time")

    results = results.drop_duplicates(
        subset=["Name", "Race", "Distance"],
        keep="first"
    )

    # -----------------------------------
    # ATHLETE ID (UNIQUE + STABLE)
    # -----------------------------------
    results["AthleteID"] = (
        results["Name"].str.lower().str.replace(r"\s+", "-", regex=True)
        + "_" +
        results["Gender"].str.lower()
        + "_" +
        results["PointsCategory"].str.lower()
    )

    athlete_profiles = (
        results.groupby("AthleteID")
        .agg({
            "Name": canonical_name,
            "Gender": "first",
            "PointsCategory": "first"
        })
        .reset_index()
    )

    # -----------------------------------
    # PIVOT
    # -----------------------------------
    race_table = (
        results.pivot_table(
            index=["AthleteID"],
            columns="RaceLabel",
            values="Points",
            aggfunc="max",
            fill_value=0
        )
        .reset_index()
    )

    race_table = race_table.merge(athlete_profiles, on="AthleteID", how="left")

    # -----------------------------------
    # DYNAMIC RACE COLS (FIXED)
    # -----------------------------------
    base_cols = ["AthleteID", "Name", "Gender", "PointsCategory"]

    race_cols = [c for c in race_table.columns if c not in base_cols]

    # -----------------------------------
    # TOTALS
    # -----------------------------------
    race_table["Total Points"] = race_table[race_cols].sum(axis=1)
    race_table["Races Completed"] = (race_table[race_cols] > 0).sum(axis=1)

    # -----------------------------------
    # RANK
    # -----------------------------------
    race_table["RankNum"] = (
        race_table.groupby("Gender")["Total Points"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    def medal(rank):
        return "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""

    race_table["Rank"] = race_table["RankNum"].apply(
        lambda r: f"{medal(r)} {r}" if r <= 3 else r
    )

    race_table = race_table.sort_values(["Gender", "RankNum"])

    # -----------------------------------
    # FINAL
    # -----------------------------------
    final_cols = ["AthleteID", "Name", "Gender", "PointsCategory", "Rank", "Races Completed", "Total Points"]

    return race_table[final_cols + race_cols]


# -----------------------------------
# RIVALS
# -----------------------------------

def attach_rivals(race_table):

    race_table = race_table.copy()

    # Safety: ensure RankNum exists
    if "RankNum" not in race_table.columns:
        race_table["RankNum"] = (
            race_table["Rank"]
            .astype(str)
            .str.extract(r"(\d+)")
            .astype(int)
        )

    rivals = {}

    for (gender, category), group in race_table.groupby(["Gender", "PointsCategory"]):

        group = group.sort_values("RankNum").reset_index(drop=True)

        for i in range(len(group)):

            athlete = group.iloc[i]
            athlete_id = athlete["AthleteID"]
            athlete_points = athlete["Total Points"]

            rival = None
            gap = None
            direction = None

            # chase person above
            if i > 0:
                rival_row = group.iloc[i - 1]
                rival = rival_row["Name"]
                gap = rival_row["Total Points"] - athlete_points
                direction = "behind"

            # leader → show who is chasing
            elif i < len(group) - 1:
                rival_row = group.iloc[i + 1]
                rival = rival_row["Name"]
                gap = athlete_points - rival_row["Total Points"]
                direction = "ahead"

            rivals[athlete_id] = {
                "rival": rival,
                "gap": int(gap) if gap is not None else None,
                "direction": direction
            }

    return rivals
# -----------------------------------
# HELPERS
# -----------------------------------

def safe_read(file, cols=None):
    try:
        return pd.read_csv(file)
    except:
        return pd.DataFrame(columns=cols if cols else [])


def read_result_file(path):
    filename = getattr(path, "filename", str(path))
    ext = os.path.splitext(filename)[1].lower()
    source = getattr(path, "stream", path)

    if hasattr(source, "seek"):
        source.seek(0)

    if ext == ".csv":
        df = pd.read_csv(source, sep=";")
    elif ext == ".xlsx":
        df = pd.read_excel(source)
    else:
        raise ValueError("Unsupported result file type")

    return normalize_result_columns(df)


def normalize_result_columns(df):
    df = df.dropna(how="all").copy()

    if not has_result_headers(df.columns):
        header_idx = find_result_header_row(df)
        if header_idx is None:
            raise ValueError("Could not find result headers")

        header = df.iloc[header_idx].tolist()
        df = df.iloc[header_idx + 1:].copy()
        df.columns = header

    df.columns = [normalize_header(c) for c in df.columns]
    df = df.rename(columns={
        "Participant": "Name",
        "Bibno": "Race No",
        "Bib No": "Race No",
        "Pos": "Pos",
    })

    df = df.dropna(how="all").copy()

    if "Time" not in df.columns and "Finish" in df.columns:
        df["Time"] = df["Finish"]

    for column in ["Time", "Finish"]:
        if column in df.columns:
            df[column] = df[column].apply(normalize_time_value)

    required = ["Name", "Gender", "Category", "Distance"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    return df


def normalize_header(value):
    value = str(value).strip()
    value = value.replace("\ufeff", "")
    value = value.rstrip(".")
    return value


def normalize_time_value(value):
    if pd.isna(value):
        return value

    text = str(value).strip()
    if text.count(":") == 1:
        minutes, seconds = text.split(":")
        if minutes.isdigit() and seconds.isdigit():
            return f"00:{int(minutes):02d}:{int(seconds):02d}"

    return value


def canonical_name(values):
    names = [str(v).strip() for v in values if pd.notna(v) and str(v).strip()]
    if not names:
        return ""

    return sorted(
        names,
        key=lambda name: (
            sum(1 for char in name if char.isupper()),
            len(name)
        ),
        reverse=True
    )[0]


def header_key(value):
    return normalize_header(value).lower().replace(" ", "")


def has_result_headers(columns):
    keys = {header_key(c) for c in columns}
    return (
        ("name" in keys or "participant" in keys) and
        "gender" in keys and
        "category" in keys and
        "distance" in keys and
        ("time" in keys or "finish" in keys)
    )


def find_result_header_row(df):
    for idx in range(min(len(df), 10)):
        if has_result_headers(df.iloc[idx].tolist()):
            return idx
    return None


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

    return (
        rules.dropna(subset=["TimeTo"])
        .groupby(["Distance", "Gender", "Category"])["TimeTo"]
        .max()
        .to_dict()
    )


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
        "AthleteID",
        "Name",
        "Gender",
        "PointsCategory",
        "Rank",
        "Races Completed",
        "Total Points"
    ])
