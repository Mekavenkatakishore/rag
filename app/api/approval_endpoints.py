"""
approval_endpoints.py
─────────────────────
FastAPI routes for the human-in-the-loop candidate approval workflow:
  - GET  /shortlisted
  - GET  /candidates/{id}/match-details
  - POST /candidates/{id}/approve
  - POST /candidates/{id}/reject
  - POST /candidates/{id}/hold
  - GET  /candidates/{id}/email-preview
  - GET  /candidates/{id}/audit-logs
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.api.deps import require_hr_or_admin
from app.db import hr_db
from app.schemas.approval_schemas import (
    CandidateApproveRequest,
    CandidateRejectRequest,
    CandidateHoldRequest,
    ShortlistedListResponse,
    MatchDetailsResponse,
    ActionSuccessResponse,
    EmailPreviewResponse
)
from app.services.hr import approval_service, email_service
from app.utils.logger import logger

router = APIRouter()

@router.get("/shortlisted", response_model=ShortlistedListResponse)
@router.get("/hr/shortlisted", response_model=ShortlistedListResponse)
@router.get("/hr/jobs/{job_id}/shortlisted", response_model=ShortlistedListResponse)
async def list_shortlisted_candidates(
    job_id: Optional[str] = None,
    status: str = Query("Pending Approval", description="Filter by status ('Pending Approval', 'Approved', 'On Hold', 'Rejected', or 'all')"),
    sort_by: str = Query("score", description="Sort by 'score', 'date', or 'name'"),
    sort_order: str = Query("desc", description="Sort order 'desc' or 'asc'"),
    min_score: Optional[float] = Query(None, description="Optional minimum score filter"),
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Returns candidate list for the approval review table with filtering and sorting.
    """
    try:
        candidates = hr_db.get_shortlisted_for_approval(
            job_id=job_id,
            status_filter=status,
            sort_by=sort_by,
            sort_order=sort_order,
            min_score=min_score
        )
        return {
            "status": "success",
            "total": len(candidates),
            "filter_status": status,
            "candidates": candidates
        }
    except Exception as e:
        logger.error(f"Error fetching shortlisted review candidates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch candidates for approval: {e}"
        )


@router.get("/candidates/{candidate_id}/match-details", response_model=MatchDetailsResponse)
@router.get("/hr/candidates/{candidate_id}/match-details", response_model=MatchDetailsResponse)
async def get_candidate_match_details(
    candidate_id: str,
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Returns full explainable match details: score breakdown, criteria pass/fail matrix,
    matched/missing/bonus skills, experience difference, AI summary, red flags, and resume preview.
    """
    try:
        details = approval_service.get_candidate_match_details(candidate_id)
        return details
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error fetching match details for '{candidate_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load candidate match details: {e}"
        )


@router.post("/candidates/{candidate_id}/approve", response_model=ActionSuccessResponse)
@router.post("/hr/candidates/{candidate_id}/approve", response_model=ActionSuccessResponse)
async def approve_candidate(
    candidate_id: str,
    request: CandidateApproveRequest = CandidateApproveRequest(),
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Approves candidate, updates status to 'Approved', records audit log, and stubs email dispatch.
    """
    try:
        result = approval_service.approve_candidate(
            candidate_id=candidate_id,
            current_user=current_user,
            hr_notes=request.hr_notes
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error approving candidate '{candidate_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval action failed: {e}"
        )


@router.post("/candidates/{candidate_id}/reject", response_model=ActionSuccessResponse)
@router.post("/hr/candidates/{candidate_id}/reject", response_model=ActionSuccessResponse)
async def reject_candidate(
    candidate_id: str,
    request: CandidateRejectRequest = CandidateRejectRequest(),
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Rejects candidate, updates status to 'Rejected', and records audit log.
    """
    try:
        result = approval_service.reject_candidate(
            candidate_id=candidate_id,
            current_user=current_user,
            hr_notes=request.hr_notes,
            rejection_reason=request.rejection_reason
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error rejecting candidate '{candidate_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rejection action failed: {e}"
        )


@router.post("/candidates/{candidate_id}/hold", response_model=ActionSuccessResponse)
@router.post("/hr/candidates/{candidate_id}/hold", response_model=ActionSuccessResponse)
async def hold_candidate(
    candidate_id: str,
    request: CandidateHoldRequest = CandidateHoldRequest(),
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Places candidate On Hold with optional notes.
    """
    try:
        result = approval_service.hold_candidate(
            candidate_id=candidate_id,
            current_user=current_user,
            hr_notes=request.hr_notes
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error putting candidate '{candidate_id}' on hold: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hold action failed: {e}"
        )


@router.get("/candidates/{candidate_id}/email-preview", response_model=EmailPreviewResponse)
@router.get("/hr/candidates/{candidate_id}/email-preview", response_model=EmailPreviewResponse)
async def preview_candidate_email(
    candidate_id: str,
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Renders HTML and plain-text email preview for HR review before sending.
    """
    try:
        match_details = approval_service.get_candidate_match_details(candidate_id)
        preview = email_service.preview_shortlist_email(
            candidate=match_details,
            current_user=current_user,
            job_title=match_details.get("role")
        )
        return preview
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error previewing email for '{candidate_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate email preview: {e}"
        )


@router.get("/candidates/{candidate_id}/audit-logs")
@router.get("/hr/candidates/{candidate_id}/audit-logs")
async def get_candidate_audit_logs(
    candidate_id: str,
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Returns audit trail history for candidate.
    """
    try:
        logs = hr_db.get_audit_logs(candidate_id=candidate_id)
        return {"status": "success", "candidate_id": candidate_id, "logs": logs}
    except Exception as e:
        logger.error(f"Error retrieving audit logs for '{candidate_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit logs: {e}"
        )

