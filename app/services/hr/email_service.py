"""
email_service.py
────────────────
Modular email service for candidate notifications.
Phase 1: Generates HTML/text preview templates and stubs actual delivery.
Phase 2: Will connect to SMTP server with retries, logging, and rate limiting.
"""

from typing import Dict, Any, Optional
from app.utils.logger import logger

DEFAULT_COMPANY_NAME = "Enterprise AI Systems"
DEFAULT_NEXT_STEP = "We would love to invite you to an initial 30-minute technical conversation with our engineering lead."
DEFAULT_HR_CONTACT = "hr@enterprise-ai.example.com"

def render_shortlist_email(
    candidate_name: str,
    job_title: str,
    company_name: str = DEFAULT_COMPANY_NAME,
    hr_name: str = "HR Talent Acquisition Team",
    hr_contact: str = DEFAULT_HR_CONTACT,
    next_step: str = DEFAULT_NEXT_STEP
) -> Dict[str, str]:
    """
    Renders professional HTML and plain-text shortlist email templates.
    """
    subject = f"Congratulations! You've been Shortlisted for {job_title} at {company_name}"
    
    plain_text = f"""Dear {candidate_name},

Thank you for your interest in the {job_title} role at {company_name}.

We have reviewed your application and resume. Based on your impressive skill set, background, and demonstrated project experience, we are delighted to inform you that you have been SHORTLISTED for this position!

Next Steps:
{next_step}

Our talent team will be in touch shortly to coordinate schedule availability. If you have any immediate questions, feel free to reply directly to this email or reach us at {hr_contact}.

Best regards,
{hr_name}
Talent Acquisition Team
{company_name}
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #0f172a; margin: 0; padding: 24px; color: #f1f5f9; }}
    .container {{ max-width: 600px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; }}
    .header {{ border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 24px; }}
    .logo-badge {{ display: inline-block; background: #6366f1; color: #ffffff; padding: 6px 14px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-bottom: 12px; }}
    h1 {{ color: #ffffff; font-size: 22px; margin: 0 0 8px 0; }}
    p {{ line-height: 1.6; color: #cbd5e1; font-size: 15px; margin: 12px 0; }}
    .highlight-card {{ background: rgba(99, 102, 241, 0.08); border-left: 4px solid #6366f1; border-radius: 6px; padding: 16px; margin: 20px 0; }}
    .highlight-title {{ font-weight: 600; color: #a5b4fc; margin-bottom: 6px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }}
    .footer {{ margin-top: 32px; pt-4; border-top: 1px solid #334155; font-size: 13px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="logo-badge">{company_name} Careers</div>
      <h1>Congratulations, {candidate_name}!</h1>
    </div>
    <p>Thank you for taking the time to apply for the <strong>{job_title}</strong> opening with us.</p>
    <p>Our hiring and evaluation team has thoroughly reviewed your resume and profile. We were genuinely impressed with your technical capabilities, past project impact, and alignment with our team goals.</p>
    
    <div class="highlight-card">
      <div class="highlight-title">Your Next Step</div>
      <p style="margin: 0; color: #f1f5f9;">{next_step}</p>
    </div>

    <p>We look forward to speaking with you! If you have any scheduling constraints or questions in the meantime, please contact us at <a href="mailto:{hr_contact}" style="color: #818cf8; text-decoration: none;">{hr_contact}</a>.</p>

    <div class="footer">
      <p style="margin: 0;">Sent on behalf of <strong>{hr_name}</strong> &bull; {company_name}</p>
    </div>
  </div>
</body>
</html>"""

    return {
        "subject": subject,
        "plain_text_body": plain_text,
        "html_body": html
    }

def preview_shortlist_email(
    candidate: dict,
    current_user: Optional[dict] = None,
    job_title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates preview data for an HR user before they confirm approval.
    """
    cand_name = candidate.get("name") or candidate.get("filename") or "Candidate"
    cand_email = candidate.get("email") or "candidate@example.com"
    role_title = job_title or candidate.get("job_title") or candidate.get("role") or "Engineering Role"
    hr_username = (current_user.get("username") if current_user else "HR Talent Team").title()

    rendered = render_shortlist_email(
        candidate_name=cand_name,
        job_title=role_title,
        hr_name=f"{hr_username} (Talent Acquisition)"
    )

    return {
        "status": "success",
        "candidate_id": candidate.get("candidate_id"),
        "candidate_name": cand_name,
        "to_email": cand_email,
        "subject": rendered["subject"],
        "job_title": role_title,
        "company_name": DEFAULT_COMPANY_NAME,
        "next_step": DEFAULT_NEXT_STEP,
        "hr_name": hr_username,
        "hr_contact": DEFAULT_HR_CONTACT,
        "html_body": rendered["html_body"],
        "plain_text_body": rendered["plain_text_body"]
    }

def send_shortlist_email_stub(
    candidate_id: str,
    to_email: str,
    candidate_name: str,
    job_title: str,
    approved_by: str
) -> Dict[str, Any]:
    """
    Phase 1 Stub: records that email was triggered and approved without sending over SMTP.
    Phase 2 will replace this with SMTP worker dispatch.
    """
    logger.info(
        f"[EMAIL STUB - Phase 1] Shortlist approval email queued for candidate '{candidate_id}' "
        f"({candidate_name} <{to_email}>) for role '{job_title}', approved by '{approved_by}'."
    )
    return {
        "sent": False,
        "status": "stubbed",
        "message": f"Phase 1 approval recorded. Shortlist email to {to_email} is stubbed (SMTP will be enabled in Phase 2)."
    }

