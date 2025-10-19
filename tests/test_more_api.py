# tests/test_more_api.py
"""
Additional API tests for Visiona.
Covers: authentication guards, insights schema, calendar reschedule, and library CRUD.
"""

import os, sys, json
from datetime import datetime, timedelta, timezone

# --- Setup so pytest can find the backend package ---
# Adds the parent directory (project root) to the Python path
# so that "backend.app" can be imported successfully.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Disable the reminder scheduler so background jobs don’t interfere during testing
os.environ["VISIONA_DISABLE_SCHEDULER"] = "1"

# Import the Flask app, database, and models from the main backend
from backend.app import app, db
from backend.models import User, Content


# ---------------------------------------------------------------------
# Helper functions (used across multiple tests)
# ---------------------------------------------------------------------

def register(client, name, email, password):
    """
    Helper function to register a user.
    This automatically logs the user in (because /register does that in the app).
    """
    return client.post("/register", data={"name": name, "email": email, "password": password})


def iso_in(hours=0):
    """
    Returns an ISO-8601 UTC timestamp string for the current time + given hours.
    Example: used to schedule future posts (e.g., 2 hours from now).
    """
    dt = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=hours)
    return dt.isoformat().replace("+00:00", "Z")


def setup_clean_db():
    """
    Drops and recreates the entire database before each test.
    Ensures each test starts with a clean slate and independent data.
    """
    with app.app_context():
        db.drop_all()
        db.create_all()


# ---------------------------------------------------------------------
# TEST 1 — Authentication Guard
# ---------------------------------------------------------------------

def test_auth_required_on_api_routes():
    """
    Verify that API routes are properly protected.
    Unauthenticated users should get redirected (302) or forbidden (401)
    when trying to access protected endpoints.
    """
    app.config.update(TESTING=True)
    setup_clean_db()
    with app.test_client() as client:
        # These requests should fail because the user isn’t logged in
        assert client.get("/api/ideas").status_code in (302, 401)
        assert client.get("/api/insights").status_code in (302, 401)
        assert client.post("/api/ideas", json={"title": "x"}).status_code in (302, 401)


# ---------------------------------------------------------------------
# TEST 2 — Insights Endpoint
# ---------------------------------------------------------------------

def test_insights_schema_and_values_empty_ok():
    """
    Test that /api/insights works and returns the correct structure,
    even when there is no content yet in the database.
    This ensures the frontend graphs and stats can still load gracefully.
    """
    app.config.update(TESTING=True)
    setup_clean_db()
    with app.test_client() as client, app.app_context():
        # Register a test user (this also logs them in)
        register(client, "User1", "user1@example.com", "pw")

        # Call the insights API endpoint
        resp = client.get("/api/insights")
        j = resp.get_json()
        assert resp.status_code == 200 and j["ok"]

        # Check that expected data keys are always present
        data = j["data"]
        for key in ("week_summary", "weekly_series", "platform_breakdown", "avg_idea_to_post_days", "suggestions"):
            assert key in data


# ---------------------------------------------------------------------
# TEST 3 — Calendar Reschedule
# ---------------------------------------------------------------------

def test_patch_only_scheduled_time_from_calendar():
    """
    Simulates a user dragging a scheduled post to a new date on the calendar.
    This tests that PATCH /api/ideas/:id correctly updates 'scheduled_time'
    and that the new value is stored in the database.
    """
    app.config.update(TESTING=True)
    setup_clean_db()
    with app.test_client() as client, app.app_context():
        # Create and log in a test user
        register(client, "CalUser", "cal@example.com", "pw")

        # Step 1: Create a scheduled post 6 hours in the future
        payload = {
            "title": "Calendar Move",
            "platform": "Instagram",
            "scheduled_time": iso_in(6),
            "status": "Scheduled"
        }
        create = client.post("/api/ideas", json=payload)
        idea_id = create.json["id"]

        # Step 2: "Move" it 30 hours later — simulate a drag-and-drop action
        new_dt = (datetime.utcnow() + timedelta(hours=30)).replace(tzinfo=timezone.utc)
        new_iso = new_dt.isoformat().replace("+00:00", "Z")

        # Step 3: Update the scheduled_time with a PATCH request
        update = client.patch(
            f"/api/ideas/{idea_id}",
            data=json.dumps({"scheduled_time": new_iso}),
            content_type="application/json"
        )
        assert update.status_code == 200 and update.json["ok"]

        # Step 4: Verify the change in the database
        c = db.session.get(Content, idea_id)
        # Allowing up to 2 seconds difference due to rounding/time drift
        assert abs((c.scheduled_time.replace(tzinfo=timezone.utc) - new_dt).total_seconds()) < 2


# ---------------------------------------------------------------------
# TEST 4 — Library CRUD (Create, Read, Delete)
# ---------------------------------------------------------------------

def test_library_min_crud():
    """
    Tests basic Library API operations:
    1. Create a new library item
    2. List all items to confirm it exists
    3. Delete the item and confirm it’s gone
    """
    app.config.update(TESTING=True)
    setup_clean_db()
    with app.test_client() as client, app.app_context():
        # Step 1: Register a new user (auto login)
        register(client, "LibUser", "lib@example.com", "pw")

        # Step 2: Create a new library item
        add = client.post("/api/library", json={
            "title": "Summer Promo",
            "caption": "Hot deals!",
            "hashtags": "#summer #promo",
            "category": "Campaign"
        })
        item_id = add.json["id"]

        # Step 3: Confirm it appears in the list
        lst = client.get("/api/library")
        assert any(i["id"] == item_id for i in lst.json["items"])

        # Step 4: Delete the item
        client.delete(f"/api/library/{item_id}")

        # Step 5: Confirm it’s no longer listed
        lst2 = client.get("/api/library")
        assert all(i["id"] != item_id for i in lst2.json["items"])
