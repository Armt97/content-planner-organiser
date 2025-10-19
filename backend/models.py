from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    contents = db.relationship("Content", backref="user", lazy=True)

    def __repr__(self):
      return f"<User {self.email}>"

    def set_password(self, password):
      self.password_hash = generate_password_hash(password)

    def check_password(self, password):
      return check_password_hash(self.password_hash, password)


class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    platform = db.Column(db.String(50), nullable=False)   # e.g. Instagram, TikTok
    scheduled_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Idea")
    details = db.Column(db.Text, nullable=True, default="")
    thumbnail_url = db.Column(db.Text)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    def __repr__(self):
      return f"<Content {self.title} on {self.platform}>"

class LibraryItem(db.Model):
    __tablename__ = "library_items"
    id = db.Column(db.Integer, primary_key=True)
    # fix FK target to match your existing 'user' table name
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(100), nullable=False)        # e.g. “Summer Campaign”
    caption = db.Column(db.Text, nullable=True)              # main text
    hashtags = db.Column(db.Text, nullable=True)             # e.g. "#summer #travel"
    category = db.Column(db.String(50), nullable=True)       # optional
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<LibraryItem {self.title}>"

# (optional but recommended) add a relationship on User
User.library_items = db.relationship(
    "LibraryItem",
    backref="user",
    lazy=True,
    cascade="all, delete-orphan"
)
