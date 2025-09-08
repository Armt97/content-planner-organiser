from flask import Flask, render_template, url_for
import os
from models import db

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES = os.path.join(BASE_DIR, "frontend")
STATIC = os.path.join(BASE_DIR, "frontend", "static")

app = Flask(__name__, template_folder=TEMPLATES, static_folder=STATIC)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///visiona.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/idea-board")
def idea_board():
    return render_template("idea-board.html")

@app.route("/calendar")
def calendar():
    return render_template("calendar.html")

@app.route("/library")
def library():
    return render_template("library.html")

@app.route("/insights")
def insights():
    return render_template("insights.html")

@app.route("/init-db")
def init_db():
    with app.app_context():
        db.create_all()
    return {"status": "database initialised"}

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)
