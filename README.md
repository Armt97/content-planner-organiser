# Content Planner and Organiser for Social Media Creators

**Course:** 159.333 — Semester 2, 2025  
**Student:** Aroha Tawiri (ID: 22013041)

---

## 🧠 Project Overview
This project is a web-based content planning and organisation tool designed for social media creators. It aims to provide a simple yet powerful platform for managing content ideas, scheduling posts, and storing reusable hashtags and captions. To further support creators in maintaining a consistent and efficient posting routine, the system includes insightful data visualisations and an interactive grid preview, helping users spot trends, plan aesthetically pleasing layouts, and improve their workflow over time.

---

## 👥 Target Users
Individual content creators, students, freelancers, or small business owners who publish on Instagram, TikTok, and YouTube. They typically manage content alone and need a centralised, user-friendly system to stay organised, keep consistent, and visually preview their feed layout.

---

## ✨ Key Features
- **Content Idea Board (Kanban):** Idea → Draft → Scheduled → Posted  
- **Content Calendar:** Drag-and-drop by date, platform, and time  
- **Hashtag & Caption Library:** Save/reuse hashtag sets and templates  
- **Post Reminders:** In-dashboard or email reminders  
- **Media Preview:** Upload/attach image previews to content cards  
- **Grid Preview (Aesthetic Feed Planner):** Visual feed layout planning  
- **Data Insights Dashboard:** Weekly activity, platform breakdown, idea→publish time, and simple rule-based suggestions  
- **Authentication:** Secure login, signup, and logout (Flask-Login & bcrypt)  
- **Testing:** Automated API and authentication tests using Pytest  

---

## 🧰 Tech Stack
- **Frontend:** HTML, CSS, JavaScript (Bootstrap)  
- **Backend:** Python (Flask, RESTful API)  
- **Database:** SQLite (dev) → PostgreSQL (future deploy)  
- **Cloud:** AWS EC2 (Flask host), AWS S3 (media storage planned)  
- **Libraries:** Flask-Login, SQLAlchemy, FullCalendar.js, Chart.js, Pytest, SendGrid API (email), AWS SDK  

---

## ⚙️ How to Run Locally

### 1️⃣ Clone the repository
```bash
git clone https://github.com/Armt97/content-planner-organiser.git
cd content-planner-organiser
```

### 2️⃣ Create and activate a virtual environment

Mac/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```
Windows
```bash
python -m venv venv
venv\Scripts\activate
```

### 3️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 4️⃣ Run the application
```bash
python backend/app.py
```

Then open your browser and go to:
👉 http://127.0.0.1:5000

You can register a new user, log in, and begin creating ideas on the Idea Board.

### ✅ Testing

Run automated backend tests using:
```bash
pytest
```

Expected output:
====================== test session starts ======================
collected 6 items
====================== 6 passed in 1.2s ========================

---

☁️ Deployment

The project is deployed on AWS EC2 for demonstration:
Demo link:
http://ec2-52-63-20-45.ap-southeast-2.compute.amazonaws.com/idea-board

📩 Email reminders are disabled on EC2 due to outbound SMTP restrictions but work locally when configured.

---

🚀 Future Work

- Integrate AWS S3 for image uploads and thumbnails
- Move database to PostgreSQL (AWS RDS) for scalability
- Replace SMTP with SendGrid HTTPS API or AWS SES for reliable email delivery
- Implement AI-powered insights for hashtags, captions, and best posting times
- Add push notifications and improve mobile responsiveness

---

👩‍💻 Developer

Aroha Tawiri
Bachelor of Information Sciences (Software Engineering & AI)
Massey University — Semester 2, 2025

---
