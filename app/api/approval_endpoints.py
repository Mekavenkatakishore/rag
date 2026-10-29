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
from fastapi import APIRouter, Depends, Query, HTTPException, status, BackgroundTasks, Request

from app.api.deps import require_hr_or_admin
from app.db import hr_db
from app.schemas.approval_schemas import (
    CandidateEmailUpdateRequest,
    CandidateEmailUpdateResponse,
    CandidateApproveRequest,
    CandidateRejectRequest,
    CandidateHoldRequest,
    ShortlistedListResponse,
    MatchDetailsResponse,
    ActionSuccessResponse,
    EmailPreviewResponse,
    EmailLogsResponse
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
    background_tasks: BackgroundTasks,
    http_request: Request,
    payload: Optional[CandidateApproveRequest] = None,
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Approves candidate, updates status to 'Approved & Email Queued', records audit log, and enqueues background email delivery.
    """
    try:
        # Robustly extract body and query parameters to guarantee email is never dropped
        body_data = {}
        try:
            body_data = await http_request.json()
        except Exception:
            pass

        target_email = ""
        if payload and (payload.candidate_email or payload.email):
            target_email = (payload.candidate_email or payload.email).strip()
        if not target_email and body_data:
            target_email = (body_data.get("candidate_email") or body_data.get("email") or "").strip()
        if not target_email:
            target_email = (http_request.query_params.get("candidate_email") or http_request.query_params.get("email") or "").strip()

        hr_notes = None
        if payload and payload.hr_notes:
            hr_notes = payload.hr_notes
        elif body_data and "hr_notes" in body_data:
            hr_notes = body_data.get("hr_notes")
        elif "hr_notes" in http_request.query_params:
            hr_notes = http_request.query_params.get("hr_notes")

        custom_subject = (payload.custom_subject if payload else None) or body_data.get("custom_subject")
        custom_next_step = (payload.custom_next_step if payload else None) or body_data.get("custom_next_step")

        # If a candidate email was provided, persist it immediately to candidate record
        if target_email:
            if not email_service.validate_email_address(target_email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email address '{target_email}'. Please check the format."
                )
            hr_db.update_candidate_email(candidate_id, target_email)

        result = approval_service.approve_candidate(
            candidate_id=candidate_id,
            current_user=current_user,
            hr_notes=hr_notes,
            background_tasks=background_tasks,
            custom_subject=custom_subject,
            custom_next_step=custom_next_step,
            candidate_email=target_email
        )
        return result
    except HTTPException:
        raise
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        elif "already" in err_msg.lower() or "duplicate" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
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


@router.put("/candidates/{candidate_id}/email", response_model=CandidateEmailUpdateResponse)
@router.patch("/candidates/{candidate_id}/email", response_model=CandidateEmailUpdateResponse)
@router.post("/candidates/{candidate_id}/email", response_model=CandidateEmailUpdateResponse)
@router.put("/hr/candidates/{candidate_id}/email", response_model=CandidateEmailUpdateResponse)
@router.patch("/hr/candidates/{candidate_id}/email", response_model=CandidateEmailUpdateResponse)
@router.post("/hr/candidates/{candidate_id}/email", response_model=CandidateEmailUpdateResponse)
async def update_candidate_email_endpoint(
    candidate_id: str,
    http_request: Request,
    request: Optional[CandidateEmailUpdateRequest] = None,
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Directly updates candidate email address and logs audit trail.
    """
    clean_email = ""
    if request and request.email:
        clean_email = request.email.strip()
    if not clean_email:
        try:
            body = await http_request.json()
            clean_email = (body.get("email") or body.get("candidate_email") or "").strip()
        except Exception:
            pass
    if not clean_email:
        clean_email = (http_request.query_params.get("email") or http_request.query_params.get("candidate_email") or "").strip()

    if not clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address cannot be empty."
        )
    if not email_service.validate_email_address(clean_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid email address '{clean_email}'. Please check the format."
        )

    cand = hr_db.get_candidate_by_id(candidate_id)
    if not cand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate '{candidate_id}' not found."
        )

    success = hr_db.update_candidate_email(candidate_id, clean_email)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update email address for candidate '{candidate_id}'."
        )

    approver = current_user.get("username") or "hr_user"
    hr_db.record_audit_log(
        candidate_id=candidate_id,
        job_id=cand.get("job_id", "default_job"),
        action="EMAIL_UPDATED",
        performed_by=approver,
        details={"previous_email": cand.get("email"), "new_email": clean_email}
    )

    return {
        "status": "success",
        "message": f"Candidate email address updated to '{clean_email}'.",
        "candidate_id": candidate_id,
        "email": clean_email
    }


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


@router.post("/candidates/{candidate_id}/retry-email", response_model=ActionSuccessResponse)
@router.post("/hr/candidates/{candidate_id}/retry-email", response_model=ActionSuccessResponse)
async def retry_candidate_email(
    candidate_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Retries failed shortlist email dispatch for a candidate.
    """
    approver = current_user.get("username") or "hr_user"
    try:
        res = email_service.retry_candidate_email(
            candidate_id=candidate_id,
            approver=approver,
            background_tasks=background_tasks
        )
        return {
            "status": "success",
            "message": f"Email retry queued for candidate '{candidate_id}'.",
            "candidate_id": candidate_id,
            "candidate_status": "Approved & Email Queued",
            "approved_by": approver,
            "approved_at": None,
            "email_status": "queued"
        }
    except ValueError as ve:
        err_msg = str(ve)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        elif "already" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err_msg)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except Exception as e:
        logger.error(f"Error retrying email for '{candidate_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email retry failed: {e}"
        )


@router.get("/candidates/{candidate_id}/email-logs", response_model=EmailLogsResponse)
@router.get("/hr/candidates/{candidate_id}/email-logs", response_model=EmailLogsResponse)
async def get_candidate_email_logs(
    candidate_id: str,
    current_user: dict = Depends(require_hr_or_admin)
):
    """
    Returns email dispatch log history for a candidate.
    """
    try:
        logs = hr_db.get_email_logs_for_candidate(candidate_id=candidate_id)
        return {
            "status": "success",
            "candidate_id": candidate_id,
            "total": len(logs),
            "logs": logs
        }
    except Exception as e:
        logger.error(f"Error retrieving email logs for '{candidate_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve email logs: {e}"
        )


