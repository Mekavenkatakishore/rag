from langchain_core.tools import tool
from app.db import hr_db
from app.agent.llm import get_llm
from app.utils.logger import logger

llm = get_llm(temperature=0.3)

@tool
def draft_candidate_email(candidate_id: str, template_type: str = "interview_invite") -> str:
    """
    Drafts a candidate outreach email (e.g. interview invitation, follow-up, or rejection update).
    Does NOT send the email. Email sending requires Human Approval.
    """
    logger.info(f"Agent executing tool 'draft_candidate_email' for candidate_id: '{candidate_id}'")
    try:
        profile = hr_db.get_candidate_profile(candidate_id) or {}
        candidate_name = profile.get("candidate_name", candidate_id)
        email_addr = profile.get("email", f"{candidate_id.lower()}@example.com")
        
        draft = f"To: {email_addr}\n"
        draft += f"Subject: Interview Invitation — RAG Pro HR Team\n\n"
        draft += f"Dear {candidate_name},\n\n"
        draft += f"Thank you for submitting your resume. Based on our evaluation of your skills ({', '.join(profile.get('matched_required_skills', []))}), "
        draft += f"we would like to invite you for an initial interview.\n\n"
        draft += f"Please let us know your availability for a 30-minute conversation this week.\n\n"
        draft += f"Best regards,\nHR Talent Acquisition Team"
        return draft
    except Exception as e:
        logger.error(f"Error in draft_candidate_email tool: {e}")
        return f"Error drafting email: {e}"

@tool
def send_candidate_email(recipient_email: str, email_content: str) -> str:
    """
    Sends the candidate email.
    CRITICAL: Requires explicit Human-in-the-Loop approval before execution.
    """
    logger.info(f"Executing sensitive action tool 'send_candidate_email' to '{recipient_email}'")
    # Mock/simulated email dispatch
    return f"SUCCESS: Email successfully dispatched to {recipient_email}."
