import json
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.services import hr_service
from app.db import hr_db
from app.agent.llm import get_llm
from app.utils.logger import logger

llm = get_llm(temperature=0.2)

@tool
def match_candidates(job_id: str) -> str:
    """
    Evaluates and scores all uploaded candidate resumes for a specific Job ID using hybrid evidence retrieval,
    FlashRank reranking, and 100% deterministic math scoring (0-100%).
    Returns a ranked candidate leaderboard.
    """
    logger.info(f"Agent executing tool 'match_candidates' for job_id: '{job_id}'")
    try:
        leaderboard = hr_service.analyze_all_job_candidates(job_id)
        if not leaderboard:
            return f"No candidate resumes found or evaluated for job_id '{job_id}'."
            
        summary = f"Evaluated {len(leaderboard)} candidate(s) for job_id '{job_id}':\n\n"
        for c in leaderboard[:5]:
            summary += f"- Rank #{c['rank']}: {c['name']} | Score: {c['score']}% ({c['fit']})\n"
            profile = c.get("profile", {})
            summary += f"  Matched Required Skills: {', '.join(profile.get('matched_required_skills', []))}\n"
            summary += f"  Missing Required Skills: {', '.join(profile.get('missing_required_skills', []))}\n\n"
            
        return summary
    except Exception as e:
        logger.error(f"Error in match_candidates tool: {e}")
        return f"Error matching candidates: {e}"

@tool
def get_candidate_details(candidate_id: str) -> str:
    """
    Fetches stored candidate profile, final deterministic score, category fit breakdown, and matched/missing skills.
    """
    logger.info(f"Agent executing tool 'get_candidate_details' for candidate_id: '{candidate_id}'")
    try:
        score_data = hr_db.get_candidate_score(candidate_id)
        profile_data = hr_db.get_candidate_profile(candidate_id)
        
        if not score_data and not profile_data:
            return f"Candidate '{candidate_id}' not found."
            
        profile = profile_data or {}
        score = score_data.get("final_score", 0.0) if score_data else 0.0
        fit = score_data.get("fit_category", "Pending") if score_data else "Pending"
        
        res = f"Candidate ID: {candidate_id}\n"
        res += f"Name: {profile.get('candidate_name', candidate_id)}\n"
        res += f"Match Score: {score}% ({fit})\n"
        res += f"Experience Years: {profile.get('experience_years', 'N/A')}\n"
        res += f"Matched Skills: {', '.join(profile.get('matched_required_skills', []))}\n"
        res += f"Missing Skills: {', '.join(profile.get('missing_required_skills', []))}\n"
        return res
    except Exception as e:
        logger.error(f"Error in get_candidate_details tool: {e}")
        return f"Error fetching candidate details: {e}"

@tool
def get_candidate_evidence(candidate_id: str) -> str:
    """
    Fetches exact resume text quotes and page citations supporting a candidate's skill evaluations.
    """
    logger.info(f"Agent executing tool 'get_candidate_evidence' for candidate_id: '{candidate_id}'")
    try:
        evidence = hr_db.get_candidate_evidence(candidate_id)
        if not evidence:
            return f"No supporting quotes/evidence stored for candidate '{candidate_id}'."
            
        res = f"Evidence Quotes for Candidate '{candidate_id}':\n\n"
        for item in evidence[:6]:
            match_status = "Matched" if item.get("matched") else "Missing"
            res += f"- Skill: {item.get('skill')} [{match_status}]\n"
            res += f"  Quote: \"{item.get('evidence_quote', '')}\"\n"
            res += f"  Source: {item.get('document', '')} (Page {item.get('page', 1)})\n\n"
            
        return res
    except Exception as e:
        logger.error(f"Error in get_candidate_evidence tool: {e}")
        return f"Error fetching evidence: {e}"

@tool
def generate_interview_questions(job_id: str, candidate_id: str) -> str:
    """
    Generates targeted technical, behavioral, and experience interview questions for a specific candidate
    based on their matched and missing skills.
    """
    logger.info(f"Agent executing tool 'generate_interview_questions' for candidate_id: '{candidate_id}'")
    try:
        job = hr_db.get_job(job_id)
        profile = hr_db.get_candidate_profile(candidate_id) or {}
        score_data = hr_db.get_candidate_score(candidate_id) or {}
        
        if not job or not profile:
            return f"Cannot generate interview questions: Candidate '{candidate_id}' or Job '{job_id}' profile data missing."
            
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Senior Technical Recruiter. Generate structured interview questions based on candidate profile evidence."),
            ("user", """Generate structured interview questions for this candidate:

Job Role: {job_title}
Candidate Name: {candidate_name}
Deterministic Score: {score}% ({fit})
Matched Skills: {matched_skills}
Missing/Gap Skills: {missing_skills}
Experience Years: {exp_years}

Generate 5 specific interview questions:
1. Technical Deep-Dive (focusing on matched skills)
2. Gap Assessment (focusing on missing skills)
3. Behavioral/Situational Question
4. Past Project Experience Inquiry
5. Problem-Solving Challenge

Output format:
Candidate: {candidate_name}
Score: {score}%

Questions:
1. [Technical]: ...
2. [Gap Assessment]: ...
3. [Behavioral]: ...
4. [Project Experience]: ...
5. [Challenge]: ...
""")
        ])
        
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({
            "job_title": job.get("title", "Role"),
            "candidate_name": profile.get("candidate_name", candidate_id),
            "score": score_data.get("final_score", 0.0),
            "fit": score_data.get("fit_category", "Pending"),
            "matched_skills": ", ".join(profile.get("matched_required_skills", [])),
            "missing_skills": ", ".join(profile.get("missing_required_skills", [])),
            "exp_years": profile.get("experience_years", "N/A")
        })
        return result
    except Exception as e:
        logger.error(f"Error in generate_interview_questions tool: {e}")
        return f"Error generating interview questions: {e}"

@tool
def generate_candidate_summary(candidate_id: str) -> str:
    """
    Generates an executive candidate fit summary grounded in deterministic score and verified resume evidence.
    """
    logger.info(f"Agent executing tool 'generate_candidate_summary' for candidate_id: '{candidate_id}'")
    try:
        profile = hr_db.get_candidate_profile(candidate_id) or {}
        score_data = hr_db.get_candidate_score(candidate_id) or {}
        
        if not profile and not score_data:
            return f"Candidate '{candidate_id}' profile data not found."
            
        score = score_data.get("final_score", 0.0)
        fit = score_data.get("fit_category", "Pending")
        name = profile.get("candidate_name", candidate_id)
        
        summary = f"Executive Candidate Summary for {name}:\n"
        summary += f"- Overall Match Score: {score}% ({fit})\n"
        summary += f"- Key Strengths: {', '.join(profile.get('matched_required_skills', []))}\n"
        summary += f"- Identified Gaps: {', '.join(profile.get('missing_required_skills', []))}\n"
        summary += f"- Experience Evaluation: {profile.get('experience_fit', 'Evaluated')}\n"
        return summary
    except Exception as e:
        logger.error(f"Error in generate_candidate_summary tool: {e}")
        return f"Error generating summary: {e}"
