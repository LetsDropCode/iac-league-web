from flask import Flask, render_template, request, redirect, session, abort, flash
import os
import logging
import pandas as pd
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html import escape
from hmac import compare_digest
from urllib.parse import quote

import bleach
from werkzeug.utils import secure_filename

# Security libraries
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_seasurf import SeaSurf
from flask_talisman import Talisman

# Your engine
from update_engine import process_league, read_result_file, clean_distance

from functools import lru_cache


app = Flask(__name__)

# -----------------------------------
# CONFIG
# -----------------------------------

app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

app.permanent_session_lifetime = timedelta(hours=2)

# -----------------------------------
# CONTENT SECURITY POLICY
# -----------------------------------

csp = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "https://code.jquery.com",
        "https://cdn.datatables.net"
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.datatables.net"
    ],
    "img-src": [
        "'self'",
        "data:",
        "https:"
    ],
    "font-src": [
        "'self'",
        "data:"
    ]
}

Talisman(app, content_security_policy=csp)

# -----------------------------------
# RATE LIMITING
# -----------------------------------

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# -----------------------------------
# CSRF PROTECTION
# -----------------------------------

csrf = SeaSurf(app)

BASE_LEAGUE_COLS = [
    "AthleteID",
    "Name",
    "Gender",
    "PointsCategory",
    "Rank",
    "Rank Change",
    "Category Rank",
    "Races Completed",
    "Total Points",
]

# -----------------------------------
# LOGGING
# -----------------------------------

logging.basicConfig(level=logging.INFO)

@app.before_request
def log_requests():
    logging.info(f"{request.remote_addr} accessed {request.path}")

# -----------------------------------
# BOT BLOCKER
# -----------------------------------

@app.before_request
def block_bots():
    ua = request.headers.get("User-Agent", "").lower()

    blocked = ["curl", "wget", "python-requests", "scrapy", "httpclient"]

    if any(bot in ua for bot in blocked):
        abort(403)

# -----------------------------------
# INPUT SANITIZER
# -----------------------------------

def sanitize(value):
    return bleach.clean(value) if value else value

def numeric_rank(value):
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None

def latest_result_file():
    files = [
        os.path.join("results", f)
        for f in os.listdir("results")
        if f.lower().endswith((".csv", ".xlsx"))
    ]
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def race_stem(filename):
    if not filename:
        return ""
    name = os.path.splitext(os.path.basename(filename))[0]
    return re.sub(r"^\d+K_", "", name).replace("_", " ")

def add_leaderboard_context(df):
    if df.empty:
        return df

    table = df.copy()
    race_cols = [c for c in table.columns if c not in BASE_LEAGUE_COLS]

    table["CategoryRankNum"] = (
        table.groupby(["Gender", "PointsCategory"])["Total Points"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    table["Category Rank"] = table["CategoryRankNum"]

    latest_stem = race_stem(latest_result_file())
    latest_cols = [c for c in race_cols if c.startswith(latest_stem)] if latest_stem else []

    if latest_cols:
        table["Previous Points"] = table["Total Points"] - table[latest_cols].sum(axis=1)
        table["PreviousRankNum"] = (
            table.groupby("Gender")["Previous Points"]
            .rank(method="dense", ascending=False)
            .astype(int)
        )

        def rank_change(row):
            current = numeric_rank(row["Rank"])
            previous = int(row["PreviousRankNum"])
            if row["Previous Points"] <= 0 and row["Total Points"] > 0:
                return "new"
            delta = previous - current
            if delta > 0:
                return f"+{delta}"
            if delta < 0:
                return str(delta)
            return "same"

        table["Rank Change"] = table.apply(rank_change, axis=1)
        table = table.drop(columns=["Previous Points", "PreviousRankNum"], errors="ignore")
    else:
        table["Rank Change"] = "same"

    table = table.drop(columns=["CategoryRankNum"], errors="ignore")
    race_cols = [c for c in table.columns if c not in BASE_LEAGUE_COLS]
    ordered_cols = [c for c in BASE_LEAGUE_COLS if c in table.columns]
    return table[ordered_cols + race_cols]

def display_table(df, league):
    if df.empty:
        return df

    display = df.copy()

    for column in display.select_dtypes(include=["object"]).columns:
        display[column] = display[column].astype(str).map(escape)

    links = []
    for _, row in df.iterrows():
        athlete_id = quote(str(row["AthleteID"]), safe="")
        name = escape(str(row["Name"]))
        links.append(f'<a class="athlete-link" href="/athlete/{league.lower()}/{athlete_id}">{name}</a>')

    display["Name"] = links
    return display.drop(columns=["AthleteID"], errors="ignore")

def league_summary(df):
    if df.empty:
        return {
            "athletes": 0,
            "races": 0,
            "leader_male": "No results",
            "leader_female": "No results",
        }

    race_cols = [c for c in df.columns if c not in BASE_LEAGUE_COLS]

    def leader(gender):
        subset = df[df["Gender"] == gender]
        if subset.empty:
            return "No results"
        row = subset.sort_values("Total Points", ascending=False).iloc[0]
        return f"{row['Name']} ({int(row['Total Points'])})"

    return {
        "athletes": len(df),
        "races": len(race_cols),
        "leader_male": leader("Male"),
        "leader_female": leader("Female"),
    }

def latest_result_name():
    latest = latest_result_file()
    if not latest:
        return "No uploads yet"
    return os.path.basename(latest).replace(".csv", "").replace("_", " ")

def result_race_label(row):
    race_name = (
        str(row["Race"])
        .replace(".csv", "")
        .replace(".xlsx", "")
    )
    race_name = re.sub(r"\d+K_", "", race_name).replace("_", " ")
    if pd.notnull(row["Distance"]):
        return f"{race_name} {int(row['Distance'])}km"
    return race_name

def format_duration(value):
    if pd.isna(value):
        return ""
    seconds = int(value.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def load_result_details():
    try:
        category_map = pd.read_csv("category_map.csv")
    except Exception:
        category_map = pd.DataFrame(columns=["FinishtimeCategory", "PointsCategory"])
    frames = []

    for file in os.listdir("results"):
        if not file.lower().endswith((".csv", ".xlsx")):
            continue

        try:
            df = read_result_file(os.path.join("results", file))
        except Exception:
            continue

        df = df.copy()
        df["Race"] = os.path.splitext(file)[0]
        df["Discipline"] = "Walk" if "walk" in file.lower() else "Run"
        df["Distance"] = df["Distance"].apply(clean_distance)
        df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce").round().astype("Int64")
        df["Name"] = df["Name"].astype(str).str.strip()
        df["Gender"] = df["Gender"].astype(str).str.strip()
        df["Category"] = df["Category"].astype(str).str.strip()

        if not category_map.empty:
            df = df.merge(
                category_map,
                left_on="Category",
                right_on="FinishtimeCategory",
                how="left"
            )

        df["PointsCategory"] = df.get("PointsCategory", "Senior").fillna("Senior")
        df["AthleteID"] = (
            df["Name"].str.lower().str.replace(r"\s+", "-", regex=True)
            + "_" +
            df["Gender"].str.lower()
            + "_" +
            df["PointsCategory"].str.lower()
        )
        time_col = next((c for c in df.columns if "time" in c.lower() or "finish" in c.lower()), None)
        df["Time"] = pd.to_timedelta(df[time_col], errors="coerce") if time_col else pd.NaT
        df["RaceLabel"] = df.apply(result_race_label, axis=1)
        frames.append(df[["AthleteID", "Discipline", "RaceLabel", "Time"]])

    if not frames:
        return pd.DataFrame(columns=["AthleteID", "Discipline", "RaceLabel", "Time"])

    details = pd.concat(frames, ignore_index=True)
    details = details.sort_values("Time")
    return details.drop_duplicates(
        subset=["AthleteID", "Discipline", "RaceLabel"],
        keep="first"
    )

def athlete_history_with_times(athlete_row, table, league):
    race_cols = [c for c in table.columns if c not in BASE_LEAGUE_COLS]
    history = (
        athlete_row[race_cols]
        .T
        .reset_index()
        .rename(columns={"index": "Race", athlete_row.index[0]: "Points"})
    )
    history = history[history["Points"] > 0].copy()

    if history.empty:
        history["Time"] = []
        return history

    details = load_result_details()
    details = details[
        (details["AthleteID"] == athlete_row.iloc[0]["AthleteID"]) &
        (details["Discipline"].str.lower() == league.lower())
    ]

    time_map = details.set_index("RaceLabel")["Time"].to_dict()
    history["Time"] = history["Race"].map(time_map).map(format_duration)
    return history[["Race", "Time", "Points"]]

def preview_results_file(file):
    try:
        df = read_result_file(file)
    except Exception as exc:
        return {"ok": False, "error": f"Could not read this result file: {exc}"}

    columns = set(df.columns)
    time_col = next((c for c in df.columns if "time" in c.lower() or "finish" in c.lower()), None)
    missing = [c for c in ["Name", "Gender", "Category", "Distance"] if c not in columns]
    if not time_col:
        missing.append("Time/Finish column")

    duplicate_subset = [c for c in ["Name", "Distance"] if c in columns]
    duplicates = int(df.duplicated(subset=duplicate_subset).sum()) if duplicate_subset else 0
    blank_names = int(df["Name"].isna().sum()) if "Name" in columns else 0
    invalid_times = int(pd.to_timedelta(df[time_col], errors="coerce").isna().sum()) if time_col else len(df)

    return {
        "ok": not missing,
        "rows": len(df),
        "columns": len(df.columns),
        "missing": missing,
        "duplicates": duplicates,
        "blank_names": blank_names,
        "invalid_times": invalid_times,
    }

# -----------------------------------
# FILE VALIDATION
# -----------------------------------

ALLOWED_EXTENSIONS = {"csv", "xlsx"}
UNSUPPORTED_EXTENSIONS = {"numbers"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# -----------------------------------
# CACHE
# -----------------------------------

@lru_cache(maxsize=1)
def get_tables():
    return process_league()

def clear_cache():
    get_tables.cache_clear()

# -----------------------------------
# HOME (RUN)
# -----------------------------------

@app.route("/")
def home():
    run_table, _, _, _ = get_tables()
    run_table = add_leaderboard_context(run_table)

    last_updated = datetime.now(
        ZoneInfo("Africa/Johannesburg")
    ).strftime("%Y-%m-%d %H:%M SAST")

    return render_template(
        "index.html",
        table=display_table(run_table, "run").to_html(
            index=False,
            classes="display nowrap",
            border=0,
            table_id="leagueTable",
            escape=False
        ),
        last_updated=last_updated,
        league="Run",
        summary=league_summary(run_table),
        latest_result=latest_result_name()
    )

# -----------------------------------
# WALK
# -----------------------------------

@app.route("/walk")
def walk():
    _, walk_table, _, _ = get_tables()
    walk_table = add_leaderboard_context(walk_table)

    last_updated = datetime.now(
        ZoneInfo("Africa/Johannesburg")
    ).strftime("%Y-%m-%d %H:%M SAST")

    return render_template(
        "index.html",
        table=display_table(walk_table, "walk").to_html(
            index=False,
            classes="display nowrap",
            border=0,
            table_id="leagueTable",
            escape=False
        ),
        last_updated=last_updated,
        league="Walk",
        summary=league_summary(walk_table),
        latest_result=latest_result_name()
    )

# -----------------------------------
# ADMIN LOGIN
# -----------------------------------

@app.route("/admin", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin():
    if request.method == "POST":

        password = sanitize(request.form.get("password"))

        if ADMIN_PASSWORD and compare_digest(password or "", ADMIN_PASSWORD):
            session.permanent = True
            session["admin"] = True
            return redirect("/upload")

        return render_template("login.html", error="Invalid password")

    return render_template("login.html")

# -----------------------------------
# UPLOAD
# -----------------------------------

@app.route("/upload", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def upload():

    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":

        file = request.files.get("file")
        action = request.form.get("action", "upload")

        if file and allowed_file(file.filename):
            preview = preview_results_file(file)
            file.seek(0)

            if action == "preview":
                return render_template("admin.html", preview=preview)

            filename = secure_filename(file.filename)
            filepath = os.path.join("results", filename)

            file.save(filepath)

            # 🔥 Recalculate
            clear_cache()
            flash(f"Uploaded {filename} and recalculated the league.", "success")
        else:
            ext = file.filename.rsplit(".", 1)[1].lower() if file and "." in file.filename else ""
            if ext in UNSUPPORTED_EXTENSIONS:
                flash("Numbers files cannot be read by the league app. Export it as CSV or Excel, then upload again.", "error")
            else:
                flash("Please choose a valid CSV or Excel file.", "error")

        return redirect("/")

    return render_template("admin.html")

# -----------------------------------
# LOGOUT
# -----------------------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# -----------------------------------
# ATHLETE PROFILE
# -----------------------------------

@app.route("/athlete/<athlete_id>")
def athlete(athlete_id):
    return athlete_profile("run", athlete_id)

@app.route("/athlete/<league>/<athlete_id>")
def athlete_profile(league, athlete_id):
    run_table, walk_table, run_rivals, walk_rivals = get_tables()
    run_table = add_leaderboard_context(run_table)
    walk_table = add_leaderboard_context(walk_table)

    if league == "walk":
        table = walk_table
        rivals_map = walk_rivals
        back_url = "/walk"
        league_label = "Walk"
    else:
        table = run_table
        rivals_map = run_rivals
        back_url = "/"
        league_label = "Run"

    athlete_row = table[table["AthleteID"] == athlete_id]

    if athlete_row.empty:
        abort(404)

    athlete_data = athlete_row.iloc[0]

    history = athlete_history_with_times(athlete_row, table, league)

    rival_data = rivals_map.get(athlete_id, {})

    return render_template(
        "athlete.html",
        athlete=athlete_data,
        rival_data=rival_data,
        history=history,
        back_url=back_url,
        league=league_label
    )

# -----------------------------------
# POINTS SYSTEM (FIXED)
# -----------------------------------

@app.route("/points")
def points():

    def read_points_rules(filename, discipline):
        try:
            df = pd.read_csv(filename)
        except:
            return pd.DataFrame(columns=["Discipline", "Distance", "Gender", "Category", "TimeFrom", "TimeTo", "Points"])

        df = df.copy()
        df.insert(0, "Discipline", discipline)
        return df

    df = pd.concat(
        [
            read_points_rules("points_rules.csv", "Run"),
            read_points_rules("points_rules_walk.csv", "Walk"),
        ],
        ignore_index=True
    )

    if not df.empty:
        df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce").astype("Int64")
        df["Points"] = pd.to_numeric(df["Points"], errors="coerce").astype("Int64")
        df["TimeFrom"] = pd.to_timedelta(df["TimeFrom"], errors="coerce")
        df["TimeTo"] = pd.to_timedelta(df["TimeTo"], errors="coerce")

        def display_time(value):
            if pd.isna(value):
                return ""
            seconds = int(value.total_seconds())
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"

        df["TimeFrom"] = df["TimeFrom"].map(display_time)
        df["TimeTo"] = df["TimeTo"].map(display_time)

    rules = df.to_dict(orient="records") if not df.empty else []

    return render_template(
        "points.html",
        table=df.to_html(
            index=False,
            classes="display nowrap",
            border=0,
            table_id="pointsTable"
        ),
        rules=rules,
        distances=sorted(df["Distance"].dropna().unique().tolist()) if not df.empty else [],
        categories=sorted(df["Category"].dropna().unique().tolist()) if not df.empty else [],
    )

# -----------------------------------
# ERRORS
# -----------------------------------

@app.errorhandler(403)
def forbidden(e):
    return "Forbidden", 403

@app.errorhandler(404)
def not_found(e):
    return "Page not found", 404

# -----------------------------------
# SECURITY HEADERS
# -----------------------------------

@app.after_request
def apply_security_headers(response):
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return response

# -----------------------------------
# START SERVER
# -----------------------------------

if __name__ == "__main__":
    app.run(debug=False)
