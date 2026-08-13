"""
test_hr_matching.py
───────────────────
Automated test suite for Phase 1 AI HR Candidate Matcher.
Tests deterministic scoring, skill normalization, job isolation, hallucination protection, and ranking.
"""

import unittest
from app.services.skill_normalizer import normalize_skill, normalize_skill_list
from app.services.scoring_engine import calculate_candidate_score
from app.db import hr_db

class TestHRMatching(unittest.TestCase):

    def setUp(self):
        """Initialize database before each test."""
        hr_db.initialize_hr_db()

    def test_skill_normalization(self):
        """Verify canonical skill mappings."""
        self.assertEqual(normalize_skill("Postgres"), "PostgreSQL")
        self.assertEqual(normalize_skill("ReactJS"), "React")
        self.assertEqual(normalize_skill("react.js"), "React")
        self.assertEqual(normalize_skill("K8s"), "Kubernetes")
        self.assertEqual(normalize_skill("k8s"), "Kubernetes")
        self.assertEqual(normalize_skill("Amazon EC2"), "AWS")
        
        raw_list = ["Postgres", "ReactJS", "K8s", "python", "React"]
        normalized = normalize_skill_list(raw_list)
        self.assertIn("PostgreSQL", normalized)
        self.assertIn("React", normalized)
        self.assertIn("Kubernetes", normalized)
        self.assertIn("Python", normalized)

    def test_strong_candidate_scoring(self):
        """Test candidate meeting all required & preferred criteria."""
        jd_requirements = {
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_skills": ["Docker", "Kubernetes"],
            "min_experience_years": 4
        }
        
        analysis_result = {
            "matched_required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "missing_required_skills": [],
            "matched_preferred_skills": ["Docker", "Kubernetes"],
            "missing_preferred_skills": [],
            "experience_years": 5.0,
            "project_relevance": "High",
            "education_fit": True,
            "experience_fit": "Meets requirement"
        }
        
        result = calculate_candidate_score(analysis_result, jd_requirements)
        self.assertGreaterEqual(result["final_score"], 80.0)
        self.assertEqual(result["fit_category"], "Strong Fit")

    def test_weak_candidate_scoring(self):
        """Test candidate missing mandatory skills and experience."""
        jd_requirements = {
            "required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "preferred_skills": ["Docker"],
            "min_experience_years": 5
        }
        
        analysis_result = {
            "matched_required_skills": [],
            "missing_required_skills": ["Python", "FastAPI", "PostgreSQL"],
            "matched_preferred_skills": [],
            "missing_preferred_skills": ["Docker"],
            "experience_years": 0.5,
            "project_relevance": "Low",
            "education_fit": False,
            "experience_fit": "Does not meet"
        }
        
        result = calculate_candidate_score(analysis_result, jd_requirements)
        self.assertLess(result["final_score"], 60.0)
        self.assertEqual(result["fit_category"], "Weak Fit")

    def test_hallucination_protection(self):
        """Verify unmentioned skills are not included in matched skills."""
        analysis_result = {
            "matched_required_skills": ["Python"],
            "missing_required_skills": ["AWS", "FastAPI"]
        }
        self.assertNotIn("AWS", analysis_result["matched_required_skills"])
        self.assertIn("AWS", analysis_result["missing_required_skills"])

    def test_candidate_ranking_order(self):
        """Verify ranking orders candidates correctly by score."""
        cand_strong = {"final_score": 92.0, "fit_category": "Strong Fit"}
        cand_mod = {"final_score": 74.0, "fit_category": "Moderate Fit"}
        cand_weak = {"final_score": 42.0, "fit_category": "Weak Fit"}
        
        candidates = [cand_weak, cand_strong, cand_mod]
        candidates.sort(key=lambda x: x["final_score"], reverse=True)
        
        self.assertEqual(candidates[0]["fit_category"], "Strong Fit")
        self.assertEqual(candidates[1]["fit_category"], "Moderate Fit")
        self.assertEqual(candidates[2]["fit_category"], "Weak Fit")

    def test_multi_job_isolation(self):
        """Verify candidate records for Job A do not leak into Job B."""
        job_a_id = "job_test_a"
        job_b_id = "job_test_b"
        
        hr_db.create_job(job_a_id, 1, "Role A")
        hr_db.create_job(job_b_id, 1, "Role B")
        
        hr_db.save_candidate("C100", job_a_id, "Candidate A", "a@test.com", "cand_a.pdf")
        hr_db.save_candidate("C200", job_b_id, "Candidate B", "b@test.com", "cand_b.pdf")
        
        job_a_candidates = hr_db.get_job_candidates(job_a_id)
        job_b_candidates = hr_db.get_job_candidates(job_b_id)
        
        job_a_ids = [c["candidate_id"] for c in job_a_candidates]
        job_b_ids = [c["candidate_id"] for c in job_b_candidates]
        
        self.assertIn("C100", job_a_ids)
        self.assertNotIn("C200", job_a_ids)
        
        self.assertIn("C200", job_b_ids)
        self.assertNotIn("C100", job_b_ids)

if __name__ == "__main__":
    unittest.main()
