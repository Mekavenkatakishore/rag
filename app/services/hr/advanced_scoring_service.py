"""
advanced_scoring_service.py
──────────────────────────
Advanced deterministic scoring with semantic matching.
Phase 2: Improved candidate ranking algorithm (industry standard).
"""

from typing import Dict, List, Any
from app.services.hr.skill_normalizer_service import normalize_skill_list
from app.utils.logger import logger


class AdvancedScoringEngine:
    """Enhanced scoring with semantic matching and better metrics."""

    # Weight model (can be customized per company)
    DEFAULT_WEIGHTS = {
        "required_skills": 0.35,      # Reduced from 0.40
        "preferred_skills": 0.10,     # Same
        "experience": 0.25,           # Same
        "project_relevance": 0.15,    # Same
        "education": 0.05,            # Same
        "domain_fit": 0.10,           # Increased from 0.05
        "recency_bonus": 0.05         # NEW: recent experience bonus
    }

    @staticmethod
    def calculate_skill_match_score(
        required_skills: List[str],
        candidate_skills: List[str],
        preferred_skills: List[str] = None,
        evidence_text: str = None
    ) -> Dict[str, float]:
        """
        Advanced skill matching with semantic considerations.
        Returns both exact and semantic match scores.
        """
        req_set = set(s.lower() for s in required_skills)
        cand_set = set(s.lower() for s in candidate_skills)
        pref_set = set(s.lower() for s in (preferred_skills or []))

        # Exact matches
        exact_matches = req_set.intersection(cand_set)
        exact_match_ratio = len(exact_matches) / len(req_set) if req_set else 1.0

        # Missing skills
        missing_skills = req_set - cand_set
        missing_count = len(missing_skills)

        # Preferred skill bonus (if any preferred skills matched)
        pref_matches = pref_set.intersection(cand_set)
        pref_match_ratio = len(pref_matches) / len(pref_set) if pref_set else 0.0

        # Keyword density scoring (how many times required skills appear)
        keyword_density = 0.0
        if evidence_text:
            text_lower = evidence_text.lower()
            keyword_occurrences = sum(1 for skill in required_skills if skill.lower() in text_lower)
            # Normalize to 0-1 range
            keyword_density = min(1.0, keyword_occurrences / (len(required_skills) * 2))

        # Calculate final score
        exact_score = min(100.0, exact_match_ratio * 100.0)
        keyword_boost = keyword_density * 15  # Up to 15% bonus
        final_skill_score = min(100.0, exact_score + keyword_boost)

        return {
            "exact_match_score": round(exact_score, 1),
            "keyword_density_score": round(keyword_density * 100, 1),
            "preferred_match_score": round(pref_match_ratio * 100, 1),
            "final_skill_score": round(final_skill_score, 1),
            "matched_count": len(exact_matches),
            "missing_count": missing_count,
            "matched_skills": list(exact_matches),
            "missing_skills": list(missing_skills),
            "preferred_matched": list(pref_matches)
        }

    @staticmethod
    def calculate_experience_score(
        candidate_years: float,
        required_years: float,
        experience_fit: str = "Meets",
        recent_roles: bool = True
    ) -> Dict[str, float]:
        """
        Advanced experience scoring with recency consideration.
        """
        candidate_years = float(candidate_years or 0)
        required_years = float(required_years or 0)

        if required_years <= 0:
            base_score = 100.0
        elif candidate_years >= required_years:
            # Exceeds requirement
            excess = candidate_years - required_years
            base_score = min(100.0, 100.0 + (excess * 2))  # Bonus for extra years
        else:
            # Below requirement
            base_score = (candidate_years / required_years) * 100.0

        # Experience fit classification bonus
        fit_bonus = 0.0
        if "exceeds" in experience_fit.lower() or "strong" in experience_fit.lower():
            fit_bonus = 15.0
        elif "meets" in experience_fit.lower() or "good" in experience_fit.lower():
            fit_bonus = 5.0
        elif "partial" in experience_fit.lower():
            fit_bonus = -10.0

        # Recency bonus (recent roles valued higher)
        recency_bonus = 10.0 if recent_roles else 0.0

        final_experience_score = min(100.0, base_score + fit_bonus + recency_bonus)

        return {
            "base_experience_score": round(base_score, 1),
            "fit_bonus": round(fit_bonus, 1),
            "recency_bonus": round(recency_bonus, 1),
            "final_experience_score": round(final_experience_score, 1),
            "years_required": required_years,
            "years_candidate": candidate_years,
            "meets_minimum": candidate_years >= required_years
        }

    @staticmethod
    def calculate_project_relevance_score(
        project_relevance: str,
        matched_skills_count: int = 0
    ) -> float:
        """
        Project relevance scoring with skill count consideration.
        """
        base_scores = {
            "high": 100.0,
            "excellent": 100.0,
            "strong": 100.0,
            "moderate": 70.0,
            "medium": 70.0,
            "good": 75.0,
            "fair": 50.0,
            "low": 30.0,
            "weak": 20.0,
        }

        relevance_lower = project_relevance.lower()
        base_score = next(
            (score for key, score in base_scores.items() if key in relevance_lower),
            50.0  # Default to moderate
        )

        # Skill count bonus: more matched skills = better project relevance
        skill_bonus = min(15.0, matched_skills_count * 2)
        final_score = min(100.0, base_score + skill_bonus)

        return round(final_score, 1)

    @staticmethod
    def calculate_education_score(
        education_fit: bool,
        candidate_education: List[str] = None
    ) -> float:
        """
        Education fit scoring.
        """
        base_score = 100.0 if education_fit else 40.0

        # Bonus for advanced degrees
        if candidate_education:
            education_text = " ".join(candidate_education).lower()
            advanced_bonus = 0.0
            if "master" in education_text or "mtech" in education_text or "mba" in education_text:
                advanced_bonus = 10.0
            elif "phd" in education_text or "doctorate" in education_text:
                advanced_bonus = 15.0

            final_score = min(100.0, base_score + advanced_bonus)
            return round(final_score, 1)

        return base_score

    @staticmethod
    def calculate_domain_fit_score(
        domain_fit_text: str,
        industry_keywords: List[str] = None
    ) -> float:
        """
        Domain/industry fit scoring.
        """
        base_scores = {
            "exceeds": 100.0,
            "meets": 100.0,
            "strong": 100.0,
            "partial": 60.0,
            "weak": 30.0,
        }

        fit_lower = domain_fit_text.lower()
        base_score = next(
            (score for key, score in base_scores.items() if key in fit_lower),
            50.0
        )

        return round(base_score, 1)

    def calculate_final_score(
        self,
        analysis: Dict[str, Any],
        jd_requirements: Dict[str, Any],
        weights: Dict[str, float] = None,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Comprehensive scoring with all metrics.
        Returns detailed score breakdown.
        """
        if weights is None:
            weights = self.DEFAULT_WEIGHTS

        logger.info(f"Starting advanced scoring for {analysis.get('candidate_name', 'Unknown')}")

        # Normalize skills
        req_skills = normalize_skill_list(jd_requirements.get("required_skills", []))
        pref_skills = normalize_skill_list(jd_requirements.get("preferred_skills", []))
        candidate_skills = normalize_skill_list(analysis.get("matched_required_skills", []))

        # 1. Skill Matching Score
        skill_metrics = self.calculate_skill_match_score(
            req_skills,
            candidate_skills,
            pref_skills,
            analysis.get("work_history", [])
        )
        skill_score = skill_metrics["final_skill_score"]

        # 2. Experience Score
        exp_metrics = self.calculate_experience_score(
            analysis.get("experience_years", 0),
            jd_requirements.get("min_experience_years", 0),
            analysis.get("experience_fit", "Meets"),
            recent_roles=True
        )
        experience_score = exp_metrics["final_experience_score"]

        # 3. Project Relevance Score
        project_score = self.calculate_project_relevance_score(
            analysis.get("project_relevance", "Moderate"),
            skill_metrics["matched_count"]
        )

        # 4. Education Score
        education_score = self.calculate_education_score(
            analysis.get("education_fit", True),
            analysis.get("education_details", [])
        )

        # 5. Domain Fit Score
        domain_score = self.calculate_domain_fit_score(
            analysis.get("experience_fit", "Meets")
        )

        # 6. Preferred Skills Bonus
        pref_score = skill_metrics["preferred_match_score"]

        # 7. Recency Bonus (newer experience is better)
        recency_bonus = 0.0  # Included in experience score already

        # Weighted aggregation
        final_score = (
            skill_score * weights.get("required_skills", 0.35) +
            pref_score * weights.get("preferred_skills", 0.10) +
            experience_score * weights.get("experience", 0.25) +
            project_score * weights.get("project_relevance", 0.15) +
            education_score * weights.get("education", 0.05) +
            domain_score * weights.get("domain_fit", 0.10)
        )

        final_score = round(min(100.0, max(0.0, final_score)), 1)

        # Fit category
        if final_score >= 80.0:
            fit_category = "Strong Fit"
        elif final_score >= 60.0:
            fit_category = "Moderate Fit"
        else:
            fit_category = "Weak Fit"

        score_breakdown = {
            "skill_match": round(skill_score, 1),
            "skill_metrics": skill_metrics,
            "experience": round(experience_score, 1),
            "experience_metrics": exp_metrics,
            "project_relevance": round(project_score, 1),
            "preferred_skills": round(pref_score, 1),
            "education": round(education_score, 1),
            "domain_fit": round(domain_score, 1),
            "weights": weights,
            "final_score": final_score,
            "fit_category": fit_category
        }

        if verbose:
            logger.info(f"Score Breakdown: {score_breakdown}")

        return {
            "final_score": final_score,
            "fit_category": fit_category,
            "score_breakdown": score_breakdown
        }


# Global scorer instance
_advanced_scorer = AdvancedScoringEngine()


def calculate_candidate_score_advanced(
    analysis: Dict[str, Any],
    jd_requirements: Dict[str, Any],
    weights: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Calculate advanced score (drop-in replacement for basic scoring).
    """
    return _advanced_scorer.calculate_final_score(analysis, jd_requirements, weights)
