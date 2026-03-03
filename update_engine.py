import pandas as pd
import os

def process_league():
    os.makedirs("results", exist_ok=True)
    # === LOAD RULES ===
    category_map = pd.read_csv("category_map.csv")
    rules = pd.read_csv("points_rules.csv")

    rules["TimeFrom"] = pd.to_timedelta(rules["TimeFrom"])
    rules["TimeTo"] = pd.to_timedelta(rules["TimeTo"])

    # === LOAD RESULTS ===
    results_folder = "results"
    all_results = []

    for file in os.listdir(results_folder):
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(results_folder, file), sep=";")
            df["Race"] = file.replace(".csv", "")
            all_results.append(df)

    if not all_results:
        return pd.DataFrame(columns=["Name", "Gender", "PointsCategory", "TotalPoints", "LeagueRaces", "Rank"])

    results = pd.concat(all_results, ignore_index=True)

    # === TIME CONVERSION ===
    time_column = [col for col in results.columns if "time" in col.lower() or "finish" in col.lower()][0]
    results["Time"] = pd.to_timedelta(results[time_column])

    # === CLEAN DISTANCE ===
    results["Distance"] = (
        results["Distance"]
        .astype(str)
        .str.replace("km", "", regex=False)
    )
    results["Distance"] = pd.to_numeric(results["Distance"], errors="coerce")

    # === MAP CATEGORY ===
    results = results.merge(
        category_map,
        left_on="Category",
        right_on="FinishtimeCategory",
        how="left"
    )

    # === ASSIGN POINTS ===
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

    # === PIVOT + RANK ===
    results["AthleteID"] = (
        results["Name"].str.lower() + "_" +
        results["Gender"].str.lower() + "_" +
        results["PointsCategory"].str.lower()
    )

    results["RaceLabel"] = results["Race"] + " " + results["Distance"].astype(str) + "km"

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
    race_table = race_table.drop(columns=["AthleteID", "PointsCategory"], errors="ignore")
    race_cols = [
        col for col in race_table.columns
        if col not in ["AthleteID", "Name", "Gender", "PointsCategory"]
    ]

    race_table["TotalPoints"] = race_table[race_cols].sum(axis=1)
    race_table["LeagueRaces"] = (race_table[race_cols] > 0).sum(axis=1)

    race_table["Rank"] = (
        race_table.groupby("Gender")["TotalPoints"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    race_table = race_table.sort_values(["Gender", "Rank"])

    return race_table	

# ---------------------------
# Reorder Columns for Public View
# ---------------------------

race_cols = [
    col for col in race_table.columns
    if col not in [
        "AthleteID",
        "PointsCategory",
        "Name",
        "Gender",
        "Rank",
        "LeagueRaces",
        "TotalPoints"
    ]
]

race_table = race_table[
    ["Name", "Gender", "Rank", "LeagueRaces", "TotalPoints"] + race_cols
]

# ---------------------------
# Clean & Format Public Table
# ---------------------------

# Remove internal columns
race_table = race_table.drop(
    columns=["AthleteID", "PointsCategory"],
    errors="ignore"
)

# Rename columns for display
race_table = race_table.rename(columns={
    "TotalPoints": "Total Points",
    "LeagueRaces": "Races Completed"
})

# Add medals for Top 3 per gender
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

# Reorder columns cleanly
base_cols = ["Name", "Gender", "Rank", "Races Completed", "Total Points"]

race_cols = [
    col for col in race_table.columns
    if col not in base_cols
]

race_table = race_table[base_cols + race_cols]

