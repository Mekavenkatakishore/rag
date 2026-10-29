"""
email_service.py
────────────────
SMTP email service for human-approved candidate shortlist notifications.
Features:
  1. Environment-driven SMTP configuration (Host, Port, User, Password, TLS/SSL).
  2. HTML + plain-text shortlist notification templates.
  3. Pre-send preview and custom content overrides.
  4. Robust email address validation (regex + syntax checks).
  5. Idempotency guard against duplicate email sends.
  6. Rate-limited background worker with 3-attempt exponential backoff retries.
  7. Full audit logging and email_logs persistence.
"""

import re
import time
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional

from fastapi import BackgroundTasks

from app.core.config import settings
from app.db import hr_db
from app.utils.logger import logger

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

DEFAULT_COMPANY_NAME = "Enterprise AI Systems"
DEFAULT_NEXT_STEP = "We would love to invite you to an initial 30-minute technical conversation with our engineering lead."
DEFAULT_HR_CONTACT = "hr@enterprise-ai.example.com"
MAX_ATTEMPTS = 3
RATE_LIMIT_DELAY_SECONDS = 0.5

def get_default_hr_contact() -> str:
    """Returns configured Gmail / sender address or default fallback."""
    return settings.SMTP_FROM_EMAIL or settings.SMTP_USER or DEFAULT_HR_CONTACT


def validate_email_address(email: str) -> bool:
    """Validates candidate email address format."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email))


def render_shortlist_email(
    candidate_name: str,
    job_title: str,
    company_name: str = DEFAULT_COMPANY_NAME,
    hr_name: str = "HR Talent Acquisition Team",
    hr_contact: Optional[str] = None,
    next_step: str = DEFAULT_NEXT_STEP,
    custom_subject: Optional[str] = None
) -> Dict[str, str]:
    """Renders professional HTML and plain-text shortlist email templates."""
    contact_email = hr_contact or get_default_hr_contact()
    subject = custom_subject or f"Congratulations! You've been Shortlisted for {job_title} at {company_name}"
    
    plain_text = f"""Dear {candidate_name},

Thank you for your interest in the {job_title} role at {company_name}.

We have reviewed your application and resume. Based on your impressive skill set, background, and demonstrated project experience, we are delighted to inform you that you have been SHORTLISTED for this position!

Next Steps:
{next_step}

Our talent team will be in touch shortly to coordinate schedule availability. If you have any immediate questions, feel free to reply directly to this email or reach us at {contact_email}.

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
    .footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #334155; font-size: 13px; color: #64748b; }}
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

    <p>We look forward to speaking with you! If you have any scheduling constraints or questions in the meantime, please contact us at <a href="mailto:{contact_email}" style="color: #818cf8; text-decoration: none;">{contact_email}</a>.</p>

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
    """Generates preview data for an HR user before they confirm approval."""
    cand_name = candidate.get("name") or candidate.get("filename") or "Candidate"
    cand_email = candidate.get("email") or "candidate@example.com"
    role_title = job_title or candidate.get("job_title") or candidate.get("role") or "Engineering Role"
    hr_username = (current_user.get("username") if current_user else "HR Talent Team").title()
    effective_contact = get_default_hr_contact()

    rendered = render_shortlist_email(
        candidate_name=cand_name,
        job_title=role_title,
        hr_name=f"{hr_username} (Talent Acquisition)",
        hr_contact=effective_contact
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
        "hr_contact": effective_contact,
        "html_body": rendered["html_body"],
        "plain_text_body": rendered["plain_text_body"]
    }


def send_smtp_email(
    to_email: str,
    subject: str,
    html_body: str,
    plain_text_body: str,
    from_name: Optional[str] = None,
    from_email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends a multipart MIME email over SMTP with TLS or SSL support (e.g. Gmail SMTP).
    Uses settings from app.core.config.
    """
    sender_name = from_name or settings.SMTP_FROM_NAME or "Talent Acquisition Team"
    sender_addr = from_email or settings.SMTP_FROM_EMAIL or settings.SMTP_USER
    if not sender_addr:
        raise ValueError(
            "SMTP sender address not configured. Please set SMTP_USER (your Gmail address) or SMTP_FROM_EMAIL in .env."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_addr}>"
    msg["To"] = to_email

    part1 = MIMEText(plain_text_body, "plain", "utf-8")
    part2 = MIMEText(html_body, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    if settings.SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)

    try:
        server.ehlo()
        if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
            server.starttls()
            server.ehlo()

        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            # Strip spaces from password (Google 16-character App Passwords are generated as 4x4 with spaces)
            clean_password = settings.SMTP_PASSWORD.replace(" ", "")
            server.login(settings.SMTP_USER, clean_password)
        elif "gmail" in settings.SMTP_HOST.lower():
            raise ValueError(
                "Gmail SMTP requires both SMTP_USER (your Gmail address) and SMTP_PASSWORD (a 16-character App Password). Please set them in your .env file."
            )

        server.sendmail(sender_addr, [to_email], msg.as_string())
        return {"success": True}
    finally:
        try:
            server.quit()
        except Exception:
            pass


def deliver_shortlist_email_task(
    candidate_id: str,
    log_id: int,
    to_email: str,
    subject: str,
    html_body: str,
    plain_text_body: str,
    approver: str,
    job_id: Optional[str] = None,
    backoff_factor: float = 1.0,
    rate_limit_delay: float = RATE_LIMIT_DELAY_SECONDS
):
    """
    Background worker task:
      - Applies rate limiting.
      - Tries up to MAX_ATTEMPTS (3) with exponential backoff.
      - Updates email_logs table with status, error, and attempts.
      - On success: updates candidate_status to 'Shortlisted - Email Sent' and logs audit.
      - On final failure: updates candidate_status to 'Shortlisted - Email Failed' and logs audit.
    """
    if rate_limit_delay > 0:
        time.sleep(rate_limit_delay)

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            logger.info(f"[EMAIL WORKER] Attempt {attempt}/{MAX_ATTEMPTS} sending shortlist email to {to_email} (Candidate: {candidate_id})...")
            send_smtp_email(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                plain_text_body=plain_text_body
            )

            # Success!
            now = datetime.datetime.utcnow().isoformat()
            hr_db.update_email_log(
                log_id=log_id,
                status="sent",
                attempts=attempt,
                sent_at=now,
                error=None
            )
            hr_db.update_candidate_approval(
                candidate_id=candidate_id,
                status="Shortlisted - Email Sent",
                approved_by=approver,
                job_id=job_id
            )
            hr_db.record_audit_log(
                candidate_id=candidate_id,
                job_id=job_id or "default",
                action="SHORTLIST_EMAIL_SENT",
                performed_by=approver,
                details={
                    "to_email": to_email,
                    "subject": subject,
                    "attempts": attempt,
                    "status": "sent"
                }
            )
            logger.info(f"[EMAIL WORKER] Successfully sent email to {to_email} on attempt {attempt}.")
            return {"success": True, "attempts": attempt}

        except Exception as e:
            last_error = e
            logger.warning(f"[EMAIL WORKER] Attempt {attempt}/{MAX_ATTEMPTS} failed for {to_email}: {e}")
            hr_db.update_email_log(
                log_id=log_id,
                status="pending" if attempt < MAX_ATTEMPTS else "failed",
                error=str(e),
                attempts=attempt
            )
            if attempt < MAX_ATTEMPTS and backoff_factor > 0:
                sleep_seconds = backoff_factor * (2 ** (attempt - 1))
                logger.info(f"[EMAIL WORKER] Backing off for {sleep_seconds:.1f}s before retry...")
                time.sleep(sleep_seconds)

    # If all attempts exhausted:
    error_msg = f"Failed to send email after {MAX_ATTEMPTS} attempts. Last error: {last_error}"
    logger.error(f"[EMAIL WORKER] Exhausted retries for {to_email}: {error_msg}")
    hr_db.update_email_log(
        log_id=log_id,
        status="failed",
        error=error_msg,
        attempts=MAX_ATTEMPTS
    )
    hr_db.update_candidate_approval(
        candidate_id=candidate_id,
        status="Shortlisted - Email Failed",
        approved_by=approver,
        job_id=job_id
    )
    hr_db.record_audit_log(
        candidate_id=candidate_id,
        job_id=job_id or "default",
        action="SHORTLIST_EMAIL_FAILED",
        performed_by=approver,
        details={
            "to_email": to_email,
            "error": error_msg,
            "attempts": MAX_ATTEMPTS
        }
    )
    return {"success": False, "error": error_msg, "attempts": MAX_ATTEMPTS}


def enqueue_candidate_shortlist_email(
    candidate: dict,
    approver: str,
    background_tasks: BackgroundTasks,
    custom_subject: Optional[str] = None,
    custom_next_step: Optional[str] = None,
    custom_html: Optional[str] = None,
    custom_plain_text: Optional[str] = None,
    backoff_factor: float = 1.0,
    rate_limit_delay: float = RATE_LIMIT_DELAY_SECONDS
) -> Dict[str, Any]:
    """
    Enqueues candidate shortlist email for background SMTP delivery:
      1. Validates email format.
      2. Enforces idempotency: prevents duplicate sends if already successfully sent.
      3. Renders templates or applies custom overrides.
      4. Creates pending email_logs entry.
      5. Updates candidate status to 'Approved & Email Queued'.
      6. Adds background task to dispatch email with 3-attempt backoff retries.
    """
    candidate_id = candidate["candidate_id"]
    job_id = candidate.get("job_id")
    to_email = (candidate.get("email") or "").strip()

    # 1. Email validation
    if not validate_email_address(to_email):
        raise ValueError(f"Invalid email address '{to_email}' for candidate '{candidate_id}'.")

    # 2. Duplicate send / idempotency guard
    if hr_db.has_successful_email_sent(candidate_id):
        raise ValueError(f"Shortlist email has already been successfully sent to candidate '{candidate_id}'.")

    # 3. Render or custom overrides
    cand_name = candidate.get("name") or candidate.get("filename") or "Candidate"
    job_title = candidate.get("job_title") or candidate.get("role") or "Shortlisted Position"

    if custom_html and custom_plain_text and custom_subject:
        subject = custom_subject
        html_body = custom_html
        plain_text_body = custom_plain_text
    else:
        rendered = render_shortlist_email(
            candidate_name=cand_name,
            job_title=job_title,
            next_step=custom_next_step or DEFAULT_NEXT_STEP,
            custom_subject=custom_subject
        )
        subject = rendered["subject"]
        html_body = rendered["html_body"]
        plain_text_body = rendered["plain_text_body"]

    # 4. Insert pending log in email_logs
    log_id = hr_db.create_email_log(
        candidate_id=candidate_id,
        job_id=job_id,
        to_email=to_email,
        subject=subject,
        sent_by=approver,
        status="pending",
        attempts=0
    )

    # 5. Set status to 'Approved & Email Queued'
    hr_db.update_candidate_approval(
        candidate_id=candidate_id,
        status="Approved & Email Queued",
        approved_by=approver,
        job_id=job_id
    )

    # 6. Enqueue background worker task
    background_tasks.add_task(
        deliver_shortlist_email_task,
        candidate_id=candidate_id,
        log_id=log_id,
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        plain_text_body=plain_text_body,
        approver=approver,
        job_id=job_id,
        backoff_factor=backoff_factor,
        rate_limit_delay=rate_limit_delay
    )

    return {
        "status": "queued",
        "log_id": log_id,
        "to_email": to_email,
        "subject": subject,
        "message": f"Shortlist email for {cand_name} ({to_email}) queued for delivery."
    }


def retry_candidate_email(
    candidate_id: str,
    approver: str,
    background_tasks: BackgroundTasks,
    backoff_factor: float = 1.0,
    rate_limit_delay: float = 0.0
) -> Dict[str, Any]:
    """
    Retries email delivery for a candidate whose previous email attempt failed.
    """
    candidate = hr_db.get_candidate_by_id(candidate_id)
    if not candidate:
        raise ValueError(f"Candidate ID '{candidate_id}' not found.")

    # Check if candidate already has a successful send
    if hr_db.has_successful_email_sent(candidate_id):
        raise ValueError(f"Candidate '{candidate_id}' already has a successfully delivered email.")

    to_email = (candidate.get("email") or "").strip()
    if not validate_email_address(to_email):
        raise ValueError(f"Candidate email '{to_email}' is invalid.")

    # Re-queue
    return enqueue_candidate_shortlist_email(
        candidate=candidate,
        approver=approver,
        background_tasks=background_tasks,
        backoff_factor=backoff_factor,
        rate_limit_delay=rate_limit_delay
    )


def send_shortlist_email_stub(
    candidate_id: str,
    to_email: str,
    candidate_name: str,
    job_title: str,
    approved_by: str
) -> Dict[str, Any]:
    """Backward compatibility stub."""
    logger.info(
        f"[EMAIL STUB] Shortlist approval email queued for candidate '{candidate_id}' "
        f"({candidate_name} <{to_email}>) for role '{job_title}', approved by '{approved_by}'."
    )
    return {
        "sent": False,
        "status": "stubbed",
        "message": f"Shortlist email to {to_email} recorded."
    }
