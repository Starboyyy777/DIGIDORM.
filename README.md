# DIGIDORM — College Hostel Management System

Full-stack hostel management app: Flask + MySQL backend, Bootstrap 5 frontend.

## 1. Requirements
- Python 3.10+
- MySQL (XAMPP's MySQL/MariaDB works fine)

## 2. Setup

```bash
# 1. Create & activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start MySQL (via XAMPP control panel, or your own MySQL server)

# 4. Import the database
mysql -u root -p < database/hostel.sql
# or: open phpMyAdmin → Import → select database/hostel.sql

# 5. Configure DB credentials if they differ from XAMPP defaults
#    edit config.py, or set environment variables:
#    MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, SECRET_KEY

# 6. Run the app
python app.py
```

App runs at **http://127.0.0.1:5000**

## 3. Demo logins (seeded in hostel.sql)

| Role    | Username / Roll No | Password    |
|---------|---------------------|-------------|
| Admin   | admin               | admin123    |
| Warden  | warden              | warden123   |
| Student | CS101               | student123  |

## 4. Project structure

```
DIGIDORM/
├── app.py                 # Flask routes (public pages, auth, 3 dashboards)
├── config.py               # DB & app config (reads env vars)
├── requirements.txt
├── database/hostel.sql     # Full schema + sample data
├── static/
│   ├── css/style.css       # Design system (navy/gold "door plate" theme)
│   ├── js/script.js        # Dark mode, star rating, live search, confirms
│   └── images/
├── templates/              # Jinja2 templates (17 pages)
└── uploads/                # Profile photos, gallery images, receipts
```

## 5. What's implemented

- **Public site**: home, rooms, gallery, reviews, rules, contact
- **Auth**: single login form with role switch (Student / Warden / Admin), hashed passwords (Werkzeug)
- **Student dashboard**: profile, room details, complaints, fee payment status + receipt download, leave application, notices, feedback/reviews
- **Admin dashboard**: student CRUD, room CRUD, fee management, complaint status updates, notice board, gallery uploads, reports
- **Warden dashboard**: attendance roll call, complaint handling, visitor entry log, leave approval
- **Extras**: dark mode toggle, live student search, responsive Bootstrap layout, image uploads

## 6. Not wired up (left as clear extension points)

- Email notifications (add Flask-Mail in `app.py`)
- QR code hostel ID (e.g. `qrcode` library, render on profile page)
- PDF report/receipt export (currently a plain-text receipt — swap in a PDF library)

## 7. Security notes before deploying

- Change `SECRET_KEY` in `config.py` / via environment variable
- Never commit real DB credentials — use environment variables in production
- Add CSRF protection (e.g. Flask-WTF) if you add more POST forms
- Set `debug=False` in `app.py` for production, and deploy behind a WSGI server (gunicorn) + real MySQL host (e.g. Render, PythonAnywhere, or any VPS)
