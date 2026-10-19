from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CandidateApproveRequest(BaseModel):
    hr_notes: Optional[str] = Field(default=None, description="Optional notes written by the approving HR user")

class CandidateRejectRequest(BaseModel):
    hr_notes: Optional[str] = Field(default=None, description="Optional internal notes")
    rejection_reason: Optional[str] = Field(default="Candidate qualifications did not meet role requirements", description="Reason for rejection")

class CandidateHoldRequest(BaseModel):
    hr_notes: Optional[str] = Field(default=None, description="Optional notes for putting candidate on hold")

class ShortlistedCandidateItem(BaseModel):
    candidate_id: str
    job_id: str
    job_title: str
    name: str
    email: str
    role: str
    filename: str
    status: str
    score: float
    fit_category: str
    top_matched_skills: List[str] = []
    date: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    hr_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    summary: Optional[str] = None
    rank: Optional[int] = None

class ShortlistedListResponse(BaseModel):
    status: str = "success"
    total: int
    filter_status: str
    candidates: List[ShortlistedCandidateItem]

class MatchedSkillEvidence(BaseModel):
    skill: str
    evidence: str
    matched: bool = True
    document: Optional[str] = None
    page: Optional[int] = 1

class CriteriaRuleResult(BaseModel):
    rule: str
    requirement: str
    actual: str
    passed: bool

class ExperienceMatchDetail(BaseModel):
    required_years: float
    actual_years: float
    difference_years: float
    meets: bool
    status: str

class MatchDetailsResponse(BaseModel):
    status: str = "success"
    candidate_id: str
    job_id: str
    name: str
    email: str
    role: str
    filename: str
    candidate_status: str
    overall_score: float
    fit_category: str
    score_breakdown: Dict[str, Any]
    matched_skills: List[Dict[str, Any]]
    missing_skills: List[str]
    bonus_skills: List[str]
    experience_match: Dict[str, Any]
    criteria_results: List[Dict[str, Any]]
    summary: str
    red_flags: List[str]
    jd_requirements: Dict[str, Any]
    resume_preview_text: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    hr_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

class ActionSuccessResponse(BaseModel):
    status: str = "success"
    message: str
    candidate_id: str
    candidate_status: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    email_status: str = "stubbed"

class EmailPreviewResponse(BaseModel):
    status: str = "success"
    candidate_id: str
    candidate_name: str
    to_email: str
    subject: str
    job_title: str
    company_name: str
    next_step: str
    hr_name: str
    hr_contact: str
    html_body: str
    plain_text_body: str

