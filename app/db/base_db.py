import sqlite3
import os
from contextlib import contextmanager
from typing import Generator
from app.core.config import settings

@contextmanager
def get_db_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager providing a safe SQLite connection with auto-commit/rollback
    and row factory configuration.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def execute_query(db_path: str, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Helper to execute SELECT queries and return rows."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

def execute_statement(db_path: str, query: str, params: tuple = ()) -> int:
    """Helper to execute INSERT/UPDATE/DELETE queries and return lastrowid or rowcount."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.lastrowid
