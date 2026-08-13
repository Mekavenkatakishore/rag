"""
hr_db.py
────────
SQLite-backed storage for HR jobs, candidates, profiles, scores, and evidence.

Tables:
    hr_jobs (job_id TEXT PRIMARY KEY, user_id INTEGER, title TEXT, jd_filename TEXT, jd_parsed_json TEXT, created_at TEXT)
    hr_candidates (candidate_id TEXT PRIMARY KEY, job_id TEXT, name TEXT, email TEXT, filename TEXT, processed_status TEXT, created_at TEXT)
    hr_candidate_profiles (candidate_id TEXT PRIMARY KEY, profile_json TEXT, updated_at TEXT)
    hr_candidate_scores (candidate_id TEXT PRIMARY KEY, job_id TEXT, final_score REAL, fit_category TEXT, score_breakdown_json TEXT, updated_at TEXT)
    hr_candidate_evidence (id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT, job_id TEXT, skill TEXT, matched INTEGER, evidence_quote TEXT, document TEXT, page INTEGER, created_at TEXT)
"""

import sqlite3
import os
import json
import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "hr_system.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_hr_db():
    """Creates HR database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hr_jobs (
            job_id         TEXT PRIMARY KEY,
            user_id        INTEGER,
            title          TEXT NOT NULL,
            jd_filename    TEXT,
            jd_parsed_json TEXT,
            created_at     TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hr_candidates (
            candidate_id     TEXT PRIMARY KEY,
            job_id           TEXT NOT NULL,
            name             TEXT,
            email            TEXT,
            filename         TEXT NOT NULL,
            processed_status TEXT NOT NULL,
            created_at       TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hr_candidate_profiles (
            candidate_id TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hr_candidate_scores (
            candidate_id         TEXT PRIMARY KEY,
            job_id               TEXT NOT NULL,
            final_score          REAL NOT NULL,
            fit_category         TEXT NOT NULL,
            score_breakdown_json TEXT NOT NULL,
            updated_at           TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hr_candidate_evidence (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id   TEXT NOT NULL,
            job_id         TEXT NOT NULL,
            skill          TEXT NOT NULL,
            matched        INTEGER NOT NULL,
            evidence_quote TEXT,
            document       TEXT,
            page           INTEGER,
            created_at     TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

# ─── Job Operations ─────────────────────────────────────────────────────────

def create_job(job_id: str, user_id: int | None, title: str, jd_filename: str = None, jd_parsed: dict = None) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    jd_json = json.dumps(jd_parsed) if jd_parsed else "{}"
    
    cursor.execute("""
        INSERT OR REPLACE INTO hr_jobs (job_id, user_id, title, jd_filename, jd_parsed_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (job_id, user_id, title, jd_filename, jd_json, now))
    
    conn.commit()
    conn.close()
    return {"job_id": job_id, "title": title, "created_at": now}

def get_job(job_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hr_jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["jd_parsed"] = json.loads(d["jd_parsed_json"]) if d.get("jd_parsed_json") else {}
    return d

# ─── Candidate Operations ───────────────────────────────────────────────────

def save_candidate(candidate_id: str, job_id: str, name: str, email: str, filename: str, status: str = "success") -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO hr_candidates (candidate_id, job_id, name, email, filename, processed_status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (candidate_id, job_id, name, email, filename, status, now))
    
    conn.commit()
    conn.close()
    return {"candidate_id": candidate_id, "job_id": job_id, "filename": filename}

def get_job_candidates(job_id: str) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hr_candidates WHERE job_id = ?", (job_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ─── Profile & Score Persistence ──────────────────────────────────────────

def save_candidate_profile(candidate_id: str, profile: dict):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO hr_candidate_profiles (candidate_id, profile_json, updated_at)
        VALUES (?, ?, ?)
    """, (candidate_id, json.dumps(profile), now))
    conn.commit()
    conn.close()

def get_candidate_profile(candidate_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT profile_json FROM hr_candidate_profiles WHERE candidate_id = ?", (candidate_id,))
    row = cursor.fetchone()
    conn.close()
    return json.loads(row["profile_json"]) if row else None

def save_candidate_score(candidate_id: str, job_id: str, final_score: float, fit_category: str, score_breakdown: dict):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO hr_candidate_scores (candidate_id, job_id, final_score, fit_category, score_breakdown_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (candidate_id, job_id, final_score, fit_category, json.dumps(score_breakdown), now))
    conn.commit()
    conn.close()

def get_candidate_score(candidate_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hr_candidate_scores WHERE candidate_id = ?", (candidate_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["score_breakdown"] = json.loads(d["score_breakdown_json"]) if d.get("score_breakdown_json") else {}
    return d

def save_evidence_items(candidate_id: str, job_id: str, evidence_list: list[dict]):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    
    # Clear existing evidence for candidate
    cursor.execute("DELETE FROM hr_candidate_evidence WHERE candidate_id = ?", (candidate_id,))
    
    for item in evidence_list:
        cursor.execute("""
            INSERT INTO hr_candidate_evidence (candidate_id, job_id, skill, matched, evidence_quote, document, page, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            candidate_id,
            job_id,
            item.get("skill", ""),
            1 if item.get("matched") else 0,
            item.get("evidence", ""),
            item.get("document", ""),
            item.get("page", 1),
            now
        ))
    conn.commit()
    conn.close()

def get_candidate_evidence(candidate_id: str) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hr_candidate_evidence WHERE candidate_id = ?", (candidate_id,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["matched"] = bool(d["matched"])
        result.append(d)
    return result

def get_job_leaderboard(job_id: str) -> list[dict]:
    """Joins candidates, scores, and profiles for job leaderboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            c.candidate_id, c.job_id, c.name, c.email, c.filename,
            s.final_score, s.fit_category, s.score_breakdown_json,
            p.profile_json
        FROM hr_candidates c
        LEFT JOIN hr_candidate_scores s ON c.candidate_id = s.candidate_id
        LEFT JOIN hr_candidate_profiles p ON c.candidate_id = p.candidate_id
        WHERE c.job_id = ?
        ORDER BY s.final_score DESC
    """, (job_id,))
    rows = cursor.fetchall()
    conn.close()
    
    leaderboard = []
    for idx, r in enumerate(rows, 1):
        d = dict(r)
        d["rank"] = idx
        d["score"] = d["final_score"] if d["final_score"] is not None else 0.0
        d["fit"] = d["fit_category"] if d["fit_category"] else "Pending"
        d["score_breakdown"] = json.loads(d["score_breakdown_json"]) if d.get("score_breakdown_json") else {}
        d["profile"] = json.loads(d["profile_json"]) if d.get("profile_json") else {}
        leaderboard.append(d)
    return leaderboard

def clear_job_data(job_id: str):
    """Deletes all candidate records, profiles, scores, and evidence for a specific job_id."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM hr_candidates WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM hr_candidate_scores WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM hr_candidate_evidence WHERE job_id = ?", (job_id,))
    cursor.execute("DELETE FROM hr_jobs WHERE job_id = ?", (job_id,))
    
    conn.commit()
    conn.close()
