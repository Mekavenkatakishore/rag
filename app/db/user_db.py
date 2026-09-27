"""
user_db.py
──────────
SQLite-backed user storage using Python's built-in sqlite3 module.
Refactored to use centralized app.core.config settings and app.db.base_db context manager.
"""

import sqlite3
import datetime
from app.core.config import settings
from app.db.base_db import get_db_connection

def get_connection() -> sqlite3.Connection:
    """Opens and returns a connection to the SQLite database."""
    conn = sqlite3.connect(settings.USER_DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    """Creates the users table if it does not already exist."""
    with get_db_connection(settings.USER_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                username         TEXT    NOT NULL UNIQUE,
                email            TEXT    NOT NULL UNIQUE,
                hashed_password  TEXT    NOT NULL,
                salt             TEXT    NOT NULL,
                created_at       TEXT    NOT NULL
            )
        """)

def create_user(username: str, email: str, hashed_password: str, salt: str) -> dict:
    """Inserts a new user row into the users table."""
    created_at = datetime.datetime.utcnow().isoformat()
    try:
        with get_db_connection(settings.USER_DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, email, hashed_password, salt, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, email, hashed_password, salt, created_at)
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            raise ValueError(f"Username '{username}' is already taken.")
        elif "email" in str(e):
            raise ValueError(f"Email '{email}' is already registered.")
        else:
            raise ValueError("Registration failed due to a conflict.")

    return {"id": user_id, "username": username, "email": email, "created_at": created_at}

def get_user_by_username(username: str) -> dict | None:
    """Fetches a user row by username."""
    with get_db_connection(settings.USER_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id: int) -> dict | None:
    """Fetches a user row by primary key ID."""
    with get_db_connection(settings.USER_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
