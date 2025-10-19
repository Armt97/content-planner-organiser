from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import os
from datetime import datetime, timezone
import uuid
from werkzeug.utils import secure_filename
from backend.models import db, User, Content

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES = os.path.join(BASE_DIR, "frontend")
STATIC = os.path.join(BASE_DIR, "frontend", "static")

# --- Pin the database to backend/visiona.db ---
BASE_BACKEND = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_BACKEND, "visiona.db")

app = Flask(__name__, template_folder=TEMPLATES, static_folder=STATIC)

app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# --- Flask-Login setup (place this immediately after db.init_app(app)) ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"          # where to redirect unauthenticated users
login_manager.login_message_category = "info"

# --- Image uploads config ---
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = os.path.join(STATIC, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/api/upload-image", methods=["POST"])
@login_required
def upload_image():
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify(ok=False, message="No file selected."), 400
    if not allowed_file(file.filename):
        return jsonify(ok=False, message="Invalid file type."), 400

    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    # Return URL to access image
    file_url = url_for("static", filename=f"uploads/{filename}", _external=False)
    return jsonify(ok=True, url=file_url)

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
    return jsonify(ok=True, redirect=url_for("idea_board"))

@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify(ok=True, redirect=url_for("home"))

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

@app.route("/api/ideas", methods=["GET"])
@login_required
def api_list_ideas():
    ideas = (Content.query
             .filter_by(user_id=current_user.id)
             .order_by(Content.id.desc())
             .all())
    data = []
    for i in ideas:
        utc_iso_z = i.scheduled_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        data.append({
            "id": i.id,
            "title": i.title,
            "platform": i.platform,
            "scheduled_time": utc_iso_z,
            "status": i.status,
            "details": i.details or "",
            "thumbnail_url": i.thumbnail_url or ""
        })
    return jsonify(ok=True, items=data)

@app.route("/api/ideas", methods=["POST"])
@login_required
def api_create_idea():
    # accept JSON or form
    payload = request.get_json(silent=True) or request.form

    title     = (payload.get("title") or "").strip()
    platform  = (payload.get("platform") or "").strip()
    scheduled = (payload.get("scheduled_time") or "").strip()
    status    = (payload.get("status") or "Idea").strip()
    details   = (payload.get("details") or "").strip()
    thumbnail_url = (payload.get("thumbnail_url") or "").strip()

    if not title or not platform or not scheduled:
        return jsonify(ok=False, message="Missing: title, platform, or scheduled_time"), 400

    scheduled_dt = parse_scheduled_any(scheduled)
    if not scheduled_dt:
        return jsonify(ok=False, message=f"Invalid scheduled_time: {scheduled}"), 400

    try:
        item = Content(
            title=title,
            platform=platform,
            scheduled_time=scheduled_dt,
            status=status,
            details=details,
            thumbnail_url=thumbnail_url,
            user_id=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(ok=True, message="Idea created.", id=item.id)
    except Exception as e:
        # temporary debug detail; remove once fixed
        return jsonify(ok=False, message=f"DB error: {type(e).__name__}: {e}"), 500

@app.route("/api/ideas/<int:idea_id>", methods=["DELETE"])
@login_required
def api_delete_idea(idea_id):
    idea = Content.query.filter_by(id=idea_id, user_id=current_user.id).first()
    if not idea:
        return jsonify(ok=False, message="Idea not found."), 404
    db.session.delete(idea)
    db.session.commit()
    return jsonify(ok=True, message="Idea removed.")

@app.route("/api/ideas/<int:idea_id>", methods=["PATCH"])
@login_required
def api_update_idea(idea_id):
    idea = Content.query.filter_by(id=idea_id, user_id=current_user.id).first()
    if not idea:
        return jsonify(ok=False, message="Idea not found."), 404

    payload = request.get_json(silent=True) or request.form

    def norm(key):
        v = payload.get(key)
        return (v if v is None else str(v)).strip() if v is not None else None

    title     = norm("title")
    platform  = norm("platform")
    scheduled = norm("scheduled_time")
    status    = norm("status")
    details   = norm("details")
    thumbnail_url = norm("thumbnail_url")

    if title is not None:
        if not title: return jsonify(ok=False, message="Title cannot be empty."), 400
        idea.title = title
    if platform is not None:
        if not platform: return jsonify(ok=False, message="Platform cannot be empty."), 400
        idea.platform = platform
    if scheduled is not None:
        dt = parse_scheduled_any(scheduled)
        if not dt: return jsonify(ok=False, message=f"Invalid scheduled_time: {scheduled}"), 400
        idea.scheduled_time = dt
    if status is not None:
        valid = {"Idea", "In Progress", "Scheduled", "Posted"}
        if status not in valid: return jsonify(ok=False, message="Invalid status."), 400
        idea.status = status
    if details is not None:
        idea.details = details
    if thumbnail_url is not None:  # ← ADD THIS
        idea.thumbnail_url = thumbnail_url

    db.session.commit()
    return jsonify(ok=True, message="Idea updated.")

from datetime import datetime, timezone

def parse_scheduled_any(s: str):
    s = (s or "").strip()
    if not s:
        return None

    # 1) Try ISO-8601 (handles ...Z and ...+13:00, etc.)
    try:
        iso = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(iso)
        # store naive UTC in DB to avoid tz-aware issues with SQLite
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        pass

    # 2) Fallbacks: 24h and 12h with AM/PM
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    return None

@app.route("/api/calendar-events", methods=["GET"])
@login_required
def api_calendar_events():
    # Only show Scheduled + Posted on the calendar
    ideas = (Content.query
             .filter(Content.user_id == current_user.id,
                     Content.status.in_(["Scheduled", "Posted"]))
             .order_by(Content.scheduled_time.asc())
             .all())

    events = []
    for i in ideas:
        utc_iso_z = i.scheduled_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        events.append({
            "id": i.id,
            "title": i.title,
            "start": utc_iso_z,
            # pass extras for rendering
            "extendedProps": {
                "platform": i.platform,
                "status": i.status,
                "thumbnail_url": (i.thumbnail_url or ""),
                "details": (i.details or "")
            }
        })
    return jsonify(ok=True, events=events)

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)
