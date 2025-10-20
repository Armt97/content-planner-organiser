# app.py
# Visiona Content Planner — Flask app
# NOTE: Comments are written to demonstrate understanding of structure, choices, and flow.

import os
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

# Flask core + helpers
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

# Background jobs + email + env
from apscheduler.schedulers.background import BackgroundScheduler
from flask_mail import Mail, Message
from dotenv import load_dotenv

# ORM models (SQLAlchemy)
from backend.models import db, User, Content, LibraryItem


# -----------------------------
# Paths / App / Database setup
# -----------------------------
# Resolve base paths for templates/static and DB file location.
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATES = os.path.join(BASE_DIR, "frontend")
STATIC = os.path.join(BASE_DIR, "frontend", "static")

# Pin the database to backend/visiona.db to keep runtime data out of repo root.
BASE_BACKEND = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_BACKEND, "visiona.db")

# Create the Flask app and point it at our frontend folders.
app = Flask(__name__, template_folder=TEMPLATES, static_folder=STATIC)

# Load environment variables from backend/.env (SMTP creds, etc.)
DOTENV_PATH = os.path.join(BASE_BACKEND, ".env")  # BASE_BACKEND already defined
load_dotenv(DOTENV_PATH)

# --- Flask-Mail config ---
# Pulls email server settings from .env; defaults are safe no-ops for local dev.
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
# Default sender falls back to MAIL_USERNAME if not set explicitly.
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", app.config.get("MAIL_USERNAME", "")
)

mail = Mail(app)  # Initialize Flask-Mail with the app.

# Core Flask/SQLAlchemy config. SECRET_KEY should be rotated in production.
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Attach SQLAlchemy to the app.
db.init_app(app)

# Ensure the DB directory exists and create tables if missing.
os.makedirs(BASE_BACKEND, exist_ok=True)
with app.app_context():
    db.create_all()


# -----------------------------
# Login / Session
# -----------------------------
# Configure Flask-Login (session management and @login_required).
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"  # If unauthenticated, redirect to home.
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login callback: load a user instance given the stored user_id."""
    try:
        # Using session.get to avoid full query + handles missing rows gracefully.
        return db.session.get(User, int(user_id))
    except Exception:
        # Returning None signals "no user"; prevents server error if bad cookie.
        return None


# -----------------------------
# Image uploads
# -----------------------------
# Store uploaded images under frontend/static/uploads for direct serving.
UPLOAD_FOLDER = os.path.join(STATIC, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Restrict uploads to common image types.
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename: str) -> bool:
    """True if the file has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/api/upload-image", methods=["POST"])
@login_required
def upload_image():
    """
    Accepts a multipart-encoded file under "file", saves with a UUID prefix
    to avoid collisions, and returns a static URL for the frontend to render.
    """
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify(ok=False, message="No file selected."), 400
    if not allowed_file(file.filename):
        return jsonify(ok=False, message="Invalid file type."), 400

    # Secure the filename and prefix with UUID to avoid path traversal/collisions.
    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    # Use url_for(static, ...) so the frontend can reference directly.
    file_url = url_for("static", filename=f"uploads/{filename}", _external=False)
    return jsonify(ok=True, url=file_url)


# -----------------------------
# Auth: register / login / logout
# -----------------------------
@app.route("/register", methods=["POST"])
def register():
    """
    Minimal registration: validates inputs, ensures email uniqueness,
    hashes password via model method, then logs the user in.
    """
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    # Basic form validation.
    if not name or not email or not password:
        return jsonify(ok=False, message="Please fill name, email, and password.")
    # Lightweight email sanity check (not exhaustive).
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify(ok=False, message="Please enter a valid email address.")
    # Check if the email already exists in the system.
    if User.query.filter_by(email=email).first():
        return jsonify(ok=False, message="An account with that email already exists.")

    # Create user + hash password through model helper.
    u = User(name=name, email=email)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()

    # Auto-login after successful registration.
    login_user(u)
    return jsonify(ok=True, message="Account created!", redirect=url_for("idea_board"))

@app.route("/login", methods=["POST"])
def login():
    """
    Simple name+password login. Uses werkzeug's check_password_hash against
    the stored password_hash on the user record.
    """
    # Keeps your original "name + password" flow
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    if not name or not password:
        return jsonify(ok=False, message="Please fill in both name and password.")

    # Authenticate by name; could be swapped to email if desired.
    user = User.query.filter_by(name=name).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(ok=False, message="Invalid name or password.")

    login_user(user)
    return jsonify(ok=True, redirect=url_for("idea_board"))

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    """Ends the session for the current user."""
    logout_user()
    return jsonify(ok=True, redirect=url_for("home"))


# -----------------------------
# Health / Home / Pages
# -----------------------------
@app.route("/health")
def health():
    """Lightweight health endpoint for probes/diagnostics."""
    return {"status": "ok"}

@app.route("/")
def home():
    """Landing page (public)."""
    return render_template("index.html")

@app.route("/idea-board")
@login_required
def idea_board():
    """Main board for creating and managing ideas (requires auth)."""
    return render_template("idea-board.html")

@app.route("/calendar")
@login_required
def calendar():
    """Calendar view for scheduled/posted content (requires auth)."""
    return render_template("calendar.html")

@app.route("/library")
@login_required
def library():
    """Content library page (renamed route name to match url_for('library'))."""
    # <— renamed to 'library' to match templates using url_for('library')
    return render_template("library.html")

@app.route("/insights")
@login_required
def insights():
    """Insights/analytics dashboard (requires auth)."""
    return render_template("insights.html")


# -----------------------------
# Helpers
# -----------------------------
def parse_scheduled_any(s: str):
    """
    Parse common datetime formats into a *naive UTC* datetime.
    Returns None if empty/unparseable.
    Supported:
      - ISO-8601 with 'Z' or offsets (e.g., 2025-10-20T12:00:00Z)
      - 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM AM/PM'
    """
    s = (s or "").strip()
    if not s:
        return None

    # 1) ISO-8601 (…Z or with offset). Normalize 'Z' → '+00:00' for fromisoformat.
    try:
        iso = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(iso)
        # Convert aware datetimes to UTC and strip tzinfo (store as naive UTC).
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        pass

    # 2) Fallbacks: very common local text formats.
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %I:%M %p"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    return None  # Unknown format: caller handles validation


# -----------------------------
# Library API
# -----------------------------
@app.route("/api/library", methods=["GET"])
@login_required
def api_list_library():
    """
    Return the caller's library items ordered by newest first.
    Only the current user's data is visible.
    """
    items = (
        LibraryItem.query
        .filter_by(user_id=current_user.id)
        .order_by(LibraryItem.id.desc())
        .all()
    )
    # Serialize to a compact dictionary for the frontend.
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
    """
    Create a new library item. Title is required.
    Accepts JSON or form-encoded data.
    """
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
    """
    Soft-authorization by scoping the query to the current_user.id.
    If not found (wrong user or missing), return 404.
    """
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
    """
    List ideas for the current user (newest first). Timestamps are returned as
    ISO-8601 'Z' strings (UTC) when present, else null.
    """
    ideas = (
        Content.query
        .filter_by(user_id=current_user.id)
        .order_by(Content.id.desc())
        .all()
    )
    data = []
    for i in ideas:
        if i.scheduled_time:
            # Convert naive UTC datetime → explicit UTC ISO string with trailing 'Z'.
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
    Create an idea. Title required; platform optional (defaults to 'General').
    scheduled_time is OPTIONAL (can be null for raw ideas). Accepts JSON or form.
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

    # Parse scheduled_time if provided; OK for ideas to be unscheduled (None).
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
        # Roll back on any DB error and surface a concise message.
        db.session.rollback()
        return jsonify(ok=False, message=f"DB error: {type(e).__name__}: {e}"), 500

@app.route("/api/ideas/<int:idea_id>", methods=["DELETE"])
@login_required
def api_delete_idea(idea_id):
    """
    Delete an idea owned by the current user. Returns 404 if not found or not owned.
    """
    idea = Content.query.filter_by(id=idea_id, user_id=current_user.id).first()
    if not idea:
        return jsonify(ok=False, message="Idea not found."), 404
    db.session.delete(idea)
    db.session.commit()
    return jsonify(ok=True, message="Idea removed.")

@app.route("/api/ideas/<int:idea_id>", methods=["PATCH"])
@login_required
def api_update_idea(idea_id):
    """
    Partial update of an idea. Only provided keys are changed.
    Includes validation on title/platform emptiness and status whitelist.
    """
    idea = Content.query.filter_by(id=idea_id, user_id=current_user.id).first()
    if not idea:
        return jsonify(ok=False, message="Idea not found."), 404

    payload = request.get_json(silent=True) or request.form

    def norm(key):
        """
        Normalize incoming values:
          - If key absent → None (means "leave unchanged").
          - If present → convert to string and strip spaces (keeps empty string if sent).
        """
        v = payload.get(key)
        return (v if v is None else str(v)).strip() if v is not None else None

    title         = norm("title")
    platform      = norm("platform")
    scheduled     = norm("scheduled_time")
    status        = norm("status")
    details       = norm("details")
    thumbnail_url = norm("thumbnail_url")

    # Apply field-by-field updates with validation.
    if title is not None:
        if not title:
            return jsonify(ok=False, message="Title cannot be empty."), 400
        idea.title = title
    if platform is not None:
        if not platform:
            return jsonify(ok=False, message="Platform cannot be empty."), 400
        idea.platform = platform
    if scheduled is not None:
        # Accept "" as a request to clear the scheduled_time (set to None).
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
    """
    Expose events for the calendar view. Show only Scheduled + Posted items,
    ordered chronologically by scheduled_time. Items without scheduled_time are skipped.
    """
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
        # Convert to ISO 'Z' for FullCalendar consumption on the frontend.
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
    Ensure the 'created_at' column exists and backfill it (safe to re-run).
    This avoids NULLs when deriving "idea → posted" timing metrics later.
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
    """
    Normalize a datetime down to Monday 00:00:00 of its week.
    Used to aggregate weekly posting counts.
    """
    d = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return d - timedelta(days=d.weekday())  # Monday

@app.route("/api/insights", methods=["GET"])
@login_required
def api_insights():
    """
    Compute lightweight analytics:
      - Weekly posting counts (8 weeks)
      - Platform breakdown (last 30 days)
      - Average days from idea creation to posting
      - Simple suggestions based on trends
    """
    items = Content.query.filter(Content.user_id == current_user.id).all()

    now = datetime.utcnow()
    weeks_back = 8
    window_start = (now - timedelta(weeks=weeks_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    last_30_days = now - timedelta(days=30)

    # Treat Posted as posts; use scheduled_time if present else created_at.
    def post_dt(it: Content):
        """
        Returns the datetime consider as the 'post moment':
          - Posted → first try scheduled_time, else created_at
          - Scheduled → scheduled_time
          - Others → None (ignored for posting metrics)
        """
        if it.status == "Posted":
            return it.scheduled_time or getattr(it, "created_at", None)
        if it.status == "Scheduled":
            return it.scheduled_time
        return None

    # Aggregate counts per week and per weekday in the analysis window.
    week_counts = Counter()
    weekday_counts = Counter()
    for it in items:
        dt = post_dt(it)
        if isinstance(dt, datetime) and dt >= window_start:
            wk = _week_floor(dt)
            week_counts[wk] += 1
            weekday_counts[dt.weekday()] += 1

    # Build a continuous weekly series (even if some weeks have 0).
    series = []
    for w in range(weeks_back):
        ws = _week_floor(now - timedelta(weeks=(weeks_back - 1 - w)))
        series.append({"week_start": ws.isoformat(), "count": int(week_counts[ws])})

    # Compare this week vs last week to drive a suggestion.
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

    # Convert counters to sorted list with percentages (1 dp).
    platform = []
    for name, cnt in platform_counter.most_common():
        pct = (cnt / total_platform * 100.0) if total_platform else 0.0
        platform.append({"platform": name, "count": int(cnt), "percent": round(pct, 1)})

    # Avg time idea -> post (in days), ignoring negatives and missing timestamps.
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

    # Suggestions: simple heuristics to nudge behavior.
    suggestions = []
    if delta < 0:
        suggestions.append("Your posting volume is down versus last week. Try batching two quick posts to catch up.")
    elif delta == 0 and this_week_count < 3:
        suggestions.append("Steady week. Consider scheduling 1–2 more posts to keep momentum.")
    if sum(weekday_counts.values()) >= 6:
        top_wd, _ = max(weekday_counts.items(), key=lambda kv: kv[1])
        if top_wd >= 4:  # 0=Mon ... 6=Sun → 4/5/6 are Fri/Sat/Sun
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

@app.route("/migrate/add-reminders-enabled")
def migrate_add_reminders_enabled():
    """
    Migration endpoint to add a 'reminders_enabled' boolean to the user table
    with default TRUE. Safe to call multiple times.
    """
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    cols = [c["name"] for c in insp.get_columns("user")]
    with db.engine.begin() as conn:
        if "reminders_enabled" not in cols:
            conn.execute(text("ALTER TABLE user ADD COLUMN reminders_enabled BOOLEAN DEFAULT 1"))
    return {"ok": True, "message": "reminders_enabled ensured (default TRUE)"}

def _mail_is_configured():
    """
    Quick guard: True if core mail settings exist. Prevents attempts to send
    without configuration (useful during local dev).
    """
    return bool(app.config.get("MAIL_SERVER") and
                app.config.get("MAIL_USERNAME") and
                app.config.get("MAIL_DEFAULT_SENDER"))

def send_reminders_job():
    """
    Background job (scheduled every 15 minutes):
    Sends email reminders for items 'Scheduled' within the next 24 hours.
    Groups by user to send a single digest email per user per run.
    """
    if not _mail_is_configured():
        app.logger.info("[reminders] Mail not configured; skipping send.")
        return

    # Ensure have an app context before hitting the DB or mail.
    with app.app_context():
        now = datetime.utcnow()
        window_end = now + timedelta(hours=24)

        # Fetch upcoming scheduled content within the next 24 hours.
        upcoming = (
            Content.query
            .filter(Content.status == "Scheduled")
            .filter(Content.scheduled_time != None)
            .filter(Content.scheduled_time >= now)
            .filter(Content.scheduled_time <= window_end)
            .order_by(Content.user_id.asc(), Content.scheduled_time.asc())
            .all()
        )

        # Group items by user_id for per-user emails.
        by_user = {}
        for c in upcoming:
            by_user.setdefault(c.user_id, []).append(c)

        for user_id, items in by_user.items():
            user = db.session.get(User, user_id)
            # Skip if user missing, no email, or opted out of reminders.
            if not user or not user.email or not getattr(user, "reminders_enabled", True):
                continue

            # Build a simple plain-text digest.
            lines = []
            lines.append("Heads up! You have posts scheduled in the next 24 hours:\n")
            for it in items:
                # Use UTC Z format for clarity; frontend can localize if needed.
                when_local = it.scheduled_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                lines.append(f"- {it.title} ({it.platform}) at {when_local}")
            lines.append("\nOpen Visiona → Calendar to review or adjust.\n")

            body = "\n".join(lines)

            try:
                msg = Message(
                    subject="Visiona Reminder: Upcoming scheduled posts",
                    recipients=[user.email],
                    body=body
                )
                mail.send(msg)
                app.logger.info(f"[reminders] Sent to {user.email} ({len(items)} items)")
            except Exception as e:
                # Log and continue; don't crash the scheduler on a single failure.
                app.logger.exception(f"[reminders] Failed to send to {user.email}: {e}")

# Start APScheduler (every 15 minutes)
# Run as a daemon so it doesn't block Flask shutdown in dev environments.
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=send_reminders_job, trigger="interval", minutes=15, id="visiona_reminders")
scheduler.start()

@app.route("/api/reminders/test", methods=["POST"])
@login_required
def reminders_test():
    """
    Manually trigger a reminder email to the current user showing up to 5
    upcoming scheduled posts. Helpful for validating SMTP configuration.
    """
    if not _mail_is_configured():
        return jsonify(ok=False, message="Mail not configured (.env missing or invalid)."), 400

    upcoming = (
        Content.query
        .filter(Content.user_id == current_user.id)
        .filter(Content.status == "Scheduled")
        .filter(Content.scheduled_time != None)
        .filter(Content.scheduled_time >= datetime.utcnow())
        .order_by(Content.scheduled_time.asc())
        .limit(5)
        .all()
    )

    # Build body depending on whether results exist.
    if not upcoming:
        body = "No upcoming scheduled posts found for the next 24h. Add one and try again."
    else:
        lines = ["Your next scheduled posts:\n"]
        for it in upcoming:
            when_local = it.scheduled_time.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
            lines.append(f"- {it.title} ({it.platform}) at {when_local}")
        body = "\n".join(lines)

    try:
        msg = Message(
            subject="Visiona Test: Reminder email",
            recipients=[current_user.email],
            body=body
        )
        mail.send(msg)
        return jsonify(ok=True, message=f"Sent test reminder to {current_user.email}")
    except Exception as e:
        # Surface a simple message; details appear in server logs.
        return jsonify(ok=False, message=f"Send failed: {type(e).__name__}: {e}")

@app.route("/api/test-email", methods=["GET"])
@login_required
def test_email():
    """
    Send a quick "hello" email to the current user to verify mail setup.
    """
    if not _mail_is_configured():
        return jsonify(ok=False, message="Mail not configured (.env missing or invalid)."), 400
    try:
        msg = Message(
            subject="Visiona Test Email",
            recipients=[current_user.email],  # sends to the logged-in user
            body="Hi! This is a test email from your Visiona app. If you see this, Flask-Mail works ✅"
        )
        mail.send(msg)
        return jsonify(ok=True, message=f"Test email sent to {current_user.email}")
    except Exception as e:
        return jsonify(ok=False, message=f"Send failed: {type(e).__name__}: {e}"), 500


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    # Debug server bound to localhost:5001.
    # TIP: In production, run via gunicorn/uvicorn behind a reverse proxy.
    app.run(debug=True, host="127.0.0.1", port=5001)
