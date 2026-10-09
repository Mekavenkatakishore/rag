"""
semantic_matching_service.py
─────────────────────────────
Embedding-based matching layer that supplements the deterministic, exact-string
scoring in scoring_engine.py.

Why this exists:
    The original scoring only counted a JD skill as "matched" if it appeared,
    after static-dictionary normalization, in the LLM's extracted
    matched_required_skills / matched_preferred_skills lists. That misses real
    matches whenever the candidate's resume or the LLM's own phrasing uses a
    synonym/variant that isn't in the ~90-entry skill_normalizer.py map (e.g.
    "Postgres" vs "PostgreSQL", "K8s" vs "Kubernetes", "scikit-learn" vs
    "sklearn"), and it has no notion of how relevant the document is to the JD
    as a whole — which is what let a completely unrelated PDF still rack up a
    high score on the other components.

This module reuses the SAME embedding model singleton already loaded for RAG
ingestion (sentence-transformers/all-MiniLM-L6-v2) — no extra model load, no
extra dependency, and the LLM-extraction step stays untouched (still auditable
text, no new hallucination surface). Embedding inference is deterministic for
a given model + text, so matches here remain explainable and reproducible.
"""

import numpy as np

from app.utils.logger import logger

# Cosine similarity threshold above which two skill phrases are considered the
# same skill. Calibrated empirically against this MiniLM model (not guessed):
# genuinely different-but-related technologies (React vs Angular, MySQL vs
# PostgreSQL, Docker vs Kubernetes, AWS vs GCP) consistently scored 0.20-0.33,
# while true synonyms/paraphrases (PostgreSQL vs Postgres: 0.90, Kubernetes vs
# "K8s Container Orchestration": 0.56, Apache Kafka vs "Kafka Event Streaming":
# 0.66, Machine Learning vs "Building ML Models": 0.53, Snowflake vs "Snowflake
# Cloud Data Warehouse": 0.45) all scored 0.45 or higher. 0.40 sits in the gap
# between those two clusters with a safety margin on both sides.
SKILL_MATCH_THRESHOLD = 0.40

# Whole-document JD-vs-resume cosine similarity is rescaled onto a 0-100 scale
# using this floor/ceiling, calibrated against MiniLM's typical range for
# short professional text: unrelated documents usually land around 0.1-0.3,
# genuinely relevant resumes against a JD typically land around 0.55-0.85.
RELEVANCE_FLOOR = 0.15
RELEVANCE_CEILING = 0.80

_embeddings_model = None
_embeddings_unavailable = False


def _get_embeddings_model():
    """Lazily fetches the shared HuggingFaceEmbeddings singleton used by RAG ingestion.

    Imported lazily (not at module load time) to avoid a hard import-order
    dependency on app.services.rag.ingestion_service, and guarded so that if
    the embedding model ever fails to load, candidate scoring degrades to
    exact-match-only instead of crashing.
    """
    global _embeddings_model, _embeddings_unavailable
    if _embeddings_model is not None or _embeddings_unavailable:
        return _embeddings_model
    try:
        from app.services.rag.ingestion_service import embeddings as shared_embeddings
        _embeddings_model = shared_embeddings
    except Exception as e:
        logger.warning(f"Semantic matching disabled — could not load embedding model: {e}")
        _embeddings_unavailable = True
        _embeddings_model = None
    return _embeddings_model


def _cosine_similarity(vec_a, vec_b) -> float:
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def semantic_skill_matches(jd_skills: list[str], candidate_skill_pool: list[str]) -> set[str]:
    """Returns the subset of jd_skills that have a semantically-equivalent entry
    in candidate_skill_pool, via embedding cosine similarity.

    Used to recover matches that exact-string comparison misses (synonyms,
    abbreviations, different phrasing between the JD and the LLM's extraction).
    Returns an empty set (never raises) if the embedding model is unavailable.
    """
    if not jd_skills or not candidate_skill_pool:
        return set()

    model = _get_embeddings_model()
    if model is None:
        return set()

    try:
        jd_vectors = model.embed_documents(jd_skills)
        pool_vectors = model.embed_documents(candidate_skill_pool)
    except Exception as e:
        logger.warning(f"Semantic skill matching failed, falling back to exact match only: {e}")
        return set()

    matched = set()
    for skill, skill_vec in zip(jd_skills, jd_vectors):
        best = max((_cosine_similarity(skill_vec, pv) for pv in pool_vectors), default=0.0)
        if best >= SKILL_MATCH_THRESHOLD:
            matched.add(skill)
    return matched


def build_jd_text(jd_requirements: dict) -> str:
    """Builds a representative text blob from the structured, parsed JD fields
    for whole-document semantic comparison against resume text."""
    parts = []
    if jd_requirements.get("title"):
        parts.append(str(jd_requirements["title"]))
    if jd_requirements.get("summary"):
        parts.append(str(jd_requirements["summary"]))
    for key in ("required_skills", "preferred_skills", "responsibilities", "domain", "education"):
        values = jd_requirements.get(key) or []
        if values:
            parts.append(", ".join(str(v) for v in values))
    return ". ".join(p for p in parts if p).strip()


def semantic_relevance_score(jd_text: str, resume_text: str) -> float | None:
    """Scores how relevant a resume is to a JD overall (0-100), independent of
    any individual skill match — this is what catches a document that simply
    isn't a relevant resume at all, even if a few keywords happen to overlap.

    Returns None (excluded from scoring, not defaulted to a neutral value) if
    either text is empty or the embedding model is unavailable.
    """
    if not jd_text or not resume_text:
        return None

    model = _get_embeddings_model()
    if model is None:
        return None

    try:
        jd_vec = model.embed_query(jd_text[:2000])
        resume_vec = model.embed_query(resume_text[:2000])
    except Exception as e:
        logger.warning(f"Semantic relevance scoring failed: {e}")
        return None

    similarity = _cosine_similarity(jd_vec, resume_vec)
    scaled = (similarity - RELEVANCE_FLOOR) / (RELEVANCE_CEILING - RELEVANCE_FLOOR) * 100.0
    return round(max(0.0, min(100.0, scaled)), 1)
