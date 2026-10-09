"""
hr_db.py
────────
SQLite-backed storage for HR jobs, candidates, profiles, scores, and evidence.
Refactored to use centralized app.core.config settings and app.db.base_db context manager.
Phase 1: Added candidate_status (Pending, Shortlisted) scoped to job_id + candidate_id.
"""

import sqlite3
import json
import datetime
from app.core.config import settings
from app.db.base_db import get_db_connection

VALID_CANDIDATE_STATUSES = {"Pending", "Shortlisted"}

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.HR_DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_hr_db():
    """Creates HR database tables if they do not exist."""
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
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
                candidate_status TEXT NOT NULL DEFAULT 'Pending',
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
        # Safe migration check for existing DB
        try:
            cursor.execute("ALTER TABLE hr_candidates ADD COLUMN candidate_status TEXT NOT NULL DEFAULT 'Pending'")
        except sqlite3.OperationalError:
            pass

# ─── Job Operations ─────────────────────────────────────────────────────────

def create_job(job_id: str, user_id: int | None, title: str, jd_filename: str = None, jd_parsed: dict = None) -> dict:
    now = datetime.datetime.utcnow().isoformat()
    jd_json = json.dumps(jd_parsed) if jd_parsed else "{}"
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO hr_jobs (job_id, user_id, title, jd_filename, jd_parsed_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (job_id, user_id, title, jd_filename, jd_json, now))
    return {"job_id": job_id, "title": title, "created_at": now}

def ensure_job_exists(job_id: str, user_id: int | None, default_title: str) -> dict:
    """Creates the job row only if it doesn't already exist.

    Unlike create_job() (which uses INSERT OR REPLACE and will silently wipe an
    already-parsed jd_parsed_json back to empty), this is safe to call repeatedly —
    e.g. from the legacy "upload to default job" routes — without destroying a JD
    that was already uploaded and parsed for this job_id.
    """
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO hr_jobs (job_id, user_id, title, jd_filename, jd_parsed_json, created_at)
            VALUES (?, ?, ?, NULL, '{}', ?)
        """, (job_id, user_id, default_title, now))
    return {"job_id": job_id, "title": default_title, "created_at": now}

def get_job(job_id: str) -> dict | None:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hr_jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["jd_parsed"] = json.loads(d["jd_parsed_json"]) if d.get("jd_parsed_json") else {}
        return d

# ─── Candidate Operations ───────────────────────────────────────────────────

def save_candidate(candidate_id: str, job_id: str, name: str, email: str, filename: str, status: str = "success") -> dict:
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO hr_candidates (candidate_id, job_id, name, email, filename, processed_status, candidate_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT candidate_status FROM hr_candidates WHERE candidate_id = ?), 'Pending'), ?)
        """, (candidate_id, job_id, name, email, filename, status, candidate_id, now))
    return {"candidate_id": candidate_id, "job_id": job_id, "filename": filename}

def get_job_candidates(job_id: str) -> list[dict]:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hr_candidates WHERE job_id = ?", (job_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_job_candidate(job_id: str, candidate_id: str) -> dict | None:
    """Get a specific candidate for a job."""
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hr_candidates WHERE job_id = ? AND candidate_id = ?", (job_id, candidate_id))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_candidate_shortlist_status(job_id: str, candidate_id: str, status: str) -> dict | None:
    """Updates shortlist status for a specific candidate scoped to job_id."""
    if status not in VALID_CANDIDATE_STATUSES:
        raise ValueError(f"Invalid candidate status '{status}'. Valid statuses: {VALID_CANDIDATE_STATUSES}")
        
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT candidate_id FROM hr_candidates WHERE candidate_id = ? AND job_id = ?", (candidate_id, job_id))
        if not cursor.fetchone():
            return None
            
        cursor.execute("""
            UPDATE hr_candidates
            SET candidate_status = ?
            WHERE candidate_id = ? AND job_id = ?
        """, (status, candidate_id, job_id))
        
    return {
        "success": True,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "candidate_status": status
    }

def get_shortlisted_candidates(job_id: str) -> list[dict]:
    """Retrieves all candidates for job_id that have candidate_status == 'Shortlisted'."""
    leaderboard = get_job_leaderboard(job_id)
    return [c for c in leaderboard if c.get("candidate_status") == "Shortlisted"]

# ─── Profile & Score Persistence ──────────────────────────────────────────

def save_candidate_profile(candidate_id: str, profile: dict):
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO hr_candidate_profiles (candidate_id, profile_json, updated_at)
            VALUES (?, ?, ?)
        """, (candidate_id, json.dumps(profile), now))

def get_candidate_profile(candidate_id: str) -> dict | None:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT profile_json FROM hr_candidate_profiles WHERE candidate_id = ?", (candidate_id,))
        row = cursor.fetchone()
        return json.loads(row["profile_json"]) if row else None

def save_candidate_score(candidate_id: str, job_id: str, final_score: float, fit_category: str, score_breakdown: dict):
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO hr_candidate_scores (candidate_id, job_id, final_score, fit_category, score_breakdown_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (candidate_id, job_id, final_score, fit_category, json.dumps(score_breakdown), now))

def get_candidate_score(candidate_id: str) -> dict | None:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hr_candidate_scores WHERE candidate_id = ?", (candidate_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["score_breakdown"] = json.loads(d["score_breakdown_json"]) if d.get("score_breakdown_json") else {}
        return d

def save_evidence_items(candidate_id: str, job_id: str, evidence_list: list[dict]):
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
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

def get_candidate_evidence(candidate_id: str) -> list[dict]:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hr_candidate_evidence WHERE candidate_id = ?", (candidate_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["matched"] = bool(d["matched"])
            result.append(d)
        return result

def get_job_leaderboard(job_id: str) -> list[dict]:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.candidate_id, c.job_id, c.name, c.email, c.filename, c.candidate_status,
                s.final_score, s.fit_category, s.score_breakdown_json,
                p.profile_json
            FROM hr_candidates c
            LEFT JOIN hr_candidate_scores s ON c.candidate_id = s.candidate_id
            LEFT JOIN hr_candidate_profiles p ON c.candidate_id = p.candidate_id
            WHERE c.job_id = ?
            ORDER BY s.final_score DESC
        """, (job_id,))
        rows = cursor.fetchall()
        leaderboard = []
        for idx, r in enumerate(rows, 1):
            d = dict(r)
            d["rank"] = idx
            d["score"] = d["final_score"] if d["final_score"] is not None else 0.0
            d["fit"] = d["fit_category"] if d["fit_category"] else "Pending"
            d["candidate_status"] = d.get("candidate_status") or "Pending"
            d["score_breakdown"] = json.loads(d["score_breakdown_json"]) if d.get("score_breakdown_json") else {}
            d["profile"] = json.loads(d["profile_json"]) if d.get("profile_json") else {}
            leaderboard.append(d)
        return leaderboard

def clear_job_data(job_id: str):
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM hr_candidates WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM hr_candidate_scores WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM hr_candidate_evidence WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM hr_jobs WHERE job_id = ?", (job_id,))
