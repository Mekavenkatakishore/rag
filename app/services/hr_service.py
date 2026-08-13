"""
hr_service.py
─────────────
Core service layer for HR Job Description processing, batch candidate resume parsing,
hybrid evidence retrieval, FlashRank reranking, LLM evidence extraction, and deterministic scoring.
"""

import os
import json
import uuid
import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from app.loaders.loader_factory import get_document_loader
from app.services import rag_service
from app.services.skill_normalizer import normalize_skill, normalize_skill_list
from app.services.scoring_engine import calculate_candidate_score
from app.db import hr_db
from app.utils.logger import logger

load_dotenv()

BASE_UPLOAD_DIR = "./uploaded_files"
JD_DIR = os.path.join(BASE_UPLOAD_DIR, "jd")
RESUME_DIR = os.path.join(BASE_UPLOAD_DIR, "resumes")

os.makedirs(JD_DIR, exist_ok=True)
os.makedirs(RESUME_DIR, exist_ok=True)

# Shared HuggingFace embeddings
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Groq LLM for extraction
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.1
)

def extract_text_from_file(file_path: str) -> str:
    """Uses loader factory to extract text from PDF, DOCX, TXT, etc."""
    try:
        loader = get_document_loader(file_path)
        docs = loader.load()
        full_text = "\n\n".join([doc.page_content for doc in docs if doc.page_content])
        return full_text
    except Exception as e:
        logger.error(f"Error reading file '{file_path}': {e}")
        return ""

def parse_job_description(jd_text: str, filename: str) -> dict:
    """Extracts structured requirements from JD text using LLM."""
    if not jd_text:
        return {
            "title": filename,
            "required_skills": [],
            "preferred_skills": [],
            "min_experience_years": 0,
            "preferred_experience_years": 0,
            "education": [],
            "responsibilities": [],
            "domain": [],
            "summary": "Empty or unreadable JD file."
        }

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert HR recruiter. Extract structured information from this Job Description (JD). Return ONLY valid JSON format without markdown code fences."),
        ("user", """Extract the following JSON structure from this Job Description:
{{
  "title": "Job Role Title",
  "required_skills": ["Skill1", "Skill2"],
  "preferred_skills": ["SkillA", "SkillB"],
  "min_experience_years": 3,
  "preferred_experience_years": 5,
  "education": ["Degree1"],
  "responsibilities": ["Responsibility 1", "Responsibility 2"],
  "domain": ["Software Engineering"],
  "summary": "Brief role summary"
}}

Job Description Text:
{jd_text}
""")
    ])

    chain = prompt | llm | StrOutputParser()
    try:
        response_text = chain.invoke({"jd_text": jd_text[:4000]})
        clean_text = response_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(clean_text)
        
        # Normalize skills
        parsed["required_skills"] = normalize_skill_list(parsed.get("required_skills", []))
        parsed["preferred_skills"] = normalize_skill_list(parsed.get("preferred_skills", []))
        return parsed
    except Exception as e:
        logger.error(f"Failed to parse JD JSON via LLM: {e}")
        return {
            "title": filename,
            "required_skills": [],
            "preferred_skills": [],
            "min_experience_years": 0,
            "preferred_experience_years": 0,
            "education": [],
            "responsibilities": [],
            "domain": [],
            "summary": jd_text[:300]
        }

def process_single_resume(job_id: str, candidate_id: str, filename: str, file_bytes: bytes) -> dict:
    """
    Processes a single resume independently (fault-tolerant batch worker).
    Saves resume file, extracts text, chunks document, attaches metadata, and updates DB.
    """
    resume_file_path = os.path.join(RESUME_DIR, f"{job_id}_{candidate_id}_{filename}")
    
    try:
        with open(resume_file_path, "wb") as f:
            f.write(file_bytes)
            
        resume_text = extract_text_from_file(resume_file_path)
        if not resume_text:
            hr_db.save_candidate(candidate_id, job_id, filename, "", filename, status="failed_extraction")
            return {"candidate_id": candidate_id, "filename": filename, "status": "failed_extraction"}
            
        # Extract basic name & email if possible
        candidate_name = os.path.splitext(filename)[0].replace("_", " ").title()
        
        # Chunk text with metadata
        splitter = rag_service.get_text_splitter()
        raw_docs = [Document(page_content=resume_text, metadata={
            "candidate_id": candidate_id,
            "job_id": job_id,
            "candidate_name": candidate_name,
            "document": filename,
            "source": filename
        })]
        chunks = splitter.split_documents(raw_docs)
        
        # Add page numbers to chunk metadata
        for idx, chunk in enumerate(chunks, 1):
            chunk.metadata["page"] = (idx // 3) + 1  # Approximate page number
            chunk.metadata["section"] = "Resume Section"
            
        # Add to Chroma vector store
        rag_service.vectorstore.add_documents(chunks)
        
        # Save candidate in SQLite DB
        hr_db.save_candidate(
            candidate_id=candidate_id,
            job_id=job_id,
            name=candidate_name,
            email="",
            filename=filename,
            status="success"
        )
        
        return {"candidate_id": candidate_id, "filename": filename, "status": "success", "chunks_count": len(chunks)}
        
    except Exception as e:
        logger.error(f"Failed processing resume '{filename}': {e}")
        hr_db.save_candidate(candidate_id, job_id, filename, "", filename, status=f"failed: {e}")
        return {"candidate_id": candidate_id, "filename": filename, "status": "failed", "error": str(e)}

def retrieve_candidate_evidence(job_id: str, candidate_id: str, jd_requirements: dict) -> list[Document]:
    """
    Retrieves evidence chunks for a specific candidate using Chroma DB metadata filter
    followed by FlashRank cross-encoder reranking.
    """
    skills_query = " ".join(jd_requirements.get("required_skills", []) + jd_requirements.get("preferred_skills", []))
    query_text = f"{jd_requirements.get('title', '')} {skills_query}"
    
    try:
        # Chroma similarity search with job_id & candidate_id metadata filter
        retrieved_docs = rag_service.vectorstore.similarity_search(
            query=query_text,
            k=15,
            filter={"candidate_id": candidate_id}
        )
        
        if not retrieved_docs:
            return []
            
        # FlashRank Cross-Encoder Reranking
        try:
            ranker = rag_service.Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
            passages = [
                {"id": idx, "text": doc.page_content, "meta": doc.metadata}
                for idx, doc in enumerate(retrieved_docs)
            ]
            rerank_request = {"query": query_text, "passages": passages}
            rerank_results = ranker.rank(rerank_request)
            
            top_docs = []
            for r in rerank_results[:6]:
                top_docs.append(Document(page_content=r["text"], metadata=r["meta"]))
            return top_docs
        except Exception as re:
            logger.warning(f"FlashRank reranker fallback for candidate {candidate_id}: {re}")
            return retrieved_docs[:6]
            
    except Exception as e:
        logger.error(f"Error retrieving candidate evidence for {candidate_id}: {e}")
        return []

def analyze_and_score_candidate(job_id: str, candidate_id: str, candidate_name: str, filename: str, jd_requirements: dict) -> dict:
    """
    Runs LLM evidence extraction on candidate evidence chunks,
    calculates deterministic score via scoring_engine, and saves output to SQLite DB.
    """
    evidence_docs = retrieve_candidate_evidence(job_id, candidate_id, jd_requirements)
    combined_evidence_text = "\n\n".join([
        f"[Source: {doc.metadata.get('document', filename)}, Page {doc.metadata.get('page', 1)}]\n{doc.page_content}"
        for doc in evidence_docs
    ])
    
    if not combined_evidence_text:
        # Try reading full raw file if vector search returned empty
        raw_path = os.path.join(RESUME_DIR, f"{job_id}_{candidate_id}_{filename}")
        combined_evidence_text = extract_text_from_file(raw_path)[:3000]

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an elite HR Talent Acquisition Specialist. Analyze candidate resume evidence against Job Description requirements. Be strict and objective. Do NOT invent skills. Return ONLY valid JSON."),
        ("user", """Analyze candidate resume evidence against this Job Description.

Job Title: {jd_title}
Required Skills: {required_skills}
Preferred Skills: {preferred_skills}
Min Experience Years: {min_experience_years}

Candidate Resume Evidence Text:
{evidence_text}

Return ONLY a JSON object formatted exactly as:
{{
  "candidate_name": "{candidate_name}",
  "matched_required_skills": ["Skill1"],
  "missing_required_skills": ["Skill2"],
  "matched_preferred_skills": ["SkillA"],
  "missing_preferred_skills": ["SkillB"],
  "experience_years": 5.0,
  "experience_fit": "Meets requirement",
  "project_relevance": "High",
  "education_fit": true,
  "evidence_items": [
    {{
      "skill": "Python",
      "matched": true,
      "evidence": "Exact quote or summary from text",
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
            "required_skills": ", ".join(jd_requirements.get("required_skills", [])),
            "preferred_skills": ", ".join(jd_requirements.get("preferred_skills", [])),
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
            "matched_required_skills": [],
            "missing_required_skills": jd_requirements.get("required_skills", []),
            "matched_preferred_skills": [],
            "missing_preferred_skills": jd_requirements.get("preferred_skills", []),
            "experience_years": 0.0,
            "experience_fit": "Unknown",
            "project_relevance": "Low",
            "education_fit": True,
            "evidence_items": []
        }

    # Normalize extracted skill lists
    analysis["matched_required_skills"] = normalize_skill_list(analysis.get("matched_required_skills", []))
    analysis["missing_required_skills"] = normalize_skill_list(analysis.get("missing_required_skills", []))
    analysis["matched_preferred_skills"] = normalize_skill_list(analysis.get("matched_preferred_skills", []))
    analysis["missing_preferred_skills"] = normalize_skill_list(analysis.get("missing_preferred_skills", []))

    # Calculate Deterministic Match Score (Python Application Math)
    scoring_result = calculate_candidate_score(analysis, jd_requirements)
    final_score = scoring_result["final_score"]
    fit_category = scoring_result["fit_category"]
    score_breakdown = scoring_result["score_breakdown"]

    # Save outputs to SQLite Database
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
        
    # Return sorted leaderboard
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
