"""
test_db_unit.py
───────────────
Unit tests for database initialization, schema creation, and user management.
Uses a temporary SQLite database to avoid touching real production/local data.
"""

import pytest
import sqlite3
from app.core.config import settings
from app.db import user_db

@pytest.fixture
def temp_user_db(tmp_path, monkeypatch):
    """Creates an isolated temporary SQLite database for test execution."""
    test_db_path = str(tmp_path / "test_users.db")
    monkeypatch.setattr(settings, "USER_DATABASE_PATH", test_db_path)
    user_db.initialize_db()
    return test_db_path

def test_db_initialization(temp_user_db):
    """Verify that user_db initializes the users table correctly."""
    conn = sqlite3.connect(temp_user_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    table = cursor.fetchone()
    conn.close()
    
    assert table is not None
    assert table[0] == "users"

def test_create_and_fetch_user(temp_user_db):
    """Verify inserting and fetching a user record."""
    user = user_db.create_user(
        username="test_recruiter",
        email="recruiter@example.com",
        hashed_password="dummy_hash_value",
        salt="dummy_salt_value",
        role="hr"
    )
    
    assert user["id"] is not None
    assert user["username"] == "test_recruiter"
    assert user["email"] == "recruiter@example.com"
    assert user["role"] == "hr"
    
    # Query user by username
    fetched = user_db.get_user_by_username("test_recruiter")
    assert fetched is not None
    assert fetched["id"] == user["id"]
    assert fetched["username"] == "test_recruiter"

def test_duplicate_user_raises_conflict(temp_user_db):
    """Verify that inserting duplicate usernames raises a ValueError."""
    user_db.create_user(
        username="unique_user",
        email="user1@example.com",
        hashed_password="hash",
        salt="salt"
    )
    
    with pytest.raises(ValueError, match="already taken"):
        user_db.create_user(
            username="unique_user",
            email="user2@example.com",
            hashed_password="hash",
            salt="salt"
        )

