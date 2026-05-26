from flask import Flask, render_template, request, redirect, session, abort
import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import bleach
from werkzeug.utils import secure_filename

# Security libraries
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_seasurf import SeaSurf
from flask_talisman import Talisman

# Your engine
from update_engine import process_league

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

# -----------------------------------
# FILE VALIDATION
# -----------------------------------

ALLOWED_EXTENSIONS = {"csv"}

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

    # 🔥 Hide backend columns
    run_table = run_table.drop(columns=["AthleteID"], errors="ignore")

    last_updated = datetime.now(
        ZoneInfo("Africa/Johannesburg")
    ).strftime("%Y-%m-%d %H:%M SAST")

    return render_template(
        "index.html",
        table=run_table.to_html(
            index=False,
            classes="display nowrap",
            border=0,
            table_id="leagueTable"
        ),
        last_updated=last_updated,
        league="Run"
    )

# -----------------------------------
# WALK
# -----------------------------------

@app.route("/walk")
def walk():
    _, walk_table, _, _ = get_tables()

    walk_table = walk_table.drop(columns=["AthleteID"], errors="ignore")

    last_updated = datetime.now(
        ZoneInfo("Africa/Johannesburg")
    ).strftime("%Y-%m-%d %H:%M SAST")

    return render_template(
        "index.html",
        table=walk_table.to_html(
            index=False,
            classes="display nowrap",
            border=0,
            table_id="leagueTable"
        ),
        last_updated=last_updated,
        league="Walk"
    )

# -----------------------------------
# ADMIN LOGIN
# -----------------------------------

@app.route("/admin", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin():
    if request.method == "POST":

        password = sanitize(request.form.get("password"))

        if password == ADMIN_PASSWORD:
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

        if file and allowed_file(file.filename):

            filename = secure_filename(file.filename)
            filepath = os.path.join("results", filename)

            file.save(filepath)

            # 🔥 Recalculate
            clear_cache()

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

    run_table, _, rivals_map, _ = get_tables()

    athlete_row = run_table[run_table["AthleteID"] == athlete_id]

    if athlete_row.empty:
        abort(404)

    athlete_data = athlete_row.iloc[0]

    # Load all results
    all_files = [
        pd.read_csv(os.path.join("results", f), sep=";")
        for f in os.listdir("results") if f.endswith(".csv")
    ]

    results = pd.concat(all_files, ignore_index=True)

    history = results[
        results["Name"].str.lower() == athlete_data["Name"].lower()
    ].copy()

    # Clean history
    history["Race"] = history.get("Race", "Unknown")
    history["Distance"] = history.get("Distance", "")
    history["Time"] = history.get("Time", "")
    history["Points"] = history.get("Points", "")

    rival_data = rivals_map.get(athlete_id, {})

    return render_template(
        "athlete.html",
        athlete=athlete_data,
        rival=rival,
        history=history
    )

# -----------------------------------
# POINTS SYSTEM (FIXED)
# -----------------------------------

@app.route("/points")
def points():

    try:
        df = pd.read_csv("points_rules.csv")
    except:
        df = pd.DataFrame()

    return render_template(
        "points.html",
        table=df.to_html(
            index=False,
            classes="display nowrap",
            border=0
        )
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
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    return response

# -----------------------------------
# START SERVER
# -----------------------------------

if __name__ == "__main__":
    app.run(debug=False)