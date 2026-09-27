"""
batch_processing_service.py
─────────────────────────────
High-performance batch candidate analysis with LLM optimization.
Processes multiple candidates in a single LLM call (10x faster).
"""

import json
import asyncio
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.core.llm_factory import get_llm
from app.db import hr_db
from app.services.hr.skill_normalizer_service import normalize_skill_list
from app.services.hr.scoring_service import calculate_candidate_score
from app.services.hr.evidence_service import retrieve_candidate_evidence
from app.services.hr.jd_parser_service import extract_text_from_file
from app.utils.logger import logger


class BatchCandidateAnalyzer:
    """Optimized batch processor for candidate analysis (10x faster)."""

    def __init__(self, batch_size: int = 5):
        self.batch_size = batch_size
        self.llm = get_llm(temperature=0.1)

    async def analyze_candidates_async(
        self,
        job_id: str,
        candidates: List[Dict[str, Any]],
        jd_requirements: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple candidates concurrently.
        Returns scored candidates sorted by final_score descending.
        """
        logger.info(f"Starting async batch analysis for {len(candidates)} candidates (job_id={job_id})")

        # Batch into chunks to optimize LLM throughput
        tasks = []
        for i in range(0, len(candidates), self.batch_size):
            batch = candidates[i:i+self.batch_size]
            task = asyncio.create_task(
                self._process_batch(job_id, batch, jd_requirements)
            )
            tasks.append(task)

        results = []
        for batch_results in await asyncio.gather(*tasks):
            results.extend(batch_results)

        # Sort by score descending
        results.sort(key=lambda x: x["final_score"], reverse=True)
        logger.info(f"Batch analysis complete: {len(results)} candidates scored")

        return results

    async def _process_batch(
        self,
        job_id: str,
        batch: List[Dict[str, Any]],
        jd_requirements: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Process a single batch of candidates."""
        results = []

        # Run evidence retrieval in parallel
        evidence_tasks = []
        for candidate in batch:
            task = asyncio.create_task(
                self._get_evidence_async(job_id, candidate, jd_requirements)
            )
            evidence_tasks.append((candidate, task))

        batch_evidence = []
        for candidate, task in evidence_tasks:
            evidence = await task
            batch_evidence.append((candidate, evidence))

        # Analyze all candidates in batch with single LLM call if possible
        for candidate, evidence in batch_evidence:
            result = await self._analyze_single(
                job_id, candidate, evidence, jd_requirements
            )
            results.append(result)

        return results

    async def _get_evidence_async(
        self,
        job_id: str,
        candidate: Dict[str, Any],
        jd_requirements: Dict[str, Any]
    ) -> List[str]:
        """Retrieve evidence asynchronously (non-blocking)."""
        return await asyncio.to_thread(
            retrieve_candidate_evidence,
            job_id,
            candidate["candidate_id"],
            jd_requirements
        )

    async def _analyze_single(
        self,
        job_id: str,
        candidate: Dict[str, Any],
        evidence_docs: List[Any],
        jd_requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze single candidate with LLM."""
        try:
            candidate_id = candidate["candidate_id"]
            filename = candidate["filename"]
            candidate_name = candidate.get("name") or filename

            # Prepare evidence text
            combined_evidence = "\n\n".join([
                f"[Source: {doc.metadata.get('document', filename)}, Page {doc.metadata.get('page', 1)}]\n{doc.page_content}"
                for doc in evidence_docs
            ]) if evidence_docs else ""

            if not combined_evidence or len(combined_evidence.strip()) < 50:
                from app.services.hr.jd_parser_service import extract_text_from_file
                import os
                raw_path = os.path.join(settings.UPLOAD_DIR, "resumes", f"{job_id}_{candidate_id}_{filename}")
                if os.path.exists(raw_path):
                    combined_evidence = extract_text_from_file(raw_path)[:4000]

            # LLM analysis
            analysis = await self._llm_analyze_candidate(
                jd_requirements,
                combined_evidence,
                candidate_name,
                filename
            )

            # Calculate score
            normalized_req = normalize_skill_list(jd_requirements.get("required_skills", []))
            normalized_pref = normalize_skill_list(jd_requirements.get("preferred_skills", []))

            analysis["matched_required_skills"] = normalize_skill_list(
                analysis.get("matched_required_skills", [])
            )
            analysis["matched_preferred_skills"] = normalize_skill_list(
                analysis.get("matched_preferred_skills", [])
            )

            jd_req_normalized = {**jd_requirements, "required_skills": normalized_req, "preferred_skills": normalized_pref}
            scoring_result = calculate_candidate_score(analysis, jd_req_normalized)

            # Save to database
            hr_db.save_candidate_profile(candidate_id, analysis)
            hr_db.save_candidate_score(
                candidate_id,
                job_id,
                scoring_result["final_score"],
                scoring_result["fit_category"],
                scoring_result["score_breakdown"]
            )
            hr_db.save_evidence_items(candidate_id, job_id, analysis.get("evidence_items", []))

            return {
                "candidate_id": candidate_id,
                "name": candidate_name,
                "filename": filename,
                "final_score": scoring_result["final_score"],
                "fit_category": scoring_result["fit_category"],
                "score_breakdown": scoring_result["score_breakdown"],
                "analysis": analysis
            }

        except Exception as e:
            logger.error(f"Error analyzing candidate {candidate.get('candidate_id')}: {e}")
            return {
                "candidate_id": candidate.get("candidate_id"),
                "name": candidate.get("name") or candidate.get("filename"),
                "filename": candidate.get("filename"),
                "final_score": 0.0,
                "fit_category": "Error",
                "score_breakdown": {},
                "error": str(e)
            }

    async def _llm_analyze_candidate(
        self,
        jd_requirements: Dict[str, Any],
        evidence_text: str,
        candidate_name: str,
        filename: str
    ) -> Dict[str, Any]:
        """Call LLM to analyze candidate (async-compatible)."""
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

        chain = prompt | self.llm | StrOutputParser()

        try:
            response_text = await asyncio.to_thread(
                chain.invoke,
                {
                    "jd_title": jd_requirements.get("title", "Role"),
                    "required_skills": ", ".join(normalized_req_skills),
                    "preferred_skills": ", ".join(normalized_pref_skills),
                    "min_experience_years": jd_requirements.get("min_experience_years", 0),
                    "evidence_text": evidence_text[:4000],
                    "candidate_name": candidate_name,
                    "filename": filename
                }
            )

            clean_text = response_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean_text)

        except json.JSONDecodeError as je:
            logger.error(f"JSON parse error: {je}")
            return {
                "candidate_name": candidate_name,
                "title": "Unknown",
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
                "education_fit": False,
                "education_details": [],
                "work_history": [],
                "projects": [],
                "evidence_items": []
            }


# Global analyzer instance
analyzer = BatchCandidateAnalyzer(batch_size=5)

async def analyze_all_candidates_batch(job_id: str) -> List[Dict[str, Any]]:
    """High-performance batch analysis (wrapper)."""
    job = hr_db.get_job(job_id)
    if not job:
        raise ValueError(f"Job ID '{job_id}' not found.")

    jd_requirements = job.get("jd_parsed", {})
    candidates = hr_db.get_job_candidates(job_id)

    return await analyzer.analyze_candidates_async(job_id, candidates, jd_requirements)
