import unittest
import os
import tempfile
from app.services.skill_normalizer import normalize_skill, normalize_skill_list
from app.services.scoring_engine import calculate_candidate_score
from app.db import hr_db

class TestHRMatchingSystem(unittest.TestCase):

    def test_skill_normalization(self):
        """Tests technology skill canonical mapping."""
        self.assertEqual(normalize_skill("Postgres"), "PostgreSQL")
        self.assertEqual(normalize_skill("ReactJS"), "React")
        self.assertEqual(normalize_skill("K8s"), "Kubernetes")
        self.assertEqual(normalize_skill("Amazon EC2"), "AWS")
        
        raw_list = ["Postgres", "K8s", "Docker", "ReactJS"]
        expected = ["PostgreSQL", "Kubernetes", "Docker", "React"]
        self.assertEqual(normalize_skill_list(raw_list), expected)

    def test_scoring_engine(self):
        """Tests deterministic math candidate match scoring."""
        jd = {
            "title": "Senior Python Developer",
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_skills": ["Docker", "Kubernetes"],
            "min_experience_years": 3,
            "education": ["Bachelor"]
        }

        candidate_perfect = {
            "candidate_name": "Jane Doe",
            "matched_required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "missing_required_skills": [],
            "matched_preferred_skills": ["Docker", "Kubernetes"],
            "missing_preferred_skills": [],
            "experience_years": 5.0,
            "education_fit": True,
            "project_relevance": "High"
        }

        res_perfect = calculate_candidate_score(candidate_perfect, jd)
        self.assertGreaterEqual(res_perfect["final_score"], 90.0)
        self.assertIn("Strong Fit", res_perfect["fit_category"])

    def test_hr_db_operations(self):
        """Tests SQLite HR database CRUD operations."""
        job_id = "test_job_123"
        hr_db.create_job(job_id=job_id, user_id=1, title="Test Backend Role")
        
        job = hr_db.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["title"], "Test Backend Role")
        
        hr_db.save_candidate("c_001", job_id, "Alice Smith", "alice@example.com", "resume_alice.pdf")
        cands = hr_db.get_job_candidates(job_id)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["name"], "Alice Smith")
        self.assertEqual(cands[0].get("candidate_status", "Pending"), "Pending")
        
        hr_db.clear_job_data(job_id)
        self.assertIsNone(hr_db.get_job(job_id))

    def test_candidate_shortlist_persistence_and_isolation(self):
        """Tests Phase 1 candidate shortlist persistence and JD isolation."""
        job_a = "job_A_101"
        job_b = "job_B_202"
        cand_id_a = "cand_alice_jobA"
        cand_id_b = "cand_alice_jobB"

        hr_db.create_job(job_id=job_a, user_id=1, title="Role A")
        hr_db.create_job(job_id=job_b, user_id=1, title="Role B")

        hr_db.save_candidate(cand_id_a, job_a, "Alice Smith", "alice@example.com", "alice_resume.pdf")
        hr_db.save_candidate(cand_id_b, job_b, "Alice Smith", "alice@example.com", "alice_resume.pdf")

        # Initial status must be Pending
        cands_a = hr_db.get_job_candidates(job_a)
        self.assertEqual(cands_a[0].get("candidate_status"), "Pending")

        # Shortlist under Job A only
        res = hr_db.update_candidate_shortlist_status(job_a, cand_id_a, "Shortlisted")
        self.assertIsNotNone(res)
        self.assertTrue(res["success"])
        self.assertEqual(res["candidate_status"], "Shortlisted")

        # Verify Job A candidate is Shortlisted
        shortlisted_a = hr_db.get_shortlisted_candidates(job_a)
        self.assertEqual(len(shortlisted_a), 1)
        self.assertEqual(shortlisted_a[0]["candidate_id"], cand_id_a)

        # Verify Job B candidate remains Pending (JD Isolation)
        cands_b = hr_db.get_job_candidates(job_b)
        self.assertEqual(cands_b[0].get("candidate_status"), "Pending")
        self.assertEqual(len(hr_db.get_shortlisted_candidates(job_b)), 0)

        # Remove from shortlist under Job A
        res_remove = hr_db.update_candidate_shortlist_status(job_a, cand_id_a, "Pending")
        self.assertEqual(res_remove["candidate_status"], "Pending")
        self.assertEqual(len(hr_db.get_shortlisted_candidates(job_a)), 0)

        # Test invalid status raises ValueError
        with self.assertRaises(ValueError):
            hr_db.update_candidate_shortlist_status(job_a, cand_id_a, "InvalidStatus")

        hr_db.clear_job_data(job_a)
        hr_db.clear_job_data(job_b)

if __name__ == "__main__":
    unittest.main()
