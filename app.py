"""
DIGIDORM — College Hostel Management System
Flask + MySQL backend
"""

import os
from functools import wraps
from datetime import datetime

import pymysql
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config

app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ------------------------------------------------------------------
# Database helper
# ------------------------------------------------------------------
def get_db():
    """Open a new PyMySQL connection returning rows as dicts."""
    return pymysql.connect(
        host=app.config["MYSQL_HOST"],
        port=app.config["MYSQL_PORT"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DB"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def query(sql, params=None, fetch="all"):
    """Run a SELECT and return rows ('all' | 'one')."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall() if fetch == "all" else cur.fetchone()
    finally:
        conn.close()


def execute(sql, params=None):
    """Run an INSERT / UPDATE / DELETE and return the new row id (if any)."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


# ------------------------------------------------------------------
# Auth decorators
# ------------------------------------------------------------------
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You don't have access to that page.", "danger")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    return {
        "current_user": {
            "id": session.get("user_id"),
            "name": session.get("name"),
            "role": session.get("role"),
        }
    }


# ==================================================================
# PUBLIC PAGES
# ==================================================================
@app.route("/")
def index():
    reviews = query(
        """SELECT r.*, s.name FROM review r
           JOIN student s ON s.student_id = r.student_id
           ORDER BY r.date DESC LIMIT 6"""
    )
    rooms = query("SELECT * FROM room ORDER BY block, room_no LIMIT 6")
    gallery = query("SELECT * FROM gallery ORDER BY uploaded_on DESC LIMIT 8")
    return render_template("index.html", reviews=reviews, rooms=rooms, gallery=gallery)


@app.route("/rooms")
def rooms():
    all_rooms = query("SELECT * FROM room ORDER BY block, room_no")
    return render_template("rooms.html", rooms=all_rooms)


@app.route("/gallery")
def hostel_gallery():
    images = query("SELECT * FROM gallery ORDER BY uploaded_on DESC")
    return render_template("hostel_gallery.html", images=images)


@app.route("/reviews", methods=["GET", "POST"])
def reviews():
    if request.method == "POST":
        if "user_id" not in session or session.get("role") != "student":
            flash("Please log in as a student to leave a review.", "warning")
            return redirect(url_for("login"))
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        execute(
            "INSERT INTO review (student_id, rating, comment) VALUES (%s,%s,%s)",
            (session["user_id"], rating, comment),
        )
        flash("Thanks for your feedback!", "success")
        return redirect(url_for("reviews"))

    all_reviews = query(
        """SELECT r.*, s.name FROM review r
           JOIN student s ON s.student_id = r.student_id
           ORDER BY r.date DESC"""
    )
    return render_template("reviews.html", reviews=all_reviews)


@app.route("/rules")
def rules():
    return render_template("rules.html")


# ==================================================================
# AUTH
# ==================================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        user = None
        if role == "student":
            user = query(
                "SELECT * FROM student WHERE roll_no=%s OR email=%s",
                (identifier, identifier), fetch="one",
            )
            id_field, name_field = "student_id", "name"
        elif role == "admin":
            user = query("SELECT * FROM admin WHERE username=%s", (identifier,), fetch="one")
            id_field, name_field = "admin_id", "name"
        elif role == "warden":
            user = query("SELECT * FROM warden WHERE username=%s", (identifier,), fetch="one")
            id_field, name_field = "warden_id", "name"
        else:
            flash("Please choose a login type.", "danger")
            return redirect(url_for("login"))

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user[id_field]
            session["role"] = role
            session["name"] = user[name_field]
            flash(f"Welcome back, {user[name_field]}!", "success")
            return redirect(url_for(f"{role}_dashboard"))

        flash("Invalid credentials. Please try again.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ==================================================================
# STUDENT DASHBOARD
# ==================================================================
@app.route("/student/dashboard")
@login_required("student")
def student_dashboard():
    sid = session["user_id"]
    student = query(
        """SELECT s.*, r.room_no, r.block, r.room_type FROM student s
           LEFT JOIN room r ON r.room_id = s.room_id WHERE s.student_id=%s""",
        (sid,), fetch="one",
    )
    complaints = query("SELECT * FROM complaint WHERE student_id=%s ORDER BY date DESC LIMIT 5", (sid,))
    fees = query("SELECT * FROM fee WHERE student_id=%s ORDER BY fee_id DESC", (sid,))
    notices = query("SELECT * FROM notice ORDER BY date DESC LIMIT 5")
    leaves = query("SELECT * FROM leave_application WHERE student_id=%s ORDER BY applied_on DESC LIMIT 5", (sid,))
    pending_fee = query(
        "SELECT COALESCE(SUM(amount),0) AS total FROM fee WHERE student_id=%s AND payment_status!='Paid'",
        (sid,), fetch="one",
    )
    return render_template(
        "student_dashboard.html", student=student, complaints=complaints,
        fees=fees, notices=notices, leaves=leaves, pending_fee=pending_fee["total"],
    )


@app.route("/student/profile", methods=["GET", "POST"])
@login_required("student")
def profile():
    sid = session["user_id"]
    if request.method == "POST":
        phone = request.form.get("phone")
        photo_name = None
        photo = request.files.get("photo")
        if photo and photo.filename and allowed_file(photo.filename):
            photo_name = secure_filename(f"student_{sid}_{photo.filename}")
            photo.save(os.path.join(app.config["UPLOAD_FOLDER"], photo_name))

        if photo_name:
            execute("UPDATE student SET phone=%s, photo=%s WHERE student_id=%s", (phone, photo_name, sid))
        else:
            execute("UPDATE student SET phone=%s WHERE student_id=%s", (phone, sid))
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))

    student = query(
        """SELECT s.*, r.room_no, r.block FROM student s
           LEFT JOIN room r ON r.room_id = s.room_id WHERE s.student_id=%s""",
        (sid,), fetch="one",
    )
    return render_template("profile.html", student=student)


@app.route("/student/complaints", methods=["GET", "POST"])
@login_required("student")
def student_complaints():
    sid = session["user_id"]
    if request.method == "POST":
        title = request.form.get("title")
        category = request.form.get("category")
        description = request.form.get("description")
        execute(
            "INSERT INTO complaint (student_id, title, category, description) VALUES (%s,%s,%s,%s)",
            (sid, title, category, description),
        )
        flash("Complaint raised. The warden/admin has been notified.", "success")
        return redirect(url_for("student_complaints"))

    complaints = query("SELECT * FROM complaint WHERE student_id=%s ORDER BY date DESC", (sid,))
    return render_template("complaints.html", complaints=complaints, is_admin=False, is_warden=False)


@app.route("/student/fees")
@login_required("student")
def student_fees():
    sid = session["user_id"]
    fees = query("SELECT * FROM fee WHERE student_id=%s ORDER BY fee_id DESC", (sid,))
    return render_template("fees.html", fees=fees, is_admin=False)


@app.route("/student/fees/<int:fee_id>/receipt")
@login_required("student")
def download_receipt(fee_id):
    fee = query(
        "SELECT * FROM fee WHERE fee_id=%s AND student_id=%s",
        (fee_id, session["user_id"]), fetch="one",
    )
    if not fee or fee["payment_status"] != "Paid":
        flash("Receipt not available.", "warning")
        return redirect(url_for("student_fees"))
    # Simple text receipt (swap for a PDF generator such as the pdf skill if needed)
    receipt_text = (
        f"DIGIDORM HOSTEL — FEE RECEIPT\n"
        f"Receipt No: {fee['receipt']}\n"
        f"Amount Paid: Rs. {fee['amount']}\n"
        f"Payment Date: {fee['payment_date']}\n"
        f"Status: {fee['payment_status']}\n"
    )
    path = os.path.join(app.config["UPLOAD_FOLDER"], f"receipt_{fee_id}.txt")
    with open(path, "w") as fh:
        fh.write(receipt_text)
    return send_from_directory(app.config["UPLOAD_FOLDER"], f"receipt_{fee_id}.txt", as_attachment=True)


@app.route("/student/leave", methods=["GET", "POST"])
@login_required("student")
def student_leave():
    sid = session["user_id"]
    if request.method == "POST":
        execute(
            """INSERT INTO leave_application (student_id, from_date, to_date, reason)
               VALUES (%s,%s,%s,%s)""",
            (sid, request.form.get("from_date"), request.form.get("to_date"), request.form.get("reason")),
        )
        flash("Leave application submitted.", "success")
        return redirect(url_for("student_leave"))

    leaves = query("SELECT * FROM leave_application WHERE student_id=%s ORDER BY applied_on DESC", (sid,))
    return render_template("leave.html", leaves=leaves, is_warden=False)


@app.route("/student/notices")
@login_required("student")
def student_notices():
    notices = query("SELECT * FROM notice ORDER BY date DESC")
    return render_template("notices.html", notices=notices, is_admin=False)


# ==================================================================
# ADMIN DASHBOARD
# ==================================================================
@app.route("/admin/dashboard")
@login_required("admin")
def admin_dashboard():
    stats = {
        "students": query("SELECT COUNT(*) c FROM student", fetch="one")["c"],
        "rooms": query("SELECT COUNT(*) c FROM room", fetch="one")["c"],
        "pending_complaints": query(
            "SELECT COUNT(*) c FROM complaint WHERE status!='Resolved'", fetch="one"
        )["c"],
        "unpaid_fees": query(
            "SELECT COUNT(*) c FROM fee WHERE payment_status!='Paid'", fetch="one"
        )["c"],
    }
    recent_complaints = query("SELECT c.*, s.name FROM complaint c JOIN student s ON s.student_id=c.student_id ORDER BY date DESC LIMIT 5")
    return render_template("admin_dashboard.html", stats=stats, recent_complaints=recent_complaints)


@app.route("/admin/students", methods=["GET", "POST"])
@login_required("admin")
def admin_students():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            execute(
                """INSERT INTO student (name, roll_no, branch, year, gender, phone, email, password, room_id, hostel_block)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    request.form.get("name"), request.form.get("roll_no"), request.form.get("branch"),
                    request.form.get("year"), request.form.get("gender"), request.form.get("phone"),
                    request.form.get("email"), generate_password_hash(request.form.get("password", "changeme123")),
                    request.form.get("room_id") or None, request.form.get("hostel_block"),
                ),
            )
            flash("Student added.", "success")
        elif action == "update":
            execute(
                """UPDATE student SET name=%s, branch=%s, year=%s, phone=%s, email=%s,
                   room_id=%s, hostel_block=%s WHERE student_id=%s""",
                (
                    request.form.get("name"), request.form.get("branch"), request.form.get("year"),
                    request.form.get("phone"), request.form.get("email"), request.form.get("room_id") or None,
                    request.form.get("hostel_block"), request.form.get("student_id"),
                ),
            )
            flash("Student updated.", "success")
        elif action == "delete":
            execute("DELETE FROM student WHERE student_id=%s", (request.form.get("student_id"),))
            flash("Student removed.", "info")
        return redirect(url_for("admin_students"))

    search = request.args.get("q", "")
    if search:
        students = query(
            """SELECT s.*, r.room_no FROM student s LEFT JOIN room r ON r.room_id=s.room_id
               WHERE s.name LIKE %s OR s.roll_no LIKE %s ORDER BY s.student_id""",
            (f"%{search}%", f"%{search}%"),
        )
    else:
        students = query(
            """SELECT s.*, r.room_no FROM student s LEFT JOIN room r ON r.room_id=s.room_id
               ORDER BY s.student_id"""
        )
    all_rooms = query("SELECT * FROM room ORDER BY block, room_no")
    return render_template("admin_dashboard.html", students=students, all_rooms=all_rooms, section="students", search=search)


@app.route("/admin/rooms", methods=["GET", "POST"])
@login_required("admin")
def admin_rooms():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            execute(
                "INSERT INTO room (room_no, block, room_type, capacity, occupied) VALUES (%s,%s,%s,%s,0)",
                (request.form.get("room_no"), request.form.get("block"),
                 request.form.get("room_type"), request.form.get("capacity")),
            )
            flash("Room added.", "success")
        elif action == "update":
            execute(
                "UPDATE room SET room_type=%s, capacity=%s, occupied=%s WHERE room_id=%s",
                (request.form.get("room_type"), request.form.get("capacity"),
                 request.form.get("occupied"), request.form.get("room_id")),
            )
            flash("Room updated.", "success")
        elif action == "delete":
            execute("DELETE FROM room WHERE room_id=%s", (request.form.get("room_id"),))
            flash("Room removed.", "info")
        return redirect(url_for("admin_rooms"))

    all_rooms = query("SELECT * FROM room ORDER BY block, room_no")
    return render_template("rooms.html", rooms=all_rooms, is_admin=True)


@app.route("/admin/fees", methods=["GET", "POST"])
@login_required("admin")
def admin_fees():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            execute(
                "INSERT INTO fee (student_id, amount, payment_status) VALUES (%s,%s,'Unpaid')",
                (request.form.get("student_id"), request.form.get("amount")),
            )
            flash("Fee record added.", "success")
        elif action == "mark_paid":
            receipt = f"RCPT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            execute(
                "UPDATE fee SET payment_status='Paid', payment_date=%s, receipt=%s WHERE fee_id=%s",
                (datetime.now().date(), receipt, request.form.get("fee_id")),
            )
            flash("Fee marked as paid.", "success")
        return redirect(url_for("admin_fees"))

    fees = query(
        """SELECT f.*, s.name, s.roll_no FROM fee f
           JOIN student s ON s.student_id=f.student_id ORDER BY f.fee_id DESC"""
    )
    students = query("SELECT student_id, name, roll_no FROM student ORDER BY name")
    return render_template("fees.html", fees=fees, is_admin=True, students=students)


@app.route("/admin/complaints", methods=["GET", "POST"])
@login_required("admin")
def admin_complaints():
    if request.method == "POST":
        execute(
            "UPDATE complaint SET status=%s WHERE complaint_id=%s",
            (request.form.get("status"), request.form.get("complaint_id")),
        )
        flash("Complaint status updated.", "success")
        return redirect(url_for("admin_complaints"))

    complaints = query(
        """SELECT c.*, s.name, s.roll_no FROM complaint c
           JOIN student s ON s.student_id=c.student_id ORDER BY c.date DESC"""
    )
    return render_template("complaints.html", complaints=complaints, is_admin=True, is_warden=False)


@app.route("/admin/notices", methods=["GET", "POST"])
@login_required("admin")
def admin_notices():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            execute(
                "INSERT INTO notice (title, description) VALUES (%s,%s)",
                (request.form.get("title"), request.form.get("description")),
            )
            flash("Notice published.", "success")
        elif action == "delete":
            execute("DELETE FROM notice WHERE notice_id=%s", (request.form.get("notice_id"),))
            flash("Notice removed.", "info")
        return redirect(url_for("admin_notices"))

    notices = query("SELECT * FROM notice ORDER BY date DESC")
    return render_template("notices.html", notices=notices, is_admin=True)


@app.route("/admin/gallery", methods=["GET", "POST"])
@login_required("admin")
def admin_gallery():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            photo = request.files.get("image")
            if photo and photo.filename and allowed_file(photo.filename):
                filename = secure_filename(f"gallery_{datetime.now().timestamp()}_{photo.filename}")
                photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                execute(
                    "INSERT INTO gallery (filename, caption) VALUES (%s,%s)",
                    (filename, request.form.get("caption")),
                )
                flash("Image uploaded.", "success")
            else:
                flash("Please choose a valid image file.", "danger")
        elif action == "delete":
            execute("DELETE FROM gallery WHERE image_id=%s", (request.form.get("image_id"),))
            flash("Image removed.", "info")
        return redirect(url_for("admin_gallery"))

    images = query("SELECT * FROM gallery ORDER BY uploaded_on DESC")
    return render_template("hostel_gallery.html", images=images, is_admin=True)


@app.route("/admin/reports")
@login_required("admin")
def admin_reports():
    summary = {
        "total_students": query("SELECT COUNT(*) c FROM student", fetch="one")["c"],
        "total_revenue": query("SELECT COALESCE(SUM(amount),0) t FROM fee WHERE payment_status='Paid'", fetch="one")["t"],
        "pending_revenue": query("SELECT COALESCE(SUM(amount),0) t FROM fee WHERE payment_status!='Paid'", fetch="one")["t"],
        "occupancy": query("SELECT COALESCE(SUM(occupied),0) o, COALESCE(SUM(capacity),0) c FROM room", fetch="one"),
        "complaint_breakdown": query("SELECT status, COUNT(*) c FROM complaint GROUP BY status"),
    }
    return render_template("admin_dashboard.html", section="reports", summary=summary)


# ==================================================================
# WARDEN DASHBOARD
# ==================================================================
@app.route("/warden/dashboard")
@login_required("warden")
def warden_dashboard():
    today = datetime.now().date()
    present_today = query(
        "SELECT COUNT(*) c FROM attendance WHERE date=%s AND status='Present'", (today,), fetch="one"
    )["c"]
    pending_leaves = query("SELECT COUNT(*) c FROM leave_application WHERE status='Pending'", fetch="one")["c"]
    open_complaints = query("SELECT COUNT(*) c FROM complaint WHERE status!='Resolved'", fetch="one")["c"]
    visitors_today = query(
        "SELECT COUNT(*) c FROM visitor WHERE DATE(entry_time)=%s", (today,), fetch="one"
    )["c"]
    return render_template(
        "warden_dashboard.html", present_today=present_today, pending_leaves=pending_leaves,
        open_complaints=open_complaints, visitors_today=visitors_today,
    )


@app.route("/warden/attendance", methods=["GET", "POST"])
@login_required("warden")
def warden_attendance():
    today = datetime.now().date()
    if request.method == "POST":
        student_ids = request.form.getlist("present")
        all_students = query("SELECT student_id FROM student")
        for s in all_students:
            status = "Present" if str(s["student_id"]) in student_ids else "Absent"
            execute(
                """INSERT INTO attendance (student_id, date, status, marked_by)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE status=VALUES(status)""",
                (s["student_id"], today, status, session.get("name")),
            )
        flash("Attendance recorded for today.", "success")
        return redirect(url_for("warden_attendance"))

    students = query(
        """SELECT s.*, r.room_no, a.status FROM student s
           LEFT JOIN room r ON r.room_id=s.room_id
           LEFT JOIN attendance a ON a.student_id=s.student_id AND a.date=%s
           ORDER BY s.name""",
        (today,),
    )
    return render_template("warden_dashboard.html", section="attendance", students=students, today=today)


@app.route("/warden/complaints")
@login_required("warden")
def warden_complaints():
    complaints = query(
        """SELECT c.*, s.name, s.roll_no FROM complaint c
           JOIN student s ON s.student_id=c.student_id ORDER BY c.date DESC"""
    )
    return render_template("complaints.html", complaints=complaints, is_admin=False, is_warden=True)


@app.route("/warden/complaints/update", methods=["POST"])
@login_required("warden")
def warden_update_complaint():
    execute(
        "UPDATE complaint SET status=%s WHERE complaint_id=%s",
        (request.form.get("status"), request.form.get("complaint_id")),
    )
    flash("Complaint status updated.", "success")
    return redirect(url_for("warden_complaints"))


@app.route("/warden/visitors", methods=["GET", "POST"])
@login_required("warden")
def warden_visitors():
    if request.method == "POST":
        execute(
            """INSERT INTO visitor (student_id, visitor_name, relation, phone, purpose)
               VALUES (%s,%s,%s,%s,%s)""",
            (
                request.form.get("student_id"), request.form.get("visitor_name"),
                request.form.get("relation"), request.form.get("phone"), request.form.get("purpose"),
            ),
        )
        flash("Visitor entry logged.", "success")
        return redirect(url_for("warden_visitors"))

    visitors = query(
        """SELECT v.*, s.name AS student_name, s.roll_no FROM visitor v
           JOIN student s ON s.student_id=v.student_id ORDER BY v.entry_time DESC LIMIT 50"""
    )
    students = query("SELECT student_id, name, roll_no FROM student ORDER BY name")
    return render_template("warden_dashboard.html", section="visitors", visitors=visitors, students=students)


@app.route("/warden/leave", methods=["GET", "POST"])
@login_required("warden")
def warden_leave():
    if request.method == "POST":
        execute(
            "UPDATE leave_application SET status=%s WHERE leave_id=%s",
            (request.form.get("status"), request.form.get("leave_id")),
        )
        flash("Leave request updated.", "success")
        return redirect(url_for("warden_leave"))

    leaves = query(
        """SELECT l.*, s.name, s.roll_no FROM leave_application l
           JOIN student s ON s.student_id=l.student_id ORDER BY l.applied_on DESC"""
    )
    return render_template("leave.html", leaves=leaves, is_warden=True)


# ==================================================================
# Uploaded file access
# ==================================================================
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ==================================================================
if __name__ == "__main__":
    app.run(debug=True)
