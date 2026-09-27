import os
import json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.llm_factory import get_llm
from app.db import hr_db
from app.services.hr.jd_parser_service import extract_text_from_file
from app.services.hr.skill_normalization_service import normalize_skill_list
from app.services.hr.scoring_service import calculate_candidate_score
from app.services.hr.evidence_service import retrieve_candidate_evidence
from app.utils.logger import logger

RESUME_DIR = os.path.join(settings.UPLOAD_DIR, "resumes")
JD_DIR = os.path.join(settings.UPLOAD_DIR, "jd")

def analyze_and_score_candidate(job_id: str, candidate_id: str, candidate_name: str, filename: str, jd_requirements: dict) -> dict:
    """Evaluates candidate evidence chunks, computes score, and updates DB."""
    llm = get_llm(temperature=0.1)

    evidence_docs = retrieve_candidate_evidence(job_id, candidate_id, jd_requirements)
    combined_evidence_text = "\n\n".join([
        f"[Source: {doc.metadata.get('document', filename)}, Page {doc.metadata.get('page', 1)}]\n{doc.page_content}"
        for doc in evidence_docs
    ])
    
    if not combined_evidence_text or len(combined_evidence_text.strip()) < 50:
        raw_path = os.path.join(RESUME_DIR, f"{job_id}_{candidate_id}_{filename}")
        combined_evidence_text = extract_text_from_file(raw_path)[:4000]

    normalized_req_skills = normalize_skill_list(jd_requirements.get("required_skills", []))
    normalized_pref_skills = normalize_skill_list(jd_requirements.get("preferred_skills", []))

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an elite HR Talent Acquisition Auditor.
Your task is to accurately evaluate Candidate Resume Evidence against Job Description requirements.

CRITICAL INSTRUCTIONS:
1. Compare the Candidate Resume Evidence Text strictly against the provided Required Skills List.
2. If a skill from the Required Skills List is explicitly mentioned or demonstrated in the resume, place it in `matched_required_skills`.
3. If a skill from the Required Skills List is missing or NOT mentioned in the resume, place it in `missing_required_skills`.
4. Do NOT place skills in `matched_required_skills` if they are missing from the candidate resume.
5. Do NOT invent skills that are not present in the resume.
6. Extract location, notice_period, availability, ctc ONLY if explicitly mentioned in resume. If missing, set to "Not Specified".
7. Extract projects, work_history, and education_details found in resume.
8. Return ONLY valid JSON format."""),
        ("user", """Analyze candidate resume evidence against this Job Description.

Job Title: {jd_title}
Required Skills List: {required_skills}
Preferred Skills List: {preferred_skills}
Min Experience Years Required: {min_experience_years}

Candidate Resume Evidence Text:
{evidence_text}

Return ONLY a JSON object formatted exactly as:
{{
  "candidate_name": "{candidate_name}",
  "title": "Current Job Title or Role from Resume",
  "location": "Candidate Location or Not Specified",
  "notice_period": "Notice Period or Not Specified",
  "availability": "Availability or Not Specified",
  "ctc": "Current/Expected CTC or Not Specified",
  "matched_required_skills": ["Skill1"],
  "missing_required_skills": ["Skill2"],
  "matched_preferred_skills": ["SkillA"],
  "missing_preferred_skills": ["SkillB"],
  "experience_years": 5.0,
  "experience_fit": "Meets requirement",
  "project_relevance": "High",
  "education_fit": true,
  "education_details": ["Degree, Major, Institution"],
  "work_history": ["Company, Role, Dates, Summary"],
  "projects": ["Project Name - Technologies used & description"],
  "evidence_items": [
    {{
      "skill": "Python",
      "matched": true,
      "evidence": "Exact quote or brief summary from text",
      "document": "{filename}",
      "page": 1
    }}
  ]
}}
""")
    ])

    chain = prompt | llm | StrOutputParser()
    try:
        response_text = chain.invoke({
            "jd_title": jd_requirements.get("title", "Role"),
            "required_skills": ", ".join(normalized_req_skills),
            "preferred_skills": ", ".join(normalized_pref_skills),
            "min_experience_years": jd_requirements.get("min_experience_years", 0),
            "evidence_text": combined_evidence_text[:4000],
            "candidate_name": candidate_name,
            "filename": filename
        })
        clean_text = response_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        analysis = json.loads(clean_text)
    except Exception as e:
        logger.error(f"Error in LLM candidate evidence analysis: {e}")
        analysis = {
            "candidate_name": candidate_name,
            "title": "Software Engineer",
            "location": "Not Specified",
            "notice_period": "Not Specified",
            "availability": "Not Specified",
            "ctc": "Not Specified",
            "matched_required_skills": [],
            "missing_required_skills": normalized_req_skills,
            "matched_preferred_skills": [],
            "missing_preferred_skills": normalized_pref_skills,
            "experience_years": 0.0,
            "experience_fit": "Unknown",
            "project_relevance": "Low",
            "education_fit": True,
            "education_details": [],
            "work_history": [],
            "projects": [],
            "evidence_items": []
        }

    # Normalize extracted skill lists
    matched_req = normalize_skill_list(analysis.get("matched_required_skills", []))
    matched_pref = normalize_skill_list(analysis.get("matched_preferred_skills", []))

    # Clean up missing required skills so they accurately reflect what wasn't matched
    matched_req_set = set(s.lower() for s in matched_req)
    missing_req = [s for s in normalized_req_skills if s.lower() not in matched_req_set]

    matched_pref_set = set(s.lower() for s in matched_pref)
    missing_pref = [s for s in normalized_pref_skills if s.lower() not in matched_pref_set]

    analysis["matched_required_skills"] = matched_req
    analysis["missing_required_skills"] = missing_req
    analysis["matched_preferred_skills"] = matched_pref
    analysis["missing_preferred_skills"] = missing_pref
    analysis["document"] = filename

    # Calculate Deterministic Match Score (100% Python Application Math)
    jd_req_normalized = {**jd_requirements, "required_skills": normalized_req_skills, "preferred_skills": normalized_pref_skills}
    scoring_result = calculate_candidate_score(analysis, jd_req_normalized)
    final_score = scoring_result["final_score"]
    fit_category = scoring_result["fit_category"]
    score_breakdown = scoring_result["score_breakdown"]

    hr_db.save_candidate_profile(candidate_id, analysis)
    hr_db.save_candidate_score(candidate_id, job_id, final_score, fit_category, score_breakdown)
    hr_db.save_evidence_items(candidate_id, job_id, analysis.get("evidence_items", []))

    return {
        "candidate_id": candidate_id,
        "name": candidate_name,
        "filename": filename,
        "score": final_score,
        "fit": fit_category,
        "score_breakdown": score_breakdown,
        "analysis": analysis
    }

def analyze_all_job_candidates(job_id: str) -> list[dict]:
    """Evaluates and scores all candidates belonging to a job_id."""
    job = hr_db.get_job(job_id)
    if not job:
        raise ValueError(f"Job ID '{job_id}' not found.")
        
    jd_requirements = job.get("jd_parsed", {})
    candidates = hr_db.get_job_candidates(job_id)
    
    results = []
    for cand in candidates:
        cand_id = cand["candidate_id"]
        filename = cand["filename"]
        name = cand["name"] or filename
        
        evaluated = analyze_and_score_candidate(job_id, cand_id, name, filename, jd_requirements)
        results.append(evaluated)
        
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def clear_hr_session(job_id: str):
    """Deletes uploaded files and database entries for job_id."""
    for folder in [JD_DIR, RESUME_DIR]:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                if job_id in f:
                    try:
                        os.remove(os.path.join(folder, f))
                    except Exception:
                        pass
    hr_db.clear_job_data(job_id)
