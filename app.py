from flask import Flask, render_template, request, redirect, session
import os
from update_engine import process_league
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change_this_to_something_secure"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


@app.route("/")
def home():
    race_table = process_league()
    last_updated = datetime.utcnow().strftime("%d %B %Y %H:%M UTC")
    return render_template(
        "index.html",
        table=race_table.to_html(index=False, classes="display"),
        last_updated=last_updated
    )

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/upload")
    return render_template("login.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if not session.get("admin"):
        return redirect("/admin")

    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename.endswith(".csv"):
            file.save(os.path.join("results", file.filename))
        return redirect("/")
    return render_template("admin.html")

if __name__ == "__main__":
    app.run(debug=True)
