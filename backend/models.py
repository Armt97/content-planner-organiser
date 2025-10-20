# backend/models.py
# SQLAlchemy models for Visiona Content Planner.
# Notes in comments explain schema choices, relationships, and constraints.

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Single SQLAlchemy instance shared across the app
db = SQLAlchemy()


class User(db.Model, UserMixin):
    """
    Application user:
      - Uses Flask-Login's UserMixin to integrate with session management.
      - Owns Content and LibraryItem rows via one-to-many relationships.
      - 'reminders_enabled' toggles email reminders without deleting the user.
    """
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)  # surrogate PK
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)  # uniqueness at DB level
    password_hash = db.Column(db.String(128), nullable=False)
    # Feature flag for email reminders; indexed/filtered in jobs; default ON.
    reminders_enabled = db.Column(db.Boolean, nullable=False, default=True)

    # --- Relationships ---
    # Backref 'user' lets a Content instance access its owner via content.user.
    contents = db.relationship("Content", backref="user", lazy=True)
    # Library items are considered user-owned content; delete-orphan ensures
    # removing a user will also remove their library items (no dangling rows).
    library_items = db.relationship(
        "LibraryItem",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.email}>"

    # Store only a hash, never the raw password.
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    # Convenience method for login checks; uses werkzeug's timing-safe compare.
    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Content(db.Model):
    """
    An idea/post card in the planner:
      - 'status' tracks lifecycle (Idea → In Progress → Scheduled → Posted).
      - 'scheduled_time' is optional; 'Posted' items may still have it set
        (used by calendar and insights).
      - 'created_at' is recorded to compute time-to-post metrics.
    """
    __tablename__ = "content"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    # Platform is free text (e.g., Instagram, TikTok). Consider enum if you need strict validation.
    platform = db.Column(db.String(50), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=True)  # naive UTC stored by app
    status = db.Column(db.String(50), nullable=False, default="Idea")
    details = db.Column(db.Text, nullable=True, default="")  # long-form notes
    thumbnail_url = db.Column(db.Text)  # optional media preview URL

    # When the card was created (UTC). Used for "avg idea -> post" analytics.
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # FK to owning user (required). No cascade here; user relationship controls deletion.
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    def __repr__(self):
        return f"<Content {self.title} on {self.platform}>"


class LibraryItem(db.Model):
    """
    Reusable content snippets/assets:
      - Title + optional caption/hashtags/category to help re-purpose content.
      - Belongs to a single user; orphaned rows are prevented via relationship cascade.
    """
    __tablename__ = "library_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # owner
    title = db.Column(db.String(100), nullable=False)        # e.g. “Summer Campaign”
    caption = db.Column(db.Text, nullable=True)              # long-form text
    hashtags = db.Column(db.Text, nullable=True)             # e.g. "#summer #travel"
    category = db.Column(db.String(50), nullable=True)       # optional tagging
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<LibraryItem {self.title}>"
