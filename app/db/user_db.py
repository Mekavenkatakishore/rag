"""
user_db.py
──────────
SQLite-backed user storage using Python's built-in sqlite3 module.
No external database server required — just a local file: users.db

Tables:
    users (id, username, email, hashed_password, salt, created_at)
"""

import sqlite3
import os
import datetime

# Database file is stored in the same directory as this module
DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def get_connection() -> sqlite3.Connection:
    """Opens and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Makes rows accessible as dicts
    return conn


def initialize_db():
    """
    Creates the users table if it does not already exist.
    Called once at application startup via server.py.
    """
    conn = get_connection()
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
    conn.commit()
    conn.close()


def create_user(username: str, email: str, hashed_password: str, salt: str) -> dict:
    """
    Inserts a new user row into the users table.

    Args:
        username: The chosen display name.
        email: The user's email address.
        hashed_password: The PBKDF2 hash of the password.
        salt: The random salt used during hashing.

    Returns:
        The newly created user as a dict.

    Raises:
        ValueError: If username or email is already taken.
    """
    conn = get_connection()
    cursor = conn.cursor()
    created_at = datetime.datetime.utcnow().isoformat()

    try:
        cursor.execute(
            """
            INSERT INTO users (username, email, hashed_password, salt, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, email, hashed_password, salt, created_at)
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError as e:
        conn.close()
        if "username" in str(e):
            raise ValueError(f"Username '{username}' is already taken.")
        elif "email" in str(e):
            raise ValueError(f"Email '{email}' is already registered.")
        else:
            raise ValueError("Registration failed due to a conflict.")
    finally:
        conn.close()

    return {"id": user_id, "username": username, "email": email, "created_at": created_at}


def get_user_by_username(username: str) -> dict | None:
    """
    Fetches a user row by username.

    Returns:
        User dict if found, None otherwise.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    """
    Fetches a user row by primary key ID.

    Returns:
        User dict if found, None otherwise.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
