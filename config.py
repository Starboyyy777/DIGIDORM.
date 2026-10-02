import os

class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "digidorm-dev-secret-change-me")

    # MySQL (XAMPP defaults shown — update if yours differ)
MYSQL_HOST = os.getenv("MYSQLHOST", os.getenv("MYSQL_HOST", "localhost"))
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQLUSER", os.getenv("MYSQL_USER", "root"))
MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD", os.getenv("MYSQL_PASSWORD", ""))
MYSQL_DB = os.getenv("MYSQLDATABASE", os.getenv("MYSQL_DB", "hostel"))

    # Uploads
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}
