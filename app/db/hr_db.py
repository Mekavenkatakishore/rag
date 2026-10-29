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

VALID_CANDIDATE_STATUSES = {
    "Screened",
    "Pending Approval",
    "Shortlisted (Pending Approval)",
    "Approved",
    "Rejected",
    "On Hold",
    "Shortlisted - Email Sent",
    "Approved & Email Sent",
    "Shortlisted - Email Failed",
    "Approved & Email Queued",
    "Pending",      # legacy
    "Shortlisted",  # legacy
}

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
                candidate_status TEXT NOT NULL DEFAULT 'Screened',
                approved_by      TEXT,
                approved_at      TEXT,
                hr_notes         TEXT,
                rejection_reason TEXT,
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_match_details (
                candidate_id          TEXT PRIMARY KEY,
                job_id                TEXT NOT NULL,
                overall_score         REAL NOT NULL,
                fit_category          TEXT NOT NULL,
                score_breakdown_json  TEXT NOT NULL,
                matched_skills_json   TEXT NOT NULL,
                missing_skills_json   TEXT NOT NULL,
                bonus_skills_json     TEXT NOT NULL,
                experience_match_json TEXT NOT NULL,
                criteria_results_json TEXT NOT NULL,
                summary_json          TEXT NOT NULL,
                red_flags_json        TEXT NOT NULL,
                resume_preview_text   TEXT,
                updated_at            TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_audit_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id  TEXT NOT NULL,
                job_id        TEXT NOT NULL,
                action        TEXT NOT NULL,
                performed_by  TEXT NOT NULL,
                hr_notes      TEXT,
                details_json  TEXT,
                created_at    TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT NOT NULL,
                job_id       TEXT,
                to_email     TEXT NOT NULL,
                subject      TEXT NOT NULL,
                status       TEXT NOT NULL,
                error        TEXT,
                attempts     INTEGER DEFAULT 0,
                sent_at      TEXT,
                sent_by      TEXT,
                created_at   TEXT NOT NULL
            )
        """)
        # Safe migration checks for existing DB
        for col_def in [
            "candidate_status TEXT NOT NULL DEFAULT 'Screened'",
            "approved_by TEXT",
            "approved_at TEXT",
            "hr_notes TEXT",
            "rejection_reason TEXT"
        ]:
            try:
                cursor.execute(f"ALTER TABLE hr_candidates ADD COLUMN {col_def}")
            except sqlite3.OperationalError:
                pass
        # Reset any candidate left in 'Approved' without an email log back to 'Pending Approval'
        try:
            cursor.execute("""
                UPDATE hr_candidates 
                SET candidate_status = 'Pending Approval' 
                WHERE candidate_status = 'Approved' 
                  AND candidate_id NOT IN (SELECT candidate_id FROM email_logs WHERE status IN ('SENT', 'DELIVERED', 'QUEUED'))
            """)
        except Exception:
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
            INSERT OR REPLACE INTO hr_candidates (
                candidate_id, job_id, name, email, filename, processed_status, candidate_status,
                approved_by, approved_at, hr_notes, rejection_reason, created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                COALESCE((SELECT candidate_status FROM hr_candidates WHERE candidate_id = ?), 'Screened'),
                (SELECT approved_by FROM hr_candidates WHERE candidate_id = ?),
                (SELECT approved_at FROM hr_candidates WHERE candidate_id = ?),
                (SELECT hr_notes FROM hr_candidates WHERE candidate_id = ?),
                (SELECT rejection_reason FROM hr_candidates WHERE candidate_id = ?),
                ?
            )
        """, (candidate_id, job_id, name, email, filename, status, candidate_id, candidate_id, candidate_id, candidate_id, candidate_id, now))
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

def get_candidate_by_id(candidate_id: str) -> dict | None:
    """Get a candidate record by candidate_id alone."""
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hr_candidates WHERE candidate_id = ?", (candidate_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_candidate_email(candidate_id: str, email: str) -> bool:
    """Updates candidate email address in the database."""
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE hr_candidates SET email = ? WHERE candidate_id = ?", (email.strip(), candidate_id))
        return cursor.rowcount > 0

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
        cursor.execute("DELETE FROM hr_match_details WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM hr_audit_logs WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM email_logs WHERE job_id = ?", (job_id,))
        cursor.execute("DELETE FROM hr_jobs WHERE job_id = ?", (job_id,))


# ─── Match Details & Approval Operations ──────────────────────────────────

def save_match_details(candidate_id: str, job_id: str, details: dict):
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO hr_match_details (
                candidate_id, job_id, overall_score, fit_category,
                score_breakdown_json, matched_skills_json, missing_skills_json,
                bonus_skills_json, experience_match_json, criteria_results_json,
                summary_json, red_flags_json, resume_preview_text, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            candidate_id,
            job_id,
            float(details.get("overall_score", 0.0)),
            details.get("fit_category", "Pending"),
            json.dumps(details.get("score_breakdown", {})),
            json.dumps(details.get("matched_skills", [])),
            json.dumps(details.get("missing_skills", [])),
            json.dumps(details.get("bonus_skills", [])),
            json.dumps(details.get("experience_match", {})),
            json.dumps(details.get("criteria_results", [])),
            json.dumps(details.get("summary", "")),
            json.dumps(details.get("red_flags", [])),
            details.get("resume_preview_text", ""),
            now
        ))

def get_match_details(candidate_id: str) -> dict | None:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hr_match_details WHERE candidate_id = ?", (candidate_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["score_breakdown"] = json.loads(d["score_breakdown_json"]) if d.get("score_breakdown_json") else {}
        d["matched_skills"] = json.loads(d["matched_skills_json"]) if d.get("matched_skills_json") else []
        d["missing_skills"] = json.loads(d["missing_skills_json"]) if d.get("missing_skills_json") else []
        d["bonus_skills"] = json.loads(d["bonus_skills_json"]) if d.get("bonus_skills_json") else []
        d["experience_match"] = json.loads(d["experience_match_json"]) if d.get("experience_match_json") else {}
        d["criteria_results"] = json.loads(d["criteria_results_json"]) if d.get("criteria_results_json") else []
        d["summary"] = json.loads(d["summary_json"]) if d.get("summary_json") else ""
        d["red_flags"] = json.loads(d["red_flags_json"]) if d.get("red_flags_json") else []
        return d

def record_audit_log(candidate_id: str, job_id: str, action: str, performed_by: str, hr_notes: str = None, details: dict = None) -> int:
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO hr_audit_logs (candidate_id, job_id, action, performed_by, hr_notes, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (candidate_id, job_id, action, performed_by, hr_notes or "", json.dumps(details or {}), now))
        return cursor.lastrowid

def get_audit_logs(candidate_id: str = None, job_id: str = None) -> list[dict]:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM hr_audit_logs WHERE 1=1"
        params = []
        if candidate_id:
            query += " AND candidate_id = ?"
            params.append(candidate_id)
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        query += " ORDER BY id DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        logs = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d["details_json"]) if d.get("details_json") else {}
            logs.append(d)
        return logs

def update_candidate_approval(
    candidate_id: str,
    status: str,
    approved_by: str = None,
    hr_notes: str = None,
    rejection_reason: str = None,
    job_id: str = None
) -> dict | None:
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        query = "SELECT candidate_id, job_id, email, name FROM hr_candidates WHERE candidate_id = ?"
        params = [candidate_id]
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return None
        actual_job_id = row["job_id"]
        cand_email = row["email"]
        cand_name = row["name"]

        cursor.execute("""
            UPDATE hr_candidates
            SET candidate_status = ?,
                approved_by = COALESCE(?, approved_by),
                approved_at = ?,
                hr_notes = COALESCE(?, hr_notes),
                rejection_reason = COALESCE(?, rejection_reason)
            WHERE candidate_id = ?
        """, (status, approved_by, now, hr_notes, rejection_reason, candidate_id))

    return {
        "candidate_id": candidate_id,
        "job_id": actual_job_id,
        "name": cand_name,
        "email": cand_email,
        "status": status,
        "approved_by": approved_by,
        "approved_at": now,
        "hr_notes": hr_notes,
        "rejection_reason": rejection_reason
    }

def get_shortlisted_for_approval(
    job_id: str = None,
    status_filter: str = None,
    sort_by: str = "score",
    sort_order: str = "desc",
    min_score: float = None
) -> list[dict]:
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                c.candidate_id, c.job_id, c.name, c.email, c.filename, c.candidate_status,
                c.approved_by, c.approved_at, c.hr_notes, c.rejection_reason, c.created_at,
                s.final_score, s.fit_category, s.score_breakdown_json,
                p.profile_json,
                j.title as job_title,
                m.matched_skills_json, m.missing_skills_json, m.summary_json
            FROM hr_candidates c
            LEFT JOIN hr_candidate_scores s ON c.candidate_id = s.candidate_id
            LEFT JOIN hr_candidate_profiles p ON c.candidate_id = p.candidate_id
            LEFT JOIN hr_jobs j ON c.job_id = j.job_id
            LEFT JOIN hr_match_details m ON c.candidate_id = m.candidate_id
            WHERE 1=1
        """
        params = []
        if job_id:
            query += " AND c.job_id = ?"
            params.append(job_id)

        if status_filter and status_filter.lower() != "all":
            if status_filter in ["Pending Approval", "Shortlisted (Pending Approval)"]:
                query += " AND c.candidate_status IN ('Pending Approval', 'Shortlisted (Pending Approval)', 'Shortlisted', 'Screened')"
            elif status_filter == "Approved":
                query += " AND c.candidate_status IN ('Approved', 'Approved & Email Sent', 'Shortlisted - Email Sent', 'Approved & Email Queued', 'Shortlisted - Email Failed')"
            elif status_filter in ["Email Sent", "Approved & Email Sent", "Shortlisted - Email Sent"]:
                query += " AND c.candidate_status IN ('Approved & Email Sent', 'Shortlisted - Email Sent')"
            elif status_filter in ["Email Failed", "Shortlisted - Email Failed"]:
                query += " AND c.candidate_status = 'Shortlisted - Email Failed'"
            else:
                query += " AND c.candidate_status = ?"
                params.append(status_filter)

        if min_score is not None:
            query += " AND s.final_score >= ?"
            params.append(min_score)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        candidates = []
        for idx, r in enumerate(rows, 1):
            d = dict(r)
            score = d["final_score"] if d["final_score"] is not None else 0.0
            profile = json.loads(d["profile_json"]) if d.get("profile_json") else {}
            matched_skills_from_m = json.loads(d["matched_skills_json"]) if d.get("matched_skills_json") else []
            if matched_skills_from_m and isinstance(matched_skills_from_m[0], dict):
                top_skills = [item.get("skill") for item in matched_skills_from_m if item.get("skill")]
            else:
                top_skills = profile.get("matched_required_skills", [])

            summary_str = ""
            if d.get("summary_json"):
                try:
                    summary_str = json.loads(d["summary_json"])
                except Exception:
                    summary_str = str(d["summary_json"])

            candidates.append({
                "candidate_id": d["candidate_id"],
                "job_id": d["job_id"],
                "job_title": d.get("job_title") or "Candidate Screening Role",
                "name": d["name"] or d["filename"],
                "email": d.get("email") or "Not Specified",
                "role": profile.get("title") or "Candidate",
                "filename": d["filename"],
                "status": d.get("candidate_status") or "Screened",
                "score": score,
                "fit_category": d.get("fit_category") or "Pending",
                "top_matched_skills": top_skills[:5],
                "date": d.get("created_at") or "",
                "approved_by": d.get("approved_by"),
                "approved_at": d.get("approved_at"),
                "hr_notes": d.get("hr_notes"),
                "rejection_reason": d.get("rejection_reason"),
                "summary": summary_str
            })

        reverse = (sort_order.lower() == "desc")
        if sort_by == "date":
            candidates.sort(key=lambda x: x.get("date", ""), reverse=reverse)
        elif sort_by == "name":
            candidates.sort(key=lambda x: x.get("name", "").lower(), reverse=reverse)
        else: # score
            candidates.sort(key=lambda x: x.get("score", 0.0), reverse=reverse)

        for idx, c in enumerate(candidates, 1):
            c["rank"] = idx

        return candidates


# ─── Email Logs Operations ──────────────────────────────────────────────────

def create_email_log(
    candidate_id: str,
    job_id: str | None,
    to_email: str,
    subject: str,
    sent_by: str,
    status: str = "pending",
    attempts: int = 0,
    error: str = None
) -> int:
    """Inserts a new email dispatch record into email_logs."""
    now = datetime.datetime.utcnow().isoformat()
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO email_logs (
                candidate_id, job_id, to_email, subject, status, error, attempts, sent_at, sent_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """, (candidate_id, job_id, to_email, subject, status, error, attempts, sent_by, now))
        return cursor.lastrowid

def update_email_log(
    log_id: int,
    status: str,
    error: str = None,
    attempts: int = None,
    sent_at: str = None
) -> bool:
    """Updates status, error message, attempts, or sent timestamp of an email log."""
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE email_logs
            SET status = ?,
                error = COALESCE(?, error),
                attempts = COALESCE(?, attempts),
                sent_at = COALESCE(?, sent_at)
            WHERE id = ?
        """, (status, error, attempts, sent_at, log_id))
        return cursor.rowcount > 0

def get_email_logs_for_candidate(candidate_id: str) -> list[dict]:
    """Retrieves all email logs for a specific candidate."""
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM email_logs
            WHERE candidate_id = ?
            ORDER BY id DESC
        """, (candidate_id,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def has_successful_email_sent(candidate_id: str) -> bool:
    """Returns True if an email has already been successfully sent to this candidate."""
    with get_db_connection(settings.HR_DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM email_logs
            WHERE candidate_id = ? AND status = 'sent'
            LIMIT 1
        """, (candidate_id,))
        return cursor.fetchone() is not None

