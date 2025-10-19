# tests/test_api.py
"""
Minimal backend API tests for Visiona.

Covers:
1) POST /api/ideas -> creates an idea
2) PATCH /api/ideas/:id -> updates status
3) Validation path: POST /api/ideas without a title -> 400

Notes:
- Disable the APScheduler job runner during tests so background tasks
  don't interfere with test runs.
- Each test resets the database to ensure isolation.
"""

import json
from datetime import datetime, timedelta, timezone
import os
import sys

# --- Make the project importable when running `pytest` from repo root ---
# Adds the repo root to sys.path so `from backend...` works.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Disable the scheduler for test runs (picked up in app.py) ---
os.environ["VISIONA_DISABLE_SCHEDULER"] = "1"

from backend.app import app, db  # noqa: E402  (imports after sys.path tweak)
from backend.models import User, Content  # noqa: E402


# ---------- Helper utilities ----------

def register(client, name: str, email: str, password: str):
    """
    Helper: call the /register endpoint.
    In the app, /register logs the new user in immediately on success,
    which is convenient for tests.
    """
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
    )


def login(client, name: str, password: str):
    """
    Helper: call the /login endpoint using the "name + password" flow.
    Not strictly needed when we register in the same test, but handy if you
    test login separately later.
    """
    return client.post("/login", data={"name": name, "password": password})


def iso_in(hours: int = 0) -> str:
    """
    Return an ISO-8601 UTC string with trailing 'Z' for (now + hours).

    We use timezone-aware datetimes to avoid deprecation warnings and to
    make it explicit that this time is in UTC.
    """
    dt = datetime.now(timezone.utc) + timedelta(hours=hours)
    # Convert to '...Z' form (instead of '+00:00') to match the app’s parser.
    return dt.isoformat().replace("+00:00", "Z")


def setup_clean_db():
    """
    Drop and re-create all tables for a clean slate.
    Each test calls this to ensure isolation and deterministic results.
    """
    with app.app_context():
        db.drop_all()
        db.create_all()


# ---------- Tests ----------

def test_post_idea_and_patch_status():
    """
    End-to-end happy path:
    - Register a user (auto-logged-in by /register)
    - POST /api/ideas -> create an idea scheduled 2 hours from now
    - PATCH /api/ideas/:id -> update status to 'Scheduled'
    - Assert DB reflects the new status
    """
    app.config.update(TESTING=True)
    setup_clean_db()

    with app.test_client() as client, app.app_context():
        # 1) Register (auto login)
        r = register(client, "Tester", "tester@example.com", "pw")
        assert r.status_code == 200 and r.json["ok"]

        # 2) Create an idea
        payload = {
            "title": "Test Post",
            "platform": "Instagram",
            "scheduled_time": iso_in(2),  # two hours from now
            "status": "Idea",
            "details": "Test details",
            "thumbnail_url": ""
        }
        resp = client.post(
            "/api/ideas",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.json["ok"] is True
        idea_id = resp.json["id"]
        assert isinstance(idea_id, int)

        # 3) Update status to 'Scheduled'
        upd = client.patch(
            f"/api/ideas/{idea_id}",
            data=json.dumps({"status": "Scheduled"}),
            content_type="application/json",
        )
        assert upd.status_code == 200
        assert upd.json["ok"] is True

        # 4) Verify in DB
        c = db.session.get(Content, idea_id)
        assert c is not None
        assert c.status == "Scheduled"


def test_post_idea_requires_title():
    """
    Validation path:
    - Register (for an authenticated session)
    - POST /api/ideas with an empty title should return 400 and a clear message
    """
    app.config.update(TESTING=True)
    setup_clean_db()

    with app.test_client() as client, app.app_context():
        # Must be logged in to create an idea – easiest is register
        r = register(client, "Tester2", "tester2@example.com", "pw")
        assert r.status_code == 200 and r.json["ok"]

        # Missing title should fail with 400
        resp = client.post(
            "/api/ideas",
            json={
                "title": "",
                "platform": "Instagram",
                "scheduled_time": iso_in(1),
                "status": "Idea",
            },
        )
        assert resp.status_code == 400
        assert resp.json["ok"] is False
        assert "Title is required" in resp.json["message"]
