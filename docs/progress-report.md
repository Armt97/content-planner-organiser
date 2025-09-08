# Project Progress Report — Content Planner and Organiser for Social Media Creators

## Completed Tasks (Update)
- Set up a Python virtual environment inside `backend/venv`.
- Installed Flask and created a minimal backend application.
- Implemented initial routes:
  - `/health` → returns JSON status response.
  - `/` → serves the main index.html template.
  - `/idea-board`, `/calendar`, `/library`, `/insights` → serve frontend pages.
- Configured the backend to run successfully on port 5001 (due to port 5000 being in use).
- Added `requirements.txt` to track project dependencies.
- Built the homepage UI (`frontend/index.html`) with:
  - Splash screen and typewriter effect.
  - Navbar with navigation links.
  - Styled login and signup modals using Bootstrap.
- Added static assets:
  - `frontend/static/styles.css` for global styling, hero section, and modal design.
  - Background images (`swirl.jpg`, `swirls.jpg`).
- Added a static **Content Calendar page** (`frontend/calendar.html`) using **FullCalendar.js**:
  - Displays monthly, weekly, daily, and list views.
  - Includes sample events (Instagram, TikTok, YouTube, Stories).
- Added a static **Content Idea Board** (`frontend/idea-board.html`) with a Kanban-style layout:
  - Columns for *Ideas*, *In Progress*, *Scheduled*, and *Posted*.
  - Sample content cards for demonstration.
- Added **database integration with SQLite**:
  - Created `User` and `Content` models using SQLAlchemy.
  - Configured Flask to use `visiona.db`.
  - Added `/init-db` route to initialise the database and create tables.
- Updated GitHub repository with backend, frontend pages, static assets, and database models.

## Remaining Tasks
  - Add authentication (signup/login/logout).
  - Connect calendar and idea board to backend/database for persistence.
  - Prepare deployment environment (AWS EC2/S3).

## Changes in Scope
- No major changes in scope so far.  
- Minor technical adjustment: Flask continues to run on port 5001 instead of 5000 due to a port conflict on macOS.


