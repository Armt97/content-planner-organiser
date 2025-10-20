# backend/wsgi.py
from app import app  # imports the Flask app instance from app.py

# Optional: sanity check hook (can be removed)
if __name__ == "__main__":
    app.run()
