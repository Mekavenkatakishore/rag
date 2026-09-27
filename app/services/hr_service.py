"""
hr_service.py (Facade Wrapper for Backward Compatibility)
───────────────────────────────────────────────────────
Forwards calls to app.services.hr package.
"""

from app.services.hr import (
    extract_text_from_file,
    parse_job_description,
    process_single_resume,
    RESUME_DIR,
    JD_DIR,
    normalize_skill,
    normalize_skill_list,
    calculate_candidate_score,
    retrieve_candidate_evidence,
    analyze_and_score_candidate,
    analyze_all_job_candidates,
    clear_hr_session,
)

__all__ = [
    "extract_text_from_file",
    "parse_job_description",
    "process_single_resume",
    "RESUME_DIR",
    "JD_DIR",
    "normalize_skill",
    "normalize_skill_list",
    "calculate_candidate_score",
    "retrieve_candidate_evidence",
    "analyze_and_score_candidate",
    "analyze_all_job_candidates",
    "clear_hr_session",
]
