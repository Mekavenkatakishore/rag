"""
hr_chat_service.py
──────────────────
Conversational AI for HR queries about candidates and jobs.
Phase 4: Smart HR chat system for candidate questions.
"""

from typing import Dict, List, Any, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from app.core.llm_factory import get_llm
from app.db import hr_db
from app.services.hr.evidence_cache_service import retrieve_candidate_evidence_cached
from app.utils.logger import logger


class HRChatAssistant:
    """Intelligent HR assistant for candidate and job queries."""

    def __init__(self):
        self.llm = get_llm(temperature=0.7)  # Higher temp for conversational
        self.chat_history = []

    async def answer_hr_question(
        self,
        job_id: str,
        question: str,
        candidate_id: Optional[str] = None,
        include_context: bool = True
    ) -> Dict[str, Any]:
        """
        Answer questions about candidates or jobs.
        Can be scoped to specific candidate or entire job.
        """
        logger.info(f"HR Chat: job_id={job_id}, question={question[:60]}")

        # Get job and candidate context
        job = hr_db.get_job(job_id)
        if not job:
            return {
                "status": "error",
                "message": f"Job ID '{job_id}' not found.",
                "answer": None
            }

        jd_requirements = job.get("jd_parsed", {})
        job_title = job.get("title", "Unknown Role")

        # Build context
        context = f"Job Title: {job_title}\n"
        context += f"Required Skills: {', '.join(jd_requirements.get('required_skills', []))}\n"
        context += f"Min Experience: {jd_requirements.get('min_experience_years', 0)} years\n\n"

        # If candidate-specific question
        if candidate_id:
            candidate = hr_db.get_job_candidate(job_id, candidate_id)
            if not candidate:
                return {
                    "status": "error",
                    "message": f"Candidate '{candidate_id}' not found in job.",
                    "answer": None
                }

            profile = hr_db.get_candidate_profile(candidate_id)
            score_data = hr_db.get_candidate_score(candidate_id)

            # Add candidate context
            if profile:
                profile_info = profile.get("profile_json") if isinstance(profile, dict) else profile
                context += f"Candidate: {profile_info.get('candidate_name', 'Unknown')}\n"
                context += f"Experience: {profile_info.get('experience_years', 0)} years\n"
                context += f"Skills: {', '.join(profile_info.get('matched_required_skills', []))}\n"
                context += f"Education: {', '.join(profile_info.get('education_details', []))}\n\n"

            if score_data:
                context += f"Match Score: {score_data.get('final_score', 0)}%\n"
                context += f"Fit Category: {score_data.get('fit_category', 'Unknown')}\n\n"

            # Retrieve relevant evidence
            if include_context:
                evidence = retrieve_candidate_evidence_cached(
                    job_id, candidate_id, jd_requirements, use_cache=True
                )
                if evidence:
                    context += "Supporting Evidence from Resume:\n"
                    for doc in evidence[:3]:  # Top 3 relevant passages
                        context += f"- {doc.page_content[:200]}...\n"

        else:
            # General job question - include all candidate leaderboard
            candidates = hr_db.get_job_candidates(job_id)
            if candidates:
                context += "Current Candidates (Top 5):\n"
                for i, cand in enumerate(candidates[:5], 1):
                    score_data = hr_db.get_candidate_score(cand["candidate_id"])
                    score = score_data.get("final_score", 0) if score_data else 0
                    context += f"{i}. {cand.get('name', cand['filename'])}: {score}% fit\n"

        # Call LLM with context
        answer = await self._llm_answer_question(
            question=question,
            context=context,
            candidate_id=candidate_id
        )

        return {
            "status": "success",
            "question": question,
            "answer": answer,
            "candidate_id": candidate_id,
            "job_id": job_id,
            "context_summary": f"Answered based on {job_title} job requirements"
        }

    async def _llm_answer_question(
        self,
        question: str,
        context: str,
        candidate_id: Optional[str] = None
    ) -> str:
        """LLM call for HR question answering."""
        system_prompt = """You are an expert HR Talent Acquisition Assistant.
You have deep knowledge of candidate profiles, job requirements, and hiring best practices.
Answer questions accurately, concisely, and helpfully.
If you don't have enough information, say so clearly.
Provide actionable insights when possible."""

        if candidate_id:
            user_prompt = f"""Context:
{context}

Question about this candidate: {question}

Provide a helpful, professional answer. Be specific and reference candidate details."""
        else:
            user_prompt = f"""Context:
{context}

General question about the job: {question}

Provide a helpful, professional answer."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            answer = await asyncio.to_thread(chain.invoke, {})
            return answer
        except Exception as e:
            logger.error(f"Error in HR chat LLM: {e}")
            return f"I encountered an error answering your question. Please try again. Error: {str(e)}"

    async def compare_candidates(
        self,
        job_id: str,
        candidate_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Compare multiple candidates side-by-side.
        Returns detailed comparison matrix.
        """
        logger.info(f"Comparing {len(candidate_ids)} candidates for job {job_id}")

        job = hr_db.get_job(job_id)
        if not job:
            return {"status": "error", "message": "Job not found"}

        comparison = {
            "job_title": job.get("title"),
            "candidates": []
        }

        for cand_id in candidate_ids:
            profile = hr_db.get_candidate_profile(cand_id)
            score = hr_db.get_candidate_score(cand_id)

            candidate_info = {
                "candidate_id": cand_id,
                "name": profile.get("candidate_name", "Unknown") if profile else "Unknown",
                "score": score.get("final_score", 0) if score else 0,
                "fit": score.get("fit_category", "Unknown") if score else "Unknown",
                "experience": profile.get("experience_years", 0) if profile else 0,
                "matched_skills": profile.get("matched_required_skills", []) if profile else [],
                "missing_skills": profile.get("missing_required_skills", []) if profile else [],
                "education": profile.get("education_details", []) if profile else []
            }
            comparison["candidates"].append(candidate_info)

        # Generate comparison summary using LLM
        comparison_text = self._generate_comparison_summary(comparison)
        comparison["summary"] = comparison_text

        return comparison

    def _generate_comparison_summary(self, comparison: Dict[str, Any]) -> str:
        """Generate brief comparison summary."""
        candidates = comparison.get("candidates", [])
        if not candidates:
            return "No candidates to compare."

        # Sort by score
        sorted_cands = sorted(candidates, key=lambda x: x["score"], reverse=True)

        summary = f"**Candidate Comparison for {comparison.get('job_title', 'Role')}**\n\n"
        summary += "**Rankings:**\n"
        for i, cand in enumerate(sorted_cands, 1):
            summary += f"{i}. {cand['name']} ({cand['score']}% - {cand['fit']})\n"

        summary += "\n**Key Differences:**\n"
        top_cand = sorted_cands[0]
        for cand in sorted_cands[1:]:
            gap = top_cand["score"] - cand["score"]
            summary += f"- {cand['name']} is {gap:.1f}% behind {top_cand['name']}\n"

        return summary

    async def get_candidate_insights(
        self,
        job_id: str,
        candidate_id: str
    ) -> Dict[str, Any]:
        """
        Get AI-powered insights about a candidate.
        Returns strengths, weaknesses, and recommendations.
        """
        logger.info(f"Generating insights for candidate {candidate_id}")

        profile = hr_db.get_candidate_profile(candidate_id)
        score = hr_db.get_candidate_score(candidate_id)

        if not profile or not score:
            return {"status": "error", "message": "Candidate data not found"}

        job = hr_db.get_job(job_id)
        jd_requirements = job.get("jd_parsed", {}) if job else {}

        # Generate insights using LLM
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert HR talent assessment AI.
Analyze candidate profiles and provide actionable insights.
Format your response as JSON with sections: strengths, weaknesses, recommendations."""),
            ("user", f"""Analyze this candidate for the role: {job.get('title', 'Unknown')}

Candidate Profile:
- Experience: {profile.get('experience_years', 0)} years
- Matched Skills: {', '.join(profile.get('matched_required_skills', []))}
- Missing Skills: {', '.join(profile.get('missing_required_skills', []))}
- Match Score: {score.get('final_score', 0)}%
- Education: {', '.join(profile.get('education_details', []))}

Required Skills: {', '.join(jd_requirements.get('required_skills', []))}
Minimum Experience: {jd_requirements.get('min_experience_years', 0)} years

Provide JSON with:
1. strengths: List of candidate strengths
2. weaknesses: List of areas to improve
3. recommendations: Hiring recommendations
4. development_areas: Skills to develop
5. interview_focus: Key topics for interview""")
        ])

        chain = prompt | self.llm | StrOutputParser()

        try:
            insights_text = await asyncio.to_thread(chain.invoke, {})
            import json
            # Try to parse as JSON
            try:
                insights = json.loads(insights_text)
            except:
                insights = {"raw_insights": insights_text}
            return {"status": "success", "insights": insights}
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return {"status": "error", "message": str(e)}


# Global chat instance
_hr_chat = HRChatAssistant()


async def answer_hr_question(
    job_id: str,
    question: str,
    candidate_id: Optional[str] = None
) -> Dict[str, Any]:
    """Answer questions about candidates or jobs."""
    return await _hr_chat.answer_hr_question(job_id, question, candidate_id)


async def compare_candidates(
    job_id: str,
    candidate_ids: List[str]
) -> Dict[str, Any]:
    """Compare multiple candidates."""
    return await _hr_chat.compare_candidates(job_id, candidate_ids)


async def get_candidate_insights(
    job_id: str,
    candidate_id: str
) -> Dict[str, Any]:
    """Get insights about a candidate."""
    return await _hr_chat.get_candidate_insights(job_id, candidate_id)


# Import asyncio for thread executor
import asyncio
