import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from app.schemas.hr_schemas import JobCreateRequest, HRChatRequest, CandidateShortlistRequest
from app.services import hr_service
from app.loaders.loader_factory import LOADER_MAPPING
from app.db import hr_db
from app.utils.logger import logger
from app.api.deps import get_current_user

router = APIRouter()
DEFAULT_JOB_ID = "default_job_001"

@router.post("/jobs")
async def create_job(request: JobCreateRequest, current_user: dict = Depends(get_current_user)):
    """Creates a new candidate screening job container."""
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    user_id = current_user.get("id")
    job = hr_db.create_job(job_id=job_id, user_id=user_id, title=request.title)
    return {"status": "success", "job": job}

@router.post("/jobs/{job_id}/upload-jd")
async def upload_job_description(
    job_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Uploads and parses Job Description document for a specific job."""
    file_name = os.path.basename(file.filename)
    _, ext = os.path.splitext(file_name.lower())
    
    if ext not in LOADER_MAPPING:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{ext}'. Supported: {', '.join(LOADER_MAPPING.keys())}"
        )
        
    job = hr_db.get_job(job_id)
    if not job:
        hr_db.create_job(job_id=job_id, user_id=current_user.get("id"), title="Candidate Screening Role")

    jd_path = os.path.join(hr_service.JD_DIR, f"{job_id}_{file_name}")
    try:
        with open(jd_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        jd_text = hr_service.extract_text_from_file(jd_path)
        jd_parsed = hr_service.parse_job_description(jd_text, file_name)
        
        job_title = jd_parsed.get("title", file_name)
        hr_db.create_job(job_id=job_id, user_id=current_user.get("id"), title=job_title, jd_filename=file_name, jd_parsed=jd_parsed)
        
        return {
            "status": "success",
            "job_id": job_id,
            "filename": file_name,
            "jd_parsed": jd_parsed
        }
    except Exception as e:
        logger.error(f"Error uploading JD for job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process JD: {e}")

@router.post("/jobs/{job_id}/upload-resumes")
async def upload_batch_resumes(
    job_id: str,
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Batch uploads candidate resumes for a specific job."""
    job = hr_db.get_job(job_id)
    if not job:
        hr_db.create_job(job_id=job_id, user_id=current_user.get("id"), title="Candidate Screening Role")

    results = []
    for idx, file in enumerate(files, 1):
        filename = os.path.basename(file.filename)
        _, ext = os.path.splitext(filename.lower())
        
        if ext not in LOADER_MAPPING:
            results.append({"filename": filename, "status": "unsupported_extension"})
            continue
            
        candidate_id = f"C{idx:03d}_{uuid.uuid4().hex[:4]}"
        file_bytes = await file.read()
        
        res = hr_service.process_single_resume(job_id, candidate_id, filename, file_bytes)
        results.append(res)
        
    return {
        "status": "success",
        "job_id": job_id,
        "total_files": len(files),
        "results": results
    }

@router.post("/jobs/{job_id}/analyze")
async def analyze_job_candidates(job_id: str, current_user: dict = Depends(get_current_user)):
    """Triggers candidate evaluation and deterministic scoring."""
    try:
        leaderboard = hr_service.analyze_all_job_candidates(job_id)
        return {
            "status": "success",
            "job_id": job_id,
            "total_candidates": len(leaderboard),
            "leaderboard": leaderboard
        }
    except Exception as e:
        logger.error(f"Error analyzing candidates for job '{job_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}/leaderboard")
async def get_job_leaderboard(job_id: str, current_user: dict = Depends(get_current_user)):
    """Fetches candidate rankings and leaderboard for a specific job."""
    job = hr_db.get_job(job_id)
    if not job:
        hr_db.create_job(job_id=job_id, user_id=current_user.get("id"), title="Candidate Screening Role")
        job = hr_db.get_job(job_id)
        
    leaderboard = hr_db.get_job_leaderboard(job_id)
    return {
        "status": "success",
        "job": job,
        "total_candidates": len(leaderboard),
        "candidates": leaderboard
    }

@router.post("/jobs/{job_id}/candidates/{candidate_id}/shortlist")
async def toggle_candidate_shortlist(
    job_id: str,
    candidate_id: str,
    req: CandidateShortlistRequest = CandidateShortlistRequest(status="Shortlisted"),
    current_user: dict = Depends(get_current_user)
):
    """Updates candidate shortlist status (Pending or Shortlisted) scoped to job_id."""
    status_to_set = req.status if req and req.status else "Shortlisted"
    if status_to_set not in ["Pending", "Shortlisted"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'Pending' or 'Shortlisted'.")

    res = hr_db.update_candidate_shortlist_status(job_id, candidate_id, status_to_set)
    if not res:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found for job '{job_id}'.")

    return {
        "success": True,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "status": status_to_set
    }

@router.get("/jobs/{job_id}/candidates/{candidate_id}")
async def get_candidate_details(job_id: str, candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Fetches candidate profile, score breakdown, and supporting citations evidence."""
    score_data = hr_db.get_candidate_score(candidate_id)
    profile_data = hr_db.get_candidate_profile(candidate_id)
    evidence_items = hr_db.get_candidate_evidence(candidate_id)
    cands = hr_db.get_job_candidates(job_id)
    cand = next((c for c in cands if c["candidate_id"] == candidate_id), None)
    
    if not profile_data and not score_data and not cand:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")
        
    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "score": score_data.get("final_score", 0.0) if score_data else 0.0,
        "fit": score_data.get("fit_category", "Pending") if score_data else "Pending",
        "candidate_status": cand.get("candidate_status", "Pending") if cand else "Pending",
        "score_breakdown": score_data.get("score_breakdown", {}) if score_data else {},
        "profile": profile_data or {},
        "evidence": evidence_items
    }

@router.get("/jobs/{job_id}/candidates/{candidate_id}/resume-preview")
async def preview_candidate_resume(job_id: str, candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Fetches raw extracted text from the candidate resume document for live preview."""
    cands = hr_db.get_job_candidates(job_id)
    cand = next((c for c in cands if c["candidate_id"] == candidate_id), None)
    
    filename = cand["filename"] if cand else f"{candidate_id}.pdf"
    file_path = os.path.join(hr_service.RESUME_DIR, f"{job_id}_{candidate_id}_{filename}")
    
    if not os.path.exists(file_path):
        # Try finding by candidate_id in filename
        for f in os.listdir(hr_service.RESUME_DIR):
            if candidate_id in f:
                file_path = os.path.join(hr_service.RESUME_DIR, f)
                break

    text = hr_service.extract_text_from_file(file_path) if os.path.exists(file_path) else "Resume text unavailable."
    return {
        "candidate_id": candidate_id,
        "filename": filename,
        "resume_text": text
    }

@router.post("/jobs/{job_id}/chat")
async def chat_about_job_candidates(job_id: str, req: HRChatRequest, current_user: dict = Depends(get_current_user)):
    """Handles HR questions about candidate comparisons and skill queries."""
    leaderboard = hr_db.get_job_leaderboard(job_id)
    job = hr_db.get_job(job_id)
    
    if not leaderboard:
        return {"response": "No candidates uploaded for this job yet. Please upload candidate resumes first."}
        
    context_summary = f"Job Title: {job.get('title', 'Role')}\nTotal Candidates: {len(leaderboard)}\n\nCandidates Leaderboard:\n"
    for c in leaderboard[:5]:
        context_summary += f"- Rank #{c['rank']}: {c['name']} (Score: {c['score']}%, Fit: {c['fit']})\n"
        context_summary += f"  Matched Skills: {', '.join(c.get('profile', {}).get('matched_required_skills', []))}\n"
        context_summary += f"  Missing Skills: {', '.join(c.get('profile', {}).get('missing_required_skills', []))}\n\n"
        
    prompt = f"You are an HR Assistant. Answer the HR question accurately based on candidate leaderboard data.\n\nContext:\n{context_summary}\n\nQuestion: {req.prompt}\n\nAnswer:"
    response = hr_service.jd_parser_service.llm.invoke(prompt)
    return {"response": response.content}

@router.post("/jobs/{job_id}/clear")
async def clear_job_screening_session(job_id: str, current_user: dict = Depends(get_current_user)):
    """Clears candidate records, scores, evidence, and uploaded files for a specific job."""
    hr_service.clear_hr_session(job_id)
    return {"status": "success", "message": f"Screening session for job '{job_id}' cleared successfully."}

# ─── Legacy Endpoints (For Backward Compatibility) ──────────────────────────

@router.post("/upload-jd")
async def legacy_upload_jd(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Legacy route: uploads JD to default job container."""
    hr_db.create_job(DEFAULT_JOB_ID, current_user.get("id"), "Default HR Role")
    return await upload_job_description(DEFAULT_JOB_ID, file, current_user)

@router.post("/upload-resumes")
async def legacy_upload_resumes(files: list[UploadFile] = File(...), current_user: dict = Depends(get_current_user)):
    """Legacy route: uploads batch resumes to default job container."""
    hr_db.create_job(DEFAULT_JOB_ID, current_user.get("id"), "Default HR Role")
    up_res = await upload_batch_resumes(DEFAULT_JOB_ID, files, current_user)
    await analyze_job_candidates(DEFAULT_JOB_ID, current_user)
    return up_res

@router.get("/leaderboard")
async def legacy_get_leaderboard(current_user: dict = Depends(get_current_user)):
    """Legacy route: fetches default job leaderboard."""
    return await get_job_leaderboard(DEFAULT_JOB_ID, current_user)

@router.post("/clear")
async def legacy_clear_hr(current_user: dict = Depends(get_current_user)):
    """Legacy route: resets HR data."""
    hr_service.clear_hr_session(DEFAULT_JOB_ID)
    for folder in [hr_service.JD_DIR, hr_service.RESUME_DIR]:
        if os.path.exists(folder):
            for f in os.listdir(folder):
                try:
                    os.remove(os.path.join(folder, f))
                except Exception:
                    pass
    return {"status": "success", "message": "HR screening session cleared."}
