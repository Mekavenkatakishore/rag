"""
scoring_engine.py
─────────────────
Deterministic scoring calculator for candidate evaluation against Job Descriptions.
Keeps the final arithmetic free of LLM hallucination — the LLM only extracts
raw facts (skills mentioned, experience years, etc.); every point is computed
in plain Python from those facts.

Weight Model:
    Required Skills:         35%
    Relevant Experience:     20%
    Semantic JD Relevance:   15%  (embedding similarity of whole resume vs whole JD)
    Project Relevance:       10%
    Preferred Skills:        10%
    Education:                5%
    Domain Fit:                5%
                             ---
                            100%

Required/Preferred Skills matching combines two passes:
  1. Exact match, after static-dictionary normalization (fast, fully deterministic).
  2. Embedding-similarity fallback (semantic_matching_service) for JD skills that
     didn't exact-match — recovers synonyms/variants (e.g. "Postgres" vs
     "PostgreSQL") that the normalization dictionary doesn't happen to cover.

See semantic_matching_service.py for why the embedding layer was added: a thin
exact-match-only pass systematically under-counts real matches, and gave no
signal at all about whether a document is actually relevant to the JD as a
whole (which is how an unrelated document could previously still score high).
"""

from app.services.skill_normalizer import normalize_skill_list
from app.services.semantic_matching_service import (
    semantic_skill_matches,
    semantic_relevance_score,
    build_jd_text,
)

DEFAULT_WEIGHTS = {
    "required_skills": 0.35,
    "experience": 0.20,
    "semantic_relevance": 0.15,
    "project_relevance": 0.10,
    "preferred_skills": 0.10,
    "education": 0.05,
    "domain_fit": 0.05
}

def calculate_candidate_score(
    analysis_result: dict,
    jd_requirements: dict,
    weights: dict = None,
    evidence_text: str = None
) -> dict:
    """
    Calculates exact candidate match score (0-100%) and fit category using set intersection matching.

    IMPORTANT: a component is only scored when the Job Description actually specifies a
    requirement for it. A JD that lists no required/preferred skills or no minimum experience
    is MISSING DATA, not an automatically-satisfied requirement — so that component is excluded
    from the weighted average (its weight is dropped, not defaulted to 100). This prevents a
    thin/unparsed JD from producing an inflated 100% score for every candidate regardless of fit.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    active_weights = {}

    # Pool of every skill the LLM found evidence for, used as the candidate side
    # of the embedding-similarity fallback below (original casing preserved).
    matched_req = normalize_skill_list(analysis_result.get("matched_required_skills") or [])
    matched_pref = normalize_skill_list(analysis_result.get("matched_preferred_skills") or [])
    candidate_skill_pool = list({*matched_req, *matched_pref})

    # 1. Required Skills Score (35%) - exact match first, then embedding-similarity
    #    fallback for JD skills that didn't exact-match (catches synonyms/variants
    #    the normalization dictionary doesn't cover, e.g. "Postgres" vs "PostgreSQL").
    req_jd = normalize_skill_list(jd_requirements.get("required_skills") or [])
    req_jd_set = set(s.lower() for s in req_jd)
    matched_req_set = set(s.lower() for s in matched_req)

    unmatched_req = [s for s in req_jd if s.lower() not in matched_req_set]
    semantic_matched_req = semantic_skill_matches(unmatched_req, candidate_skill_pool)
    effective_matched_req_set = matched_req_set | set(s.lower() for s in semantic_matched_req)

    req_score = None
    if req_jd_set:
        matched_count = len(req_jd_set.intersection(effective_matched_req_set))
        req_score = min(100.0, (matched_count / len(req_jd_set)) * 100.0)
        active_weights["required_skills"] = weights["required_skills"]

    # 2. Preferred Skills Score (10%) - same exact + semantic approach
    pref_jd = normalize_skill_list(jd_requirements.get("preferred_skills") or [])
    pref_jd_set = set(s.lower() for s in pref_jd)
    matched_pref_set = set(s.lower() for s in matched_pref)

    unmatched_pref = [s for s in pref_jd if s.lower() not in matched_pref_set]
    semantic_matched_pref = semantic_skill_matches(unmatched_pref, candidate_skill_pool)
    effective_matched_pref_set = matched_pref_set | set(s.lower() for s in semantic_matched_pref)

    pref_score = None
    if pref_jd_set:
        matched_pref_count = len(pref_jd_set.intersection(effective_matched_pref_set))
        pref_score = min(100.0, (matched_pref_count / len(pref_jd_set)) * 100.0)
        active_weights["preferred_skills"] = weights["preferred_skills"]

    # 3. Experience Score (20%) - only scored when the JD specifies a minimum
    min_exp = float(jd_requirements.get("min_experience_years", 0) or 0)
    cand_exp = float(analysis_result.get("experience_years", 0) or 0)

    exp_score = None
    if min_exp > 0:
        exp_score = 100.0 if cand_exp >= min_exp else (cand_exp / min_exp) * 100.0
        active_weights["experience"] = weights["experience"]

    # 3b. Semantic JD Relevance Score (15%) - whole-resume vs whole-JD embedding
    #     similarity. Independent of any single skill: this is what catches a
    #     document that simply isn't a relevant resume at all, instead of only
    #     ever checking individual keyword/skill overlap.
    semantic_score = semantic_relevance_score(build_jd_text(jd_requirements), evidence_text or "")
    if semantic_score is not None:
        active_weights["semantic_relevance"] = weights["semantic_relevance"]

    # 4. Project Relevance Score (10%) - candidate-side signal, defaults to a neutral/low value
    proj_rel = str(analysis_result.get("project_relevance") or "Not Specified").lower()
    if "high" in proj_rel or "strong" in proj_rel or "excellent" in proj_rel:
        proj_score = 100.0
    elif "medium" in proj_rel or "moderate" in proj_rel or "good" in proj_rel:
        proj_score = 70.0
    else:
        proj_score = 30.0
    active_weights["project_relevance"] = weights["project_relevance"]

    # 5. Education Score (5%) - missing/unknown defaults to NOT satisfied, not satisfied
    edu_fit = analysis_result.get("education_fit", False)
    edu_score = 100.0 if bool(edu_fit) else 40.0
    active_weights["education"] = weights["education"]

    # 6. Domain Fit Score (5%) - missing/unknown defaults to the lowest bucket
    domain_fit = str(analysis_result.get("experience_fit") or "Unknown").lower()
    if "meets" in domain_fit or "exceeds" in domain_fit or "strong" in domain_fit:
        domain_score = 100.0
    elif "partial" in domain_fit:
        domain_score = 60.0
    else:
        domain_score = 30.0
    active_weights["domain_fit"] = weights["domain_fit"]

    component_scores = {
        "required_skills": req_score,
        "preferred_skills": pref_score,
        "experience": exp_score,
        "semantic_relevance": semantic_score,
        "project_relevance": proj_score,
        "education": edu_score,
        "domain_fit": domain_score,
    }

    total_active_weight = sum(active_weights.values())
    if total_active_weight <= 0:
        # The JD specified no required/preferred skills and no minimum experience at all —
        # there is nothing meaningful to score this candidate against.
        final_score = 0.0
        fit_category = "Insufficient JD Data"
    else:
        weighted_sum = sum(component_scores[name] * w for name, w in active_weights.items())
        # Re-normalize so a JD with missing components still produces a 0-100 score
        # based only on the requirements it actually specifies.
        final_score = round(min(100.0, max(0.0, weighted_sum / total_active_weight)), 1)

        if final_score >= 80.0:
            fit_category = "Strong Fit"
        elif final_score >= 60.0:
            fit_category = "Moderate Fit"
        else:
            fit_category = "Weak Fit"

    score_breakdown = {
        "required_skills_score": round(req_score, 1) if req_score is not None else None,
        "preferred_skills_score": round(pref_score, 1) if pref_score is not None else None,
        "experience_score": round(exp_score, 1) if exp_score is not None else None,
        "semantic_relevance_score": semantic_score,
        "project_score": round(proj_score, 1),
        "education_score": round(edu_score, 1),
        "domain_score": round(domain_score, 1),
        "weights": weights,
        "active_weights": active_weights,
        "jd_missing_required_skills": req_score is None,
        "jd_missing_preferred_skills": pref_score is None,
        "jd_missing_min_experience": exp_score is None,
        "jd_missing_semantic_relevance": semantic_score is None,
        # Transparency: which matches came from exact/dictionary matching vs the
        # embedding-similarity fallback, so a recruiter can see why a skill counted.
        "semantically_matched_required_skills": sorted(semantic_matched_req),
        "semantically_matched_preferred_skills": sorted(semantic_matched_pref),
    }

    return {
        "final_score": final_score,
        "fit_category": fit_category,
        "score_breakdown": score_breakdown
    }
