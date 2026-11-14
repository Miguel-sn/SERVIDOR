import os


os.environ.setdefault("DB_HOST", "test-db")
os.environ.setdefault("DB_PORT", "3306")
os.environ.setdefault("DB_USER", "test-user")
os.environ.setdefault("DB_PASSWORD", "test-password")
os.environ.setdefault("DB_NAME", "test-db")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-that-is-32bytes!")
os.environ.setdefault("FLASK_SECRET_KEY", "test-flask-secret-key-that-is-32bytes!")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:54321")

from app import app

app.config["TESTING"] = True
