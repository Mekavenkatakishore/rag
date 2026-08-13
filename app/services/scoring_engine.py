"""
scoring_engine.py
─────────────────
Deterministic scoring calculator for candidate evaluation against Job Descriptions.
Ensures zero LLM hallucination in percentage scores.

Weight Model:
    Required Skills:       40%
    Relevant Experience:   25%
    Project Relevance:     15%
    Preferred Skills:      10%
    Education:              5%
    Domain Fit:             5%
                           ---
                          100%
"""

from app.services.skill_normalizer import normalize_skill_list

DEFAULT_WEIGHTS = {
    "required_skills": 0.40,
    "experience": 0.25,
    "project_relevance": 0.15,
    "preferred_skills": 0.10,
    "education": 0.05,
    "domain_fit": 0.05
}

def calculate_candidate_score(
    analysis_result: dict, 
    jd_requirements: dict, 
    weights: dict = None
) -> dict:
    """
    Calculates deterministic candidate match score and fit category.
    
    Args:
        analysis_result: Candidate LLM extraction output containing matched/missing skills, experience, etc.
        jd_requirements: Parsed Job Description dictionary containing required/preferred skills and min experience.
        weights: Optional custom weight overrides.
        
    Returns:
        dict containing final_score (0-100), fit_category, and detailed score_breakdown.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # 1. Required Skills Score (40%)
    req_jd = normalize_skill_list(jd_requirements.get("required_skills", []))
    matched_req = normalize_skill_list(analysis_result.get("matched_required_skills", []))
    
    if req_jd:
        # Number of matched required skills divided by total required skills
        req_score = min(100.0, (len(matched_req) / len(req_jd)) * 100.0)
    else:
        req_score = 100.0

    # 2. Preferred Skills Score (10%)
    pref_jd = normalize_skill_list(jd_requirements.get("preferred_skills", []))
    matched_pref = normalize_skill_list(analysis_result.get("matched_preferred_skills", []))
    
    if pref_jd:
        pref_score = min(100.0, (len(matched_pref) / len(pref_jd)) * 100.0)
    else:
        pref_score = 100.0

    # 3. Experience Score (25%)
    min_exp = float(jd_requirements.get("min_experience_years", 0) or 0)
    cand_exp = float(analysis_result.get("experience_years", 0) or 0)
    
    if min_exp <= 0:
        exp_score = 100.0
    elif cand_exp >= min_exp:
        # Full score if meets or exceeds minimum required years
        exp_score = 100.0
    else:
        # Partial credit proportional to experience found
        exp_score = (cand_exp / min_exp) * 100.0

    # 4. Project Relevance Score (15%)
    proj_rel = str(analysis_result.get("project_relevance", "Moderate")).lower()
    if "high" in proj_rel:
        proj_score = 100.0
    elif "medium" in proj_rel or "moderate" in proj_rel:
        proj_score = 70.0
    else:
        proj_score = 30.0

    # 5. Education Score (5%)
    edu_fit = analysis_result.get("education_fit", True)
    edu_score = 100.0 if edu_fit else 40.0

    # 6. Domain Fit Score (5%)
    domain_fit = str(analysis_result.get("experience_fit", "Meets")).lower()
    if "meets" in domain_fit or "exceeds" in domain_fit:
        domain_score = 100.0
    elif "partial" in domain_fit:
        domain_score = 60.0
    else:
        domain_score = 30.0

    # Calculate Weighted Final Score
    weighted_score = (
        req_score * weights["required_skills"] +
        exp_score * weights["experience"] +
        proj_score * weights["project_relevance"] +
        pref_score * weights["preferred_skills"] +
        edu_score * weights["education"] +
        domain_score * weights["domain_fit"]
    )

    final_score = round(min(100.0, max(0.0, weighted_score)), 1)

    # Assign Fit Category
    if final_score >= 80.0:
        fit_category = "Strong Fit"
    elif final_score >= 60.0:
        fit_category = "Moderate Fit"
    else:
        fit_category = "Weak Fit"

    score_breakdown = {
        "required_skills_score": round(req_score, 1),
        "preferred_skills_score": round(pref_score, 1),
        "experience_score": round(exp_score, 1),
        "project_score": round(proj_score, 1),
        "education_score": round(edu_score, 1),
        "domain_score": round(domain_score, 1),
        "weights": weights
    }

    return {
        "final_score": final_score,
        "fit_category": fit_category,
        "score_breakdown": score_breakdown
    }
