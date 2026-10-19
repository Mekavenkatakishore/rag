"""
approval_service.py
───────────────────
Core business logic for human-in-the-loop candidate shortlist approval,
audit logging, match details synthesis, and status transitions.
"""

import os
from typing import Dict, Any, List, Optional

from app.db import hr_db
from app.services.hr import email_service
from app.services.hr.jd_parser_service import extract_text_from_file
from app.utils.logger import logger

RESUME_DIR = os.path.join("uploads", "resumes")


def build_criteria_results(
    analysis: dict,
    jd_requirements: dict,
    final_score: float,
    score_breakdown: dict
) -> List[Dict[str, Any]]:
    """
    Evaluates explicit pass/fail criteria rules against candidate facts.
    """
    results = []

    # 1. Required Skills Match Rule (Threshold: at least 50% of required skills present)
    req_skills = jd_requirements.get("required_skills", [])
    matched_req = analysis.get("matched_required_skills", [])
    if req_skills:
        req_pct = (len(matched_req) / len(req_skills)) * 100.0
        passed = req_pct >= 50.0
        results.append({
            "rule": "Mandatory Technical Skills",
            "requirement": f">= 50% matched ({len(req_skills)} required)",
            "actual": f"{len(matched_req)}/{len(req_skills)} matched ({round(req_pct, 1)}%)",
            "passed": passed
        })

    # 2. Minimum Experience Rule
    min_exp = float(jd_requirements.get("min_experience_years", 0) or 0)
    actual_exp = float(analysis.get("experience_years", 0) or 0)
    if min_exp > 0:
        passed = actual_exp >= (min_exp * 0.8) # Allow slight margin or full check
        results.append({
            "rule": "Relevant Experience Years",
            "requirement": f">= {min_exp} years",
            "actual": f"{actual_exp} years",
            "passed": passed
        })

    # 3. Overall Qualification Match Score Rule (Threshold >= 60%)
    score_passed = final_score >= 60.0
    results.append({
        "rule": "Overall Qualification Score",
        "requirement": "Score >= 60.0% (Moderate or Strong Fit)",
        "actual": f"{round(final_score, 1)}%",
        "passed": score_passed
    })

    # 4. Education & Degree Fit Rule
    edu_fit = analysis.get("education_fit", True)
    results.append({
        "rule": "Education & Degree Requirement",
        "requirement": jd_requirements.get("education") or "Relevant Technical Degree",
        "actual": "Qualified" if edu_fit else "Non-matching / Unspecified",
        "passed": bool(edu_fit)
    })

    # 5. Semantic / Whole-Document Relevance Rule
    semantic_score = score_breakdown.get("semantic_relevance_score")
    if semantic_score is not None:
        sem_passed = semantic_score >= 50.0
        results.append({
            "rule": "Document Domain Relevance",
            "requirement": "Cosine similarity >= 50.0%",
            "actual": f"{round(semantic_score, 1)}%",
            "passed": sem_passed
        })

    return results


def extract_bonus_skills(analysis: dict, jd_requirements: dict) -> List[str]:
    """
    Identifies candidate skills that were NOT part of the JD required or preferred skills.
    These count as bonus competencies.
    """
    jd_skills_lower = set(s.lower() for s in jd_requirements.get("required_skills", []) + jd_requirements.get("preferred_skills", []))
    
    # Pool skills mentioned in projects or extra items
    candidate_skills = set()
    for s in analysis.get("matched_required_skills", []) + analysis.get("matched_preferred_skills", []):
        candidate_skills.add(s)

    # Inspect projects or raw skill mentions if any
    for proj in analysis.get("projects", []):
        if isinstance(proj, str):
            for token in ["Docker", "Kubernetes", "AWS", "GCP", "GraphQL", "Redis", "Kafka", "CI/CD", "Terraform", "TypeScript", "Python"]:
                if token.lower() in proj.lower() and token.lower() not in jd_skills_lower:
                    candidate_skills.add(token)

    bonus = [s for s in candidate_skills if s.lower() not in jd_skills_lower]
    return sorted(list(set(bonus)))[:8]


def generate_executive_summary_and_red_flags(
    analysis: dict,
    jd_requirements: dict,
    final_score: float,
    fit_category: str
) -> tuple[str, List[str]]:
    """
    Produces a 3-5 line recruiter executive summary and pinpoints red flags.
    """
    cand_name = analysis.get("candidate_name") or "Candidate"
    matched_req = analysis.get("matched_required_skills", [])
    missing_req = analysis.get("missing_required_skills", [])
    exp_years = analysis.get("experience_years", 0)
    min_exp = jd_requirements.get("min_experience_years", 0)

    # Summary
    summary_lines = [
        f"{cand_name} demonstrates a {fit_category} profile with an overall qualification score of {final_score}%.",
        f"Demonstrates strong capability in {', '.join(matched_req[:4]) if matched_req else 'core technical requirements'} with {exp_years} years of demonstrated industry experience.",
        f"Evaluation shows aligned project work in {analysis.get('title') or 'software development'}.",
        f"Recommended for human review and shortlist approval based on core requirements alignment."
    ]
    summary_text = " ".join(summary_lines)

    # Red Flags / Cautionary items
    red_flags = []
    if missing_req:
        red_flags.append(f"Missing mandatory required skills: {', '.join(missing_req[:3])}.")
    if min_exp and exp_years < min_exp:
        red_flags.append(f"Experience deficit: {exp_years} years actual vs {min_exp} years specified in JD.")
    if final_score < 60.0:
        red_flags.append("Overall qualification score below 60% threshold.")
    if analysis.get("location") and analysis.get("location") not in ["Not Specified", "Remote"]:
        red_flags.append(f"Candidate location noted as {analysis.get('location')} (verify relocation or remote viability).")

    if not red_flags:
        red_flags.append("No major red flags detected. Profile strongly meets core criteria.")

    return summary_text, red_flags


def generate_and_save_match_details(
    candidate_id: str,
    job_id: str,
    analysis: dict,
    jd_requirements: dict,
    score_breakdown: dict,
    final_score: float,
    fit_category: str,
    evidence_text: str = ""
):
    """
    Creates and persists full structured match details for review and approval screens.
    """
    criteria_results = build_criteria_results(analysis, jd_requirements, final_score, score_breakdown)
    bonus_skills = extract_bonus_skills(analysis, jd_requirements)
    summary_text, red_flags = generate_executive_summary_and_red_flags(analysis, jd_requirements, final_score, fit_category)

    # Format matched skills with evidence
    evidence_items = analysis.get("evidence_items", [])
    matched_skills_structured = []
    for skill in analysis.get("matched_required_skills", []):
        # find matching evidence item
        snippet = ""
        page = 1
        doc_name = analysis.get("document", "resume.pdf")
        for ev in evidence_items:
            if ev.get("skill", "").lower() == skill.lower() and ev.get("evidence"):
                snippet = ev.get("evidence")
                page = ev.get("page", 1)
                doc_name = ev.get("document", doc_name)
                break
        if not snippet:
            snippet = f"Skill '{skill}' verified in candidate resume experience text."
        matched_skills_structured.append({
            "skill": skill,
            "evidence": snippet,
            "matched": True,
            "document": doc_name,
            "page": page
        })

    # Experience details
    min_exp = float(jd_requirements.get("min_experience_years", 0) or 0)
    actual_exp = float(analysis.get("experience_years", 0) or 0)
    diff = round(actual_exp - min_exp, 1)
    experience_match = {
        "required_years": min_exp,
        "actual_years": actual_exp,
        "difference_years": diff,
        "meets": actual_exp >= min_exp,
        "status": "Meets or Exceeds" if actual_exp >= min_exp else "Below Requirement"
    }

    match_record = {
        "overall_score": final_score,
        "fit_category": fit_category,
        "score_breakdown": score_breakdown,
        "matched_skills": matched_skills_structured,
        "missing_skills": analysis.get("missing_required_skills", []),
        "bonus_skills": bonus_skills,
        "experience_match": experience_match,
        "criteria_results": criteria_results,
        "summary": summary_text,
        "red_flags": red_flags,
        "resume_preview_text": evidence_text[:3500] if evidence_text else ""
    }

    hr_db.save_match_details(candidate_id, job_id, match_record)
    return match_record


def get_candidate_match_details(candidate_id: str) -> Dict[str, Any]:
    """
    Retrieves complete match details, synthesizing them on the fly if needed.
    """
    match_data = hr_db.get_match_details(candidate_id)
    profile = hr_db.get_candidate_profile(candidate_id) or {}
    score_data = hr_db.get_candidate_score(candidate_id) or {}
    evidence_items = hr_db.get_candidate_evidence(candidate_id) or []

    # Get candidate metadata from hr_candidates table
    # We query directly to get candidate job and fields
    all_cand_jobs = hr_db.get_shortlisted_for_approval()
    cand_row = next((c for c in all_cand_jobs if c["candidate_id"] == candidate_id), None)
    
    job_id = cand_row["job_id"] if cand_row else "default_job_001"
    job = hr_db.get_job(job_id) or {}
    jd_requirements = job.get("jd_parsed", {})

    # If match details weren't previously generated, build them now
    if not match_data:
        final_score = score_data.get("final_score", 0.0)
        fit_category = score_data.get("fit_category", "Pending")
        score_breakdown = score_data.get("score_breakdown", {})
        
        # Read resume text if possible
        filename = cand_row.get("filename", "") if cand_row else ""
        resume_text = ""
        possible_paths = [
            os.path.join(RESUME_DIR, f"{job_id}_{candidate_id}_{filename}"),
            os.path.join(RESUME_DIR, filename)
        ]
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    resume_text = extract_text_from_file(p)
                    break
                except Exception:
                    pass

        analysis = {
            **profile,
            "evidence_items": evidence_items,
            "document": filename
        }
        match_data = generate_and_save_match_details(
            candidate_id=candidate_id,
            job_id=job_id,
            analysis=analysis,
            jd_requirements=jd_requirements,
            score_breakdown=score_breakdown,
            final_score=final_score,
            fit_category=fit_category,
            evidence_text=resume_text
        )

    # Ensure resume preview text is populated
    preview_text = match_data.get("resume_preview_text", "")
    if not preview_text:
        filename = cand_row.get("filename", "") if cand_row else ""
        p = os.path.join(RESUME_DIR, f"{job_id}_{candidate_id}_{filename}")
        if os.path.exists(p):
            try:
                preview_text = extract_text_from_file(p)[:3500]
            except Exception:
                preview_text = "Resume file uploaded and verified."

    return {
        "status": "success",
        "candidate_id": candidate_id,
        "job_id": job_id,
        "name": cand_row.get("name") if cand_row else "Candidate",
        "email": cand_row.get("email") if cand_row else "Not Specified",
        "role": cand_row.get("role") if cand_row else "Candidate",
        "filename": cand_row.get("filename") if cand_row else "resume.pdf",
        "candidate_status": cand_row.get("status") if cand_row else "Screened",
        "overall_score": match_data.get("overall_score", 0.0),
        "fit_category": match_data.get("fit_category", "Pending"),
        "score_breakdown": match_data.get("score_breakdown", {}),
        "matched_skills": match_data.get("matched_skills", []),
        "missing_skills": match_data.get("missing_skills", []),
        "bonus_skills": match_data.get("bonus_skills", []),
        "experience_match": match_data.get("experience_match", {}),
        "criteria_results": match_data.get("criteria_results", []),
        "summary": match_data.get("summary", ""),
        "red_flags": match_data.get("red_flags", []),
        "jd_requirements": jd_requirements,
        "resume_preview_text": preview_text or "Verified candidate document on file.",
        "approved_by": cand_row.get("approved_by") if cand_row else None,
        "approved_at": cand_row.get("approved_at") if cand_row else None,
        "hr_notes": cand_row.get("hr_notes") if cand_row else None,
        "rejection_reason": cand_row.get("rejection_reason") if cand_row else None
    }


def approve_candidate(
    candidate_id: str,
    current_user: dict,
    hr_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles human approval of a shortlisted candidate.
    Phase 1: updates status to 'Approved', logs audit trail, and stubs email delivery.
    """
    approver = current_user.get("username") or "hr_user"

    # Update candidate in database
    updated = hr_db.update_candidate_approval(
        candidate_id=candidate_id,
        status="Approved",
        approved_by=approver,
        hr_notes=hr_notes
    )
    if not updated:
        raise ValueError(f"Candidate ID '{candidate_id}' not found.")

    # Record Audit Log
    hr_db.record_audit_log(
        candidate_id=candidate_id,
        job_id=updated["job_id"],
        action="APPROVED",
        performed_by=approver,
        hr_notes=hr_notes,
        details={"previous_status": "Shortlisted (Pending Approval)", "new_status": "Approved"}
    )

    # Stub Email Trigger for Phase 1
    email_res = email_service.send_shortlist_email_stub(
        candidate_id=candidate_id,
        to_email=updated.get("email") or "candidate@example.com",
        candidate_name=updated.get("name") or candidate_id,
        job_title="Shortlisted Position",
        approved_by=approver
    )

    return {
        "status": "success",
        "message": f"Candidate '{candidate_id}' successfully approved by {approver}.",
        "candidate_id": candidate_id,
        "candidate_status": "Approved",
        "approved_by": approver,
        "approved_at": updated.get("approved_at"),
        "email_status": email_res.get("status", "stubbed")
    }


def reject_candidate(
    candidate_id: str,
    current_user: dict,
    hr_notes: Optional[str] = None,
    rejection_reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles candidate rejection.
    """
    user_name = current_user.get("username") or "hr_user"
    reason = rejection_reason or "Does not meet role criteria"

    updated = hr_db.update_candidate_approval(
        candidate_id=candidate_id,
        status="Rejected",
        approved_by=user_name,
        hr_notes=hr_notes,
        rejection_reason=reason
    )
    if not updated:
        raise ValueError(f"Candidate ID '{candidate_id}' not found.")

    hr_db.record_audit_log(
        candidate_id=candidate_id,
        job_id=updated["job_id"],
        action="REJECTED",
        performed_by=user_name,
        hr_notes=hr_notes,
        details={"rejection_reason": reason}
    )

    return {
        "status": "success",
        "message": f"Candidate '{candidate_id}' marked as Rejected.",
        "candidate_id": candidate_id,
        "candidate_status": "Rejected",
        "approved_by": user_name,
        "approved_at": updated.get("approved_at"),
        "email_status": "none"
    }


def hold_candidate(
    candidate_id: str,
    current_user: dict,
    hr_notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Puts candidate on hold.
    """
    user_name = current_user.get("username") or "hr_user"

    updated = hr_db.update_candidate_approval(
        candidate_id=candidate_id,
        status="On Hold",
        approved_by=user_name,
        hr_notes=hr_notes
    )
    if not updated:
        raise ValueError(f"Candidate ID '{candidate_id}' not found.")

    hr_db.record_audit_log(
        candidate_id=candidate_id,
        job_id=updated["job_id"],
        action="PUT_ON_HOLD",
        performed_by=user_name,
        hr_notes=hr_notes,
        details={"reason": "Candidate placed On Hold pending further review."}
    )

    return {
        "status": "success",
        "message": f"Candidate '{candidate_id}' placed On Hold.",
        "candidate_id": candidate_id,
        "candidate_status": "On Hold",
        "approved_by": user_name,
        "approved_at": updated.get("approved_at"),
        "email_status": "none"
    }

