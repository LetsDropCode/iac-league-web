from flask import Flask, render_template, request, redirect, session, abort
import os
from update_engine import process_league
from datetime import datetime
import bleach
import logging

# Security libraries
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_seasurf import SeaSurf
from flask_talisman import Talisman


app = Flask(__name__)

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
)

# -----------------------------------
# SECRET KEY
# -----------------------------------

app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# -----------------------------------
# SECURE COOKIE SETTINGS
# -----------------------------------

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

# -----------------------------------
# CONTENT SECURITY POLICY
# -----------------------------------

csp = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://code.jquery.com"
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://fonts.googleapis.com"
    ],
    "font-src": [
        "'self'",
        "https://fonts.gstatic.com",
        "data:"
    ],
    "img-src": [
        "'self'",
        "data:",
        "https:"
    ],
    "connect-src": [
        "'self'"
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

    blocked = [
        "curl",
        "wget",
        "python",
        "scrapy",
        "httpclient",
        "bot",
        "crawler"
    ]

    if any(bot in ua for bot in blocked):
        abort(403)

# -----------------------------------
# INPUT SANITIZER
# -----------------------------------

def sanitize(value):
    if value:
        return bleach.clean(value)
    return value

# -----------------------------------
# ROUTES
# -----------------------------------

@app.route("/")
def home():
    race_table = process_league()

    last_updated = datetime.utcnow().strftime("%d %B %Y %H:%M UTC")

    return render_template(
        "index.html",
        table=race_table.to_html(index=False, classes="display"),
        last_updated=last_updated
    )

# -----------------------------------

@app.route("/admin", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def admin():

    if request.method == "POST":

        password = sanitize(request.form.get("password"))

        if password == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/upload")

    return render_template("login.html")

# -----------------------------------

@app.route("/upload", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def upload():

    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":

        file = request.files.get("file")

        if file and file.filename.endswith(".csv"):

            filename = sanitize(file.filename)

            filepath = os.path.join("results", filename)

            file.save(filepath)

        return redirect("/")

    return render_template("admin.html")

# -----------------------------------
# ERROR HANDLING
# -----------------------------------

@app.errorhandler(403)
def forbidden(e):
    return "Forbidden", 403


@app.errorhandler(404)
def not_found(e):
    return "Page not found", 404


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