from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class JobCreateRequest(BaseModel):
    title: str = Field(..., description="Title of job role")

class JobResponse(BaseModel):
    job_id: str
    user_id: Optional[int] = None
    title: str
    jd_filename: Optional[str] = None
    jd_parsed: Dict[str, Any] = Field(default_factory=dict)
    created_at: str

class JobUploadJDResponse(BaseModel):
    status: str
    job_id: str
    filename: str
    jd_parsed: Dict[str, Any]

class ResumeUploadResult(BaseModel):
    filename: str
    status: str
    candidate_id: Optional[str] = None

class BatchResumeUploadResponse(BaseModel):
    status: str
    job_id: str
    total_files: int
    results: List[Dict[str, Any]]

class CandidateAnalyzeResponse(BaseModel):
    status: str
    job_id: str
    total_candidates: int
    leaderboard: List[Dict[str, Any]]

class LeaderboardResponse(BaseModel):
    status: str
    job: Optional[Dict[str, Any]] = None
    total_candidates: int
    candidates: List[Dict[str, Any]]

class CandidateDetailsResponse(BaseModel):
    candidate_id: str
    job_id: str
    score: float
    fit: str
    score_breakdown: Dict[str, Any]
    profile: Dict[str, Any]
    evidence: List[Dict[str, Any]]

class HRChatRequest(BaseModel):
    prompt: str

class CandidateShortlistRequest(BaseModel):
    status: Optional[str] = "Shortlisted"


class HRChatResponse(BaseModel):
    response: str
