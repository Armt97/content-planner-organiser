# app.py
import os
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from backend.models import db, User, Content, LibraryItem


# -----------------------------
# Paths / App / Database setup
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES = os.path.join(BASE_DIR, "frontend")
STATIC = os.path.join(BASE_DIR, "frontend", "static")

# Pin the database to backend/visiona.db
BASE_BACKEND = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_BACKEND, "visiona.db")

app = Flask(__name__, template_folder=TEMPLATES, static_folder=STATIC)
app.config["SECRET_KEY"] = "dev-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Ensure DB file/folders exist and tables are created
os.makedirs(BASE_BACKEND, exist_ok=True)
with app.app_context():
    db.create_all()


# -----------------------------
# Login / Session
# -----------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


# -----------------------------
# Image uploads
# -----------------------------
UPLOAD_FOLDER = os.path.join(STATIC, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename: str) -> bool:
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

    file_url = url_for("static", filename=f"uploads/{filename}", _external=False)
    return jsonify(ok=True, url=file_url)


# -----------------------------
# Auth: register / login / logout
# -----------------------------
@app.route("/register", methods=["POST"])
def register():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not name or not email or not password:
        return jsonify(ok=False, message="Please fill name, email, and password.")
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify(ok=False, message="Please enter a valid email address.")
    if User.query.filter_by(email=email).first():
        return jsonify(ok=False, message="An account with that email already exists.")

    u = User(name=name, email=email)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()

    login_user(u)
    return jsonify(ok=True, message="Account created!", redirect=url_for("idea_board"))

@app.route("/login", methods=["POST"])
def login():
    # Keeps your original "name + password" flow
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    if not name or not password:
        return jsonify(ok=False, message="Please fill in both name and password.")

    user = User.query.filter_by(name=name).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(ok=False, message="Invalid name or password.")

    login_user(user)
    return jsonify(ok=True, redirect=url_for("idea_board"))

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify(ok=True, redirect=url_for("home"))


# -----------------------------
# Health / Home / Pages
# -----------------------------
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
@login_required
def library():
    # <— renamed to 'library' to match templates using url_for('library')
    return render_template("library.html")

@app.route("/insights")
@login_required
def insights():
    return render_template("insights.html")


# -----------------------------
# Helpers
# -----------------------------
def parse_scheduled_any(s: str):
    """Parse many time formats → naive UTC datetime (or None)."""
    s = (s or "").strip()
    if not s:
        return None

    # 1) ISO-8601 (…Z or with offset)
    try:
        iso = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        pass

    # 2) Common fallbacks
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    return None


# -----------------------------
# Library API
# -----------------------------
@app.route("/api/library", methods=["GET"])
@login_required
def api_list_library():
    items = (
        LibraryItem.query
        .filter_by(user_id=current_user.id)
        .order_by(LibraryItem.id.desc())
        .all()
    )
    data = [{
        "id": i.id,
        "title": i.title,
        "caption": i.caption or "",
        "hashtags": i.hashtags or "",
        "category": i.category or "",
    } for i in items]
    return jsonify(ok=True, items=data)

@app.route("/api/library", methods=["POST"])
@login_required
def api_add_library():
    payload = request.get_json(silent=True) or request.form
    title = (payload.get("title") or "").strip()
    caption = (payload.get("caption") or "").strip()
    hashtags = (payload.get("hashtags") or "").strip()
    category = (payload.get("category") or "").strip()

    if not title:
        return jsonify(ok=False, message="Title is required"), 400

    item = LibraryItem(
        user_id=current_user.id,
        title=title,
        caption=caption,
        hashtags=hashtags,
        category=category
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(ok=True, id=item.id, message="Saved")

@app.route("/api/library/<int:item_id>", methods=["DELETE"])
@login_required
def api_delete_library(item_id):
    item = LibraryItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        return jsonify(ok=False, message="Not found"), 404
    db.session.delete(item)
    db.session.commit()
    return jsonify(ok=True, message="Deleted")


# -----------------------------
# Ideas API
# -----------------------------
@app.route("/api/ideas", methods=["GET"])
@login_required
def api_list_ideas():
    ideas = (
        Content.query
        .filter_by(user_id=current_user.id)
        .order_by(Content.id.desc())
        .all()
    )
    data = []
    for i in ideas:
        if i.scheduled_time:
            utc_iso_z = (
                i.scheduled_time.replace(tzinfo=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        else:
            utc_iso_z = None

        data.append({
            "id": i.id,
            "title": i.title,
            "platform": i.platform,
            "scheduled_time": utc_iso_z,        # can be null
            "status": i.status,
            "details": i.details or "",
            "thumbnail_url": i.thumbnail_url or ""
        })
    return jsonify(ok=True, items=data)

@app.route("/api/ideas", methods=["POST"])
@login_required
def api_create_idea():
    """
    Create an idea. Title required; platform optional (defaults to 'General');
    scheduled_time is OPTIONAL (can be null for raw ideas).
    """
    payload = request.get_json(silent=True) or request.form

    title        = (payload.get("title") or "").strip()
    platform     = (payload.get("platform") or "General").strip()
    scheduled    = (payload.get("scheduled_time") or "").strip()
    status       = (payload.get("status") or "Idea").strip() or "Idea"
    details      = (payload.get("details") or "").strip()
    thumbnail_url = (payload.get("thumbnail_url") or "").strip()

    if not title:
        return jsonify(ok=False, message="Title is required"), 400

    scheduled_dt = parse_scheduled_any(scheduled) if scheduled else None

    try:
        item = Content(
            title=title,
            platform=platform,
            scheduled_time=scheduled_dt,     # can be None
            status=status,
            details=details,
            thumbnail_url=thumbnail_url,
            user_id=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        return jsonify(ok=True, message="Idea created.", id=item.id)
    except Exception as e:
        db.session.rollback()
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

    title         = norm("title")
    platform      = norm("platform")
    scheduled     = norm("scheduled_time")
    status        = norm("status")
    details       = norm("details")
    thumbnail_url = norm("thumbnail_url")

    if title is not None:
        if not title:
            return jsonify(ok=False, message="Title cannot be empty."), 400
        idea.title = title
    if platform is not None:
        if not platform:
            return jsonify(ok=False, message="Platform cannot be empty."), 400
        idea.platform = platform
    if scheduled is not None:
        dt = parse_scheduled_any(scheduled)
        if scheduled != "" and not dt:
            return jsonify(ok=False, message=f"Invalid scheduled_time: {scheduled}"), 400
        idea.scheduled_time = dt  # allow clearing by sending ""
    if status is not None:
        valid = {"Idea", "In Progress", "Scheduled", "Posted"}
        if status not in valid:
            return jsonify(ok=False, message="Invalid status."), 400
        idea.status = status
    if details is not None:
        idea.details = details
    if thumbnail_url is not None:
        idea.thumbnail_url = thumbnail_url

    db.session.commit()
    return jsonify(ok=True, message="Idea updated.")


# -----------------------------
# Calendar Events API
# -----------------------------
@app.route("/api/calendar-events", methods=["GET"])
@login_required
def api_calendar_events():
    # Show Scheduled + Posted on the calendar.
    ideas = (
        Content.query
        .filter(
            Content.user_id == current_user.id,
            Content.status.in_(["Scheduled", "Posted"])
        )
        .order_by(Content.scheduled_time.asc())
        .all()
    )

    events = []
    for i in ideas:
        if not i.scheduled_time:
            # If a Posted item has no scheduled_time, skip it for the calendar.
            continue
        utc_iso_z = (
            i.scheduled_time.replace(tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        events.append({
            "id": i.id,
            "title": i.title,
            "start": utc_iso_z,
            "extendedProps": {
                "platform": i.platform,
                "status": i.status,
                "thumbnail_url": (i.thumbnail_url or ""),
                "details": (i.details or "")
            }
        })
    return jsonify(ok=True, events=events)


# -----------------------------
# Tiny one-time migration helper
# -----------------------------
@app.route("/migrate/add-created-at")
def migrate_add_created_at():
    """
    Ensure the 'created_at' column exists and backfill it.
    Safe to re-run.
    """
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns("content")]
    with db.engine.begin() as conn:
        if "created_at" not in cols:
            conn.execute(text("ALTER TABLE content ADD COLUMN created_at TIMESTAMP"))
            conn.execute(text("UPDATE content SET created_at = COALESCE(created_at, scheduled_time)"))
    return {"ok": True, "message": "created_at ensured/backfilled"}


# -----------------------------
# Insights API (for insights.html)
# -----------------------------
def _week_floor(dt: datetime) -> datetime:
    d = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return d - timedelta(days=d.weekday())  # Monday

@app.route("/api/insights", methods=["GET"])
@login_required
def api_insights():
    items = Content.query.filter(Content.user_id == current_user.id).all()

    now = datetime.utcnow()
    weeks_back = 8
    window_start = (now - timedelta(weeks=weeks_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    last_30_days = now - timedelta(days=30)

    # Treat Posted as posts; use scheduled_time if present else created_at.
    def post_dt(it: Content):
        if it.status == "Posted":
            return it.scheduled_time or getattr(it, "created_at", None)
        if it.status == "Scheduled":
            return it.scheduled_time
        return None

    week_counts = Counter()
    weekday_counts = Counter()
    for it in items:
        dt = post_dt(it)
        if isinstance(dt, datetime) and dt >= window_start:
            wk = _week_floor(dt)
            week_counts[wk] += 1
            weekday_counts[dt.weekday()] += 1

    series = []
    for w in range(weeks_back):
        ws = _week_floor(now - timedelta(weeks=(weeks_back - 1 - w)))
        series.append({"week_start": ws.isoformat(), "count": int(week_counts[ws])})

    this_week = _week_floor(now)
    last_week = this_week - timedelta(weeks=1)
    this_week_count = int(week_counts[this_week])
    last_week_count = int(week_counts[last_week])
    delta = this_week_count - last_week_count

    # Platform breakdown (last 30 days)
    platform_counter = Counter()
    total_platform = 0
    for it in items:
        dt = post_dt(it)
        if isinstance(dt, datetime) and dt >= last_30_days:
            platform_counter[(it.platform or "Other").strip() or "Other"] += 1
            total_platform += 1

    platform = []
    for name, cnt in platform_counter.most_common():
        pct = (cnt / total_platform * 100.0) if total_platform else 0.0
        platform.append({"platform": name, "count": int(cnt), "percent": round(pct, 1)})

    # Avg time idea -> post
    deltas = []
    for it in items:
        if it.status == "Posted":
            posted = post_dt(it)
            created = getattr(it, "created_at", None)
            if isinstance(posted, datetime) and isinstance(created, datetime):
                days = (posted - created).total_seconds() / 86400.0
                if days >= 0:
                    deltas.append(days)
    avg_days = round(sum(deltas) / len(deltas), 2) if deltas else None

    # Suggestions
    suggestions = []
    if delta < 0:
        suggestions.append("Your posting volume is down versus last week. Try batching two quick posts to catch up.")
    elif delta == 0 and this_week_count < 3:
        suggestions.append("Steady week. Consider scheduling 1–2 more posts to keep momentum.")
    if sum(weekday_counts.values()) >= 6:
        top_wd, _ = max(weekday_counts.items(), key=lambda kv: kv[1])
        if top_wd >= 4:  # Fri/Sat/Sun
            suggestions.append("Most of your posts cluster late in the week. Try scheduling more Mon–Wed.")
    if platform:
        top = platform[0]
        if top["percent"] >= 70 and len(platform) >= 2:
            suggestions.append(f"You rely heavily on {top['platform']}. Consider reusing content on other platforms.")
    if avg_days is not None and avg_days < 1.0:
        suggestions.append("You often post within 24 hours of ideation. Try drafting earlier to avoid last-minute rush.")

    return jsonify(ok=True, data={
        "week_summary": {
            "this_week": this_week_count,
            "last_week": last_week_count,
            "delta": delta
        },
        "weekly_series": series,
        "platform_breakdown": platform,
        "avg_idea_to_post_days": avg_days,
        "suggestions": suggestions
    })


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)
