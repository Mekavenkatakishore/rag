"""
test_approval_workflow.py
──────────────────────────
Unit test suite for Phase 1 Human-in-the-Loop Shortlist Approval Workflow.
Tests:
  1. Candidate status flow: Screened -> Shortlisted (Pending Approval) -> Approved / Rejected / On Hold.
  2. Audit logging on approve, reject, and hold actions.
  3. Match details synthesis (criteria pass/fail matrix, bonus skills, AI summary, red flags).
  4. RBAC permission checks (HR / Admin allowed, non-HR blocked).
  5. Shortlisted candidates list filtering and sorting.
  6. Email template preview generation and Phase 1 stubbing.
"""

import unittest
import json
import sqlite3
from fastapi import HTTPException

from app.db import hr_db, user_db
from app.services.hr import approval_service, email_service
from app.api.deps import require_hr_or_admin


class TestApprovalWorkflow(unittest.TestCase):

    def setUp(self):
        """Initialize databases and test job/candidates before each test."""
        user_db.initialize_db()
        hr_db.initialize_hr_db()

        self.test_job_id = "test_job_approval_001"
        self.hr_user = {"id": 1, "username": "hr_manager", "role": "hr", "email": "hr@test.com"}
        self.admin_user = {"id": 2, "username": "admin_lead", "role": "admin", "email": "admin@test.com"}
        self.viewer_user = {"id": 3, "username": "guest_viewer", "role": "viewer", "email": "guest@test.com"}

        # Create test job
        hr_db.create_job(
            job_id=self.test_job_id,
            user_id=1,
            title="Senior Python Backend Engineer",
            jd_filename="senior_python_jd.pdf",
            jd_parsed={
                "title": "Senior Python Backend Engineer",
                "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
                "preferred_skills": ["Kubernetes", "Redis", "AWS"],
                "min_experience_years": 4,
                "education": "Bachelor's in Computer Science"
            }
        )

        # Create test candidates
        self.cand_1_id = "C_TEST_001"
        self.cand_2_id = "C_TEST_002"
        self.cand_3_id = "C_TEST_003"

        hr_db.save_candidate(self.cand_1_id, self.test_job_id, "Alice Sharma", "alice@example.com", "alice_resume.pdf")
        hr_db.save_candidate(self.cand_2_id, self.test_job_id, "Bob Kumar", "bob@example.com", "bob_resume.pdf")
        hr_db.save_candidate(self.cand_3_id, self.test_job_id, "Charlie Singh", "charlie@example.com", "charlie_resume.pdf")

        # Save score for Candidate 1 (Strong Match -> 88%)
        hr_db.save_candidate_score(
            candidate_id=self.cand_1_id,
            job_id=self.test_job_id,
            final_score=88.0,
            fit_category="Strong Fit",
            score_breakdown={
                "required_skills_score": 90.0,
                "experience_score": 85.0,
                "semantic_relevance_score": 88.0,
                "project_score": 80.0,
                "preferred_skills_score": 75.0,
                "education_score": 100.0,
                "domain_score": 85.0
            }
        )
        hr_db.update_candidate_shortlist_status(self.test_job_id, self.cand_1_id, "Shortlisted (Pending Approval)")

        # Save score for Candidate 2 (Moderate Match -> 68%)
        hr_db.save_candidate_score(
            candidate_id=self.cand_2_id,
            job_id=self.test_job_id,
            final_score=68.0,
            fit_category="Moderate Fit",
            score_breakdown={"required_skills_score": 70.0, "experience_score": 60.0}
        )
        hr_db.update_candidate_shortlist_status(self.test_job_id, self.cand_2_id, "Pending Approval")

        # Save score for Candidate 3 (Weak Match -> 42%)
        hr_db.save_candidate_score(
            candidate_id=self.cand_3_id,
            job_id=self.test_job_id,
            final_score=42.0,
            fit_category="Weak Fit",
            score_breakdown={"required_skills_score": 30.0, "experience_score": 40.0}
        )
        hr_db.update_candidate_shortlist_status(self.test_job_id, self.cand_3_id, "Screened")

    def test_candidate_status_transitions(self):
        """Verify candidate status flow: Shortlisted -> Approved, Rejected, or On Hold."""
        # 1. Approve Candidate 1
        res_approve = approval_service.approve_candidate(
            candidate_id=self.cand_1_id,
            current_user=self.hr_user,
            hr_notes="Demonstrates strong FastAPI background"
        )
        self.assertEqual(res_approve["status"], "success")
        self.assertEqual(res_approve["candidate_status"], "Approved")
        self.assertEqual(res_approve["approved_by"], "hr_manager")
        self.assertEqual(res_approve["email_status"], "stubbed")

        # Verify DB updated
        cand_db = hr_db.get_job_candidate(self.test_job_id, self.cand_1_id)
        self.assertEqual(cand_db["candidate_status"], "Approved")
        self.assertEqual(cand_db["approved_by"], "hr_manager")
        self.assertIsNotNone(cand_db["approved_at"])
        self.assertIn("FastAPI", cand_db["hr_notes"])

        # 2. Put Candidate 2 On Hold
        res_hold = approval_service.hold_candidate(
            candidate_id=self.cand_2_id,
            current_user=self.hr_user,
            hr_notes="Holding until second round resumes arrive"
        )
        self.assertEqual(res_hold["candidate_status"], "On Hold")
        cand_2_db = hr_db.get_job_candidate(self.test_job_id, self.cand_2_id)
        self.assertEqual(cand_2_db["candidate_status"], "On Hold")

        # 3. Reject Candidate 3
        res_reject = approval_service.reject_candidate(
            candidate_id=self.cand_3_id,
            current_user=self.hr_user,
            hr_notes="Skills and experience below role threshold",
            rejection_reason="Mandatory technical skills not met"
        )
        self.assertEqual(res_reject["candidate_status"], "Rejected")
        cand_3_db = hr_db.get_job_candidate(self.test_job_id, self.cand_3_id)
        self.assertEqual(cand_3_db["candidate_status"], "Rejected")
        self.assertEqual(cand_3_db["rejection_reason"], "Mandatory technical skills not met")

    def test_audit_logging_history(self):
        """Verify that every approval, rejection, and hold action generates an auditable log entry."""
        approval_service.approve_candidate(self.cand_1_id, self.hr_user, "Approved by HR Manager")
        approval_service.hold_candidate(self.cand_2_id, self.hr_user, "Hold note")
        approval_service.reject_candidate(self.cand_3_id, self.hr_user, "Reject note", "Low score")

        logs_cand_1 = hr_db.get_audit_logs(candidate_id=self.cand_1_id)
        self.assertTrue(len(logs_cand_1) >= 1)
        self.assertEqual(logs_cand_1[0]["action"], "APPROVED")
        self.assertEqual(logs_cand_1[0]["performed_by"], "hr_manager")
        self.assertIn("Approved by HR Manager", logs_cand_1[0]["hr_notes"])

        logs_all = hr_db.get_audit_logs(job_id=self.test_job_id)
        actions = [l["action"] for l in logs_all]
        self.assertIn("APPROVED", actions)
        self.assertIn("PUT_ON_HOLD", actions)
        self.assertIn("REJECTED", actions)

    def test_match_details_synthesis(self):
        """Verify match details generation: criteria pass/fail, bonus skills, AI summary, red flags."""
        details = approval_service.get_candidate_match_details(self.cand_1_id)
        self.assertEqual(details["status"], "success")
        self.assertEqual(details["candidate_id"], self.cand_1_id)
        self.assertEqual(details["name"], "Alice Sharma")
        self.assertEqual(details["overall_score"], 88.0)
        self.assertEqual(details["fit_category"], "Strong Fit")

        # Verify Criteria Results matrix
        criteria = details["criteria_results"]
        self.assertTrue(len(criteria) >= 2)
        score_rule = next((c for c in criteria if "Qualification Score" in c["rule"]), None)
        self.assertIsNotNone(score_rule)
        self.assertTrue(score_rule["passed"])

        # Verify Summary and Red Flags
        self.assertTrue(len(details["summary"]) > 20)
        self.assertIn("Alice Sharma", details["summary"])
        self.assertIsInstance(details["red_flags"], list)

    def test_rbac_permission_checks(self):
        """Verify that HR and Admin users pass authorization, while unauthorized roles are rejected with 403."""
        # HR user passes
        hr_check = require_hr_or_admin(self.hr_user)
        self.assertEqual(hr_check["username"], "hr_manager")

        # Admin user passes
        admin_check = require_hr_or_admin(self.admin_user)
        self.assertEqual(admin_check["username"], "admin_lead")

        # Viewer / non-HR user fails with 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            require_hr_or_admin(self.viewer_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_shortlisted_listing_and_filtering(self):
        """Verify GET /shortlisted filters by status and sorts properly."""
        # Filter Pending Approval
        pending_list = hr_db.get_shortlisted_for_approval(
            job_id=self.test_job_id,
            status_filter="Pending Approval",
            sort_by="score",
            sort_order="desc"
        )
        self.assertEqual(len(pending_list), 2)
        # Should be ordered descending by score (Alice 88.0 > Bob 68.0)
        self.assertEqual(pending_list[0]["candidate_id"], self.cand_1_id)
        self.assertEqual(pending_list[1]["candidate_id"], self.cand_2_id)

        # Filter All
        all_list = hr_db.get_shortlisted_for_approval(
            job_id=self.test_job_id,
            status_filter="all"
        )
        self.assertEqual(len(all_list), 3)

        # Filter Min Score >= 70
        high_score_list = hr_db.get_shortlisted_for_approval(
            job_id=self.test_job_id,
            status_filter="all",
            min_score=70.0
        )
        self.assertEqual(len(high_score_list), 1)
        self.assertEqual(high_score_list[0]["candidate_id"], self.cand_1_id)

    def test_email_template_preview_and_stubbing(self):
        """Verify shortlist email template rendering and Phase 1 stubbing."""
        cand_dict = {
            "candidate_id": self.cand_1_id,
            "name": "Alice Sharma",
            "email": "alice@example.com",
            "role": "Senior Python Backend Engineer"
        }
        preview = email_service.preview_shortlist_email(cand_dict, self.hr_user)
        self.assertEqual(preview["status"], "success")
        self.assertEqual(preview["to_email"], "alice@example.com")
        self.assertIn("Senior Python Backend Engineer", preview["subject"])
        self.assertIn("Alice Sharma", preview["plain_text_body"])
        self.assertIn("<html", preview["html_body"])

        # Test Phase 1 email stub
        stub_res = email_service.send_shortlist_email_stub(
            candidate_id=self.cand_1_id,
            to_email="alice@example.com",
            candidate_name="Alice Sharma",
            job_title="Senior Python Backend Engineer",
            approved_by="hr_manager"
        )
        self.assertFalse(stub_res["sent"])
        self.assertEqual(stub_res["status"], "stubbed")
        self.assertIn("Phase 1", stub_res["message"])


if __name__ == "__main__":
    unittest.main()

