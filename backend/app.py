from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
import os
from models import db, User  # make sure this import exists at the top
from flask_login import login_user  # also ensure imported

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES = os.path.join(BASE_DIR, "frontend")
STATIC = os.path.join(BASE_DIR, "frontend", "static")

app = Flask(__name__, template_folder=TEMPLATES, static_folder=STATIC)

app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///visiona.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# --- Flask-Login setup (place this immediately after db.init_app(app)) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"          # where to redirect unauthenticated users
login_manager.login_message_category = "info"

@app.route("/register", methods=["POST"])
def register():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    # basic validation
    if not name or not email or not password:
        return jsonify(ok=False, message="Please fill name, email, and password.")

    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify(ok=False, message="Please enter a valid email address.")

    # uniqueness check
    if User.query.filter_by(email=email).first():
        return jsonify(ok=False, message="An account with that email already exists.")

    # create user
    u = User(name=name, email=email)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()

    # log them in
    login_user(u)

    # redirect to a protected page they now can access
    return jsonify(ok=True, message="Account created!", redirect=url_for("idea_board"))

@app.route("/login", methods=["POST"])
def login():
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""

    if not name or not password:
        return jsonify(ok=False, message="Please fill in both name and password.")

    user = User.query.filter_by(name=name).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(ok=False, message="Invalid name or password.")

    login_user(user)
    return jsonify(ok=True, message=f"Welcome back, {user.name}!", redirect=url_for("idea_board"))

@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/idea-board")
@login_required
def idea_board():
    return render_template("idea-board.html")

@app.route("/calendar")
@login_required
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
