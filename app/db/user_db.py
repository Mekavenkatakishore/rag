"""
user_db.py
──────────
SQLite-backed user storage using Python's built-in sqlite3 module.
Refactored to use centralized app.core.config settings and app.db.base_db context manager.
"""

import os
import sqlite3
import datetime
from app.core.config import settings
from app.db.base_db import get_db_connection
from app.core.security import generate_salt, hash_password
from app.utils.logger import logger

def get_connection() -> sqlite3.Connection:
    """Opens and returns a connection to the SQLite database."""
    conn = sqlite3.connect(settings.USER_DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def seed_default_user():
    """Seeds or updates the default admin/testing account."""
    demo_username = os.getenv("DEMO_USERNAME", "admin")
    demo_email = os.getenv("DEMO_EMAIL", "admin@ragpro.dev")
    demo_password = os.getenv("DEMO_PASSWORD", "admin@2026")
    demo_role = "hr"

    try:
        with get_db_connection(settings.USER_DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (demo_username,))
            row = cursor.fetchone()
            salt = generate_salt()
            hashed = hash_password(demo_password, salt)
            created_at = datetime.datetime.utcnow().isoformat()
            if row is None:
                cursor.execute(
                    """
                    INSERT INTO users (username, email, hashed_password, salt, role, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (demo_username, demo_email, hashed, salt, demo_role, created_at)
                )
                logger.info(f"Default admin account '{demo_username}' created successfully.")
            else:
                cursor.execute(
                    """
                    UPDATE users SET hashed_password = ?, salt = ? WHERE username = ?
                    """,
                    (hashed, salt, demo_username)
                )
                logger.info(f"Default admin account '{demo_username}' password synced successfully.")
    except Exception as e:
        logger.warning(f"Failed to seed demo admin account: {e}")

def initialize_db():
    """Creates the users table if it does not already exist and seeds default admin credentials."""
    with get_db_connection(settings.USER_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                username         TEXT    NOT NULL UNIQUE,
                email            TEXT    NOT NULL UNIQUE,
                hashed_password  TEXT    NOT NULL,
                salt             TEXT    NOT NULL,
                role             TEXT    NOT NULL DEFAULT 'hr',
                created_at       TEXT    NOT NULL
            )
        """)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'hr'")
        except sqlite3.OperationalError:
            pass

    seed_default_user()

def create_user(username: str, email: str, hashed_password: str, salt: str, role: str = "hr") -> dict:
    """Inserts a new user row into the users table."""
    created_at = datetime.datetime.utcnow().isoformat()
    try:
        with get_db_connection(settings.USER_DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, email, hashed_password, salt, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, email, hashed_password, salt, role, created_at)
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            raise ValueError(f"Username '{username}' is already taken.")
        elif "email" in str(e):
            raise ValueError(f"Email '{email}' is already registered.")
        else:
            raise ValueError("Registration failed due to a conflict.")

    return {"id": user_id, "username": username, "email": email, "role": role, "created_at": created_at}

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
