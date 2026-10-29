"""
test_smtp_email.py
──────────────────
Comprehensive unit test suite for Phase 2 SMTP Email Delivery System:
  1. Email format validation (syntax, length, edge cases).
  2. HTML and plain-text template rendering with variable interpolation.
  3. Successful SMTP delivery via mock SMTP server.
  4. Transient SMTP failure recovery with exponential backoff retries.
  5. Permanent SMTP failure after exhausting 3 attempts (status 'Shortlisted - Email Failed').
  6. Idempotency guard preventing duplicate sends on re-approval / double click.
  7. Rejection of invalid email addresses.
  8. Retry endpoint re-queuing failed email dispatches.
  9. Role-based access control (RBAC) ensuring non-HR users are blocked.
"""

import unittest
from unittest.mock import patch, MagicMock
import smtplib
from fastapi import BackgroundTasks, HTTPException

from app.db import hr_db, user_db
from app.services.hr import email_service, approval_service
from app.api.deps import require_hr_or_admin


class TestSMTPEmailSystem(unittest.TestCase):

    def setUp(self):
        """Initialize database and seed test job and candidates."""
        user_db.initialize_db()
        hr_db.initialize_hr_db()

        self.test_job_id = "test_job_smtp_001"
        self.hr_user = {"id": 1, "username": "hr_recruiter", "role": "hr", "email": "recruiter@example.com"}
        self.admin_user = {"id": 2, "username": "admin_user", "role": "admin", "email": "admin@example.com"}
        self.viewer_user = {"id": 3, "username": "guest_viewer", "role": "viewer", "email": "viewer@example.com"}

        # Create test job
        hr_db.create_job(
            job_id=self.test_job_id,
            user_id=1,
            title="Principal AI Platform Engineer",
            jd_filename="principal_ai.pdf",
            jd_parsed={"title": "Principal AI Platform Engineer", "required_skills": ["Python", "FastAPI"]}
        )

        # Seed candidates
        self.cand_valid_id = "C_SMTP_VALID"
        self.cand_invalid_id = "C_SMTP_INVALID"
        self.cand_fail_id = "C_SMTP_FAIL"

        hr_db.save_candidate(
            self.cand_valid_id,
            self.test_job_id,
            "Sophia Lin",
            "sophia.lin@testdomain.com",
            "sophia_resume.pdf"
        )
        hr_db.update_candidate_shortlist_status(self.test_job_id, self.cand_valid_id, "Shortlisted (Pending Approval)")

        hr_db.save_candidate(
            self.cand_invalid_id,
            self.test_job_id,
            "Bad Email Candidate",
            "not-an-email-address",
            "bad_email.pdf"
        )
        hr_db.update_candidate_shortlist_status(self.test_job_id, self.cand_invalid_id, "Shortlisted (Pending Approval)")

        hr_db.save_candidate(
            self.cand_fail_id,
            self.test_job_id,
            "Dave Network Fail",
            "dave@testdomain.com",
            "dave_resume.pdf"
        )
        hr_db.update_candidate_shortlist_status(self.test_job_id, self.cand_fail_id, "Shortlisted (Pending Approval)")

        # Ensure test SMTP credentials are populated for mock test runs
        from app.core.config import settings
        settings.SMTP_USER = "recruiter@gmail.com"
        settings.SMTP_PASSWORD = "app_pass_1234"
        settings.SMTP_FROM_EMAIL = "recruiter@gmail.com"

    def test_email_validation(self):
        """Verify robust email address validation rules."""
        valid_emails = [
            "sophia@example.com",
            "firstname.lastname@domain.co.uk",
            "user+tag@domain.org",
            "hr_team-2@sub.domain.io"
        ]
        invalid_emails = [
            "",
            None,
            "notanemail",
            "@domain.com",
            "user@",
            "user@domain",
            "user@.com",
            "spaces in@domain.com",
            "a" * 255 + "@domain.com"
        ]

        for email in valid_emails:
            self.assertTrue(email_service.validate_email_address(email), f"Expected '{email}' to be valid.")

        for email in invalid_emails:
            self.assertFalse(email_service.validate_email_address(email), f"Expected '{email}' to be invalid.")

    def test_render_shortlist_email_template(self):
        """Verify HTML and plain-text template interpolation with variables."""
        rendered = email_service.render_shortlist_email(
            candidate_name="Sophia Lin",
            job_title="Principal AI Engineer",
            company_name="Acme AI Corp",
            hr_name="HR Talent Team",
            hr_contact="recruiting@acme-ai.com",
            next_step="Technical discussion with CTO on Tuesday."
        )

        self.assertIn("Principal AI Engineer", rendered["subject"])
        self.assertIn("Sophia Lin", rendered["plain_text_body"])
        self.assertIn("Technical discussion with CTO", rendered["plain_text_body"])
        self.assertIn("recruiting@acme-ai.com", rendered["plain_text_body"])

        # Check HTML structure
        self.assertIn("<!DOCTYPE html>", rendered["html_body"])
        self.assertIn("Sophia Lin", rendered["html_body"])
        self.assertIn("Acme AI Corp", rendered["html_body"])
        self.assertIn("Technical discussion with CTO", rendered["html_body"])

    @patch("smtplib.SMTP")
    def test_smtp_send_success(self, mock_smtp_class):
        """Verify successful background SMTP delivery updates email_logs and candidate status."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        # 1. Enqueue email
        candidate = hr_db.get_candidate_by_id(self.cand_valid_id)
        bg_tasks = BackgroundTasks()
        res = email_service.enqueue_candidate_shortlist_email(
            candidate=candidate,
            approver="hr_recruiter",
            background_tasks=bg_tasks,
            backoff_factor=0.0,
            rate_limit_delay=0.0
        )
        self.assertEqual(res["status"], "queued")
        log_id = res["log_id"]

        # Candidate is immediately marked as queued
        cand_queued = hr_db.get_candidate_by_id(self.cand_valid_id)
        self.assertEqual(cand_queued["candidate_status"], "Approved & Email Queued")

        # 2. Execute background task synchronously
        for task in bg_tasks.tasks:
            task()

        # Verify SMTP server interaction
        mock_server.sendmail.assert_called_once()

        # 3. Verify email_logs table updated
        logs = hr_db.get_email_logs_for_candidate(self.cand_valid_id)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["status"], "sent")
        self.assertEqual(logs[0]["attempts"], 1)
        self.assertIsNotNone(logs[0]["sent_at"])
        self.assertIsNone(logs[0]["error"])

        # 4. Verify candidate status updated to 'Shortlisted - Email Sent'
        cand_updated = hr_db.get_candidate_by_id(self.cand_valid_id)
        self.assertEqual(cand_updated["candidate_status"], "Shortlisted - Email Sent")

        # 5. Verify audit trail logged
        audit_logs = hr_db.get_audit_logs(candidate_id=self.cand_valid_id)
        actions = [a["action"] for a in audit_logs]
        self.assertIn("SHORTLIST_EMAIL_SENT", actions)

    @patch("smtplib.SMTP")
    def test_smtp_send_retry_and_recover(self, mock_smtp_class):
        """Verify transient failure on attempt 1 retries and succeeds on attempt 2."""
        mock_server = MagicMock()
        # First sendmail raises temporary SMTPException; second succeeds
        mock_server.sendmail.side_effect = [smtplib.SMTPException("Connection reset by peer"), None]
        mock_smtp_class.return_value = mock_server

        candidate = hr_db.get_candidate_by_id(self.cand_fail_id)
        bg_tasks = BackgroundTasks()
        res = email_service.enqueue_candidate_shortlist_email(
            candidate=candidate,
            approver="hr_recruiter",
            background_tasks=bg_tasks,
            backoff_factor=0.0,
            rate_limit_delay=0.0
        )
        for task in bg_tasks.tasks:
            task()

        self.assertEqual(mock_server.sendmail.call_count, 2)

        # Verify log shows 2 attempts and sent status
        logs = hr_db.get_email_logs_for_candidate(self.cand_fail_id)
        self.assertEqual(logs[0]["status"], "sent")
        self.assertEqual(logs[0]["attempts"], 2)

        # Candidate status is sent
        cand = hr_db.get_candidate_by_id(self.cand_fail_id)
        self.assertEqual(cand["candidate_status"], "Shortlisted - Email Sent")

    @patch("smtplib.SMTP")
    def test_smtp_permanent_failure_after_3_attempts(self, mock_smtp_class):
        """Verify permanent SMTP failure retries 3 times then sets status to 'Shortlisted - Email Failed'."""
        mock_server = MagicMock()
        mock_server.sendmail.side_effect = smtplib.SMTPConnectError(421, "Service not available")
        mock_smtp_class.return_value = mock_server

        cand_id = "C_PERM_FAIL"
        hr_db.save_candidate(cand_id, self.test_job_id, "Failure Test", "fail@domain.com", "fail.pdf")

        candidate = hr_db.get_candidate_by_id(cand_id)
        bg_tasks = BackgroundTasks()
        res = email_service.enqueue_candidate_shortlist_email(
            candidate=candidate,
            approver="hr_recruiter",
            background_tasks=bg_tasks,
            backoff_factor=0.0,
            rate_limit_delay=0.0
        )
        for task in bg_tasks.tasks:
            task()

        self.assertEqual(mock_server.sendmail.call_count, 3)

        # Verify email log is marked failed with 3 attempts and error message
        logs = hr_db.get_email_logs_for_candidate(cand_id)
        self.assertEqual(logs[0]["status"], "failed")
        self.assertEqual(logs[0]["attempts"], 3)
        self.assertIn("Failed to send email after 3 attempts", logs[0]["error"])

        # Verify candidate status
        cand = hr_db.get_candidate_by_id(cand_id)
        self.assertEqual(cand["candidate_status"], "Shortlisted - Email Failed")

        # Verify audit log
        audit_logs = hr_db.get_audit_logs(candidate_id=cand_id)
        actions = [a["action"] for a in audit_logs]
        self.assertIn("SHORTLIST_EMAIL_FAILED", actions)

    @patch("smtplib.SMTP")
    def test_duplicate_send_idempotency_guard(self, mock_smtp_class):
        """Verify double-click / re-approval guard prevents duplicate email dispatches."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        candidate = hr_db.get_candidate_by_id(self.cand_valid_id)
        bg_tasks = BackgroundTasks()
        email_service.enqueue_candidate_shortlist_email(
            candidate=candidate,
            approver="hr_recruiter",
            background_tasks=bg_tasks,
            backoff_factor=0.0,
            rate_limit_delay=0.0
        )
        for task in bg_tasks.tasks:
            task()

        self.assertTrue(hr_db.has_successful_email_sent(self.cand_valid_id))

        # Attempt to enqueue or approve again -> must raise ValueError
        with self.assertRaises(ValueError) as ctx:
            email_service.enqueue_candidate_shortlist_email(
                candidate=candidate,
                approver="hr_recruiter",
                background_tasks=BackgroundTasks()
            )
        self.assertIn("already been successfully sent", str(ctx.exception))

        # Ensure sendmail was only called once for this candidate
        self.assertEqual(mock_server.sendmail.call_count, 1)

    def test_invalid_email_rejected(self):
        """Verify that attempting to enqueue an email for an invalid address is rejected immediately."""
        candidate = hr_db.get_candidate_by_id(self.cand_invalid_id)
        bg_tasks = BackgroundTasks()
        with self.assertRaises(ValueError) as ctx:
            email_service.enqueue_candidate_shortlist_email(
                candidate=candidate,
                approver="hr_recruiter",
                background_tasks=bg_tasks
            )
        self.assertIn("Invalid email address", str(ctx.exception))

    @patch("smtplib.SMTP")
    def test_retry_candidate_email(self, mock_smtp_class):
        """Verify that failed email can be re-queued and delivered using retry_candidate_email."""
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        # Simulate failed candidate
        cand_id = "C_RETRY_TEST"
        hr_db.save_candidate(cand_id, self.test_job_id, "Retry Candidate", "retry@domain.com", "retry.pdf")
        hr_db.update_candidate_approval(cand_id, status="Shortlisted - Email Failed", approved_by="hr_recruiter")
        hr_db.create_email_log(cand_id, self.test_job_id, "retry@domain.com", "Subject", "hr_recruiter", status="failed", attempts=3)

        bg_tasks = BackgroundTasks()
        res = email_service.retry_candidate_email(
            candidate_id=cand_id,
            approver="hr_recruiter",
            background_tasks=bg_tasks,
            backoff_factor=0.0,
            rate_limit_delay=0.0
        )
        self.assertEqual(res["status"], "queued")

        # Run worker
        for task in bg_tasks.tasks:
            task()

        # Candidate now updated to sent
        cand = hr_db.get_candidate_by_id(cand_id)
        self.assertEqual(cand["candidate_status"], "Shortlisted - Email Sent")
        self.assertTrue(hr_db.has_successful_email_sent(cand_id))

    def test_rbac_unauthorized_user_blocked(self):
        """Verify RBAC dependency blocks non-HR/non-Admin roles (HTTP 403)."""
        # Viewer user should be forbidden
        with self.assertRaises(HTTPException) as ctx:
            require_hr_or_admin(current_user=self.viewer_user)
        self.assertEqual(ctx.exception.status_code, 403)

        # HR and Admin users should pass
        res_hr = require_hr_or_admin(current_user=self.hr_user)
        self.assertEqual(res_hr["username"], "hr_recruiter")

        res_admin = require_hr_or_admin(current_user=self.admin_user)
        self.assertEqual(res_admin["username"], "admin_user")

    def test_candidate_email_update_and_approval(self):
        """Verify candidate email update and subsequent approval delivery."""
        cand_id = "C_EMAIL_UPDATE_TEST"
        hr_db.save_candidate(cand_id, self.test_job_id, "No Email Candidate", "", "no_email.pdf")
        hr_db.update_candidate_shortlist_status(self.test_job_id, cand_id, "Shortlisted (Pending Approval)")

        # Verify candidate initially has empty email
        cand = hr_db.get_candidate_by_id(cand_id)
        self.assertEqual(cand["email"], "")

        # Update candidate email
        updated = hr_db.update_candidate_email(cand_id, "new.email@example.com")
        self.assertTrue(updated)
        cand_updated = hr_db.get_candidate_by_id(cand_id)
        self.assertEqual(cand_updated["email"], "new.email@example.com")

        # Approve candidate
        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_smtp

            bg_tasks = BackgroundTasks()
            res = approval_service.approve_candidate(
                candidate_id=cand_id,
                current_user=self.hr_user,
                background_tasks=bg_tasks,
                backoff_factor=0.0
            )
            self.assertEqual(res["status"], "success")

            for task in bg_tasks.tasks:
                task()

            cand_final = hr_db.get_candidate_by_id(cand_id)
            self.assertEqual(cand_final["candidate_status"], "Shortlisted - Email Sent")
            self.assertEqual(cand_final["email"], "new.email@example.com")


if __name__ == "__main__":
    unittest.main()

