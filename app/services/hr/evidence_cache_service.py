"""
evidence_cache_service.py
─────────────────────────
Optimized evidence retrieval with model caching and result caching.
FlashRank model loaded ONCE and reused (5x faster).
"""

import hashlib
from functools import lru_cache
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from flashrank import Ranker

from app.services.rag import vectorstore
from app.utils.logger import logger


class CachedFlashRankReranker:
    """Singleton FlashRank model with result caching."""

    _instance = None
    _ranker = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._ranker is None:
            logger.info("Initializing FlashRank model (loaded once, reused)...")
            try:
                self._ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir="/tmp/flashrank_cache")
                logger.info("✓ FlashRank model cached and ready")
            except Exception as e:
                logger.warning(f"FlashRank initialization failed: {e}")
                self._ranker = None

    def rerank(self, query: str, passages: List[Dict[str, Any]], top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Rerank passages using cached FlashRank model.
        Returns top_k passages sorted by relevance score.
        """
        if not self._ranker or not passages:
            return passages[:top_k]

        try:
            rerank_request = {"query": query, "passages": passages}
            results = self._ranker.rank(rerank_request)
            return results[:top_k] if results else passages[:top_k]
        except Exception as e:
            logger.warning(f"FlashRank reranking failed, returning top passages: {e}")
            return passages[:top_k]


class EvidenceCacheLayer:
    """Result caching for evidence queries (avoid duplicate searches)."""

    def __init__(self, max_cache_size: int = 128):
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, List[Document]] = {}
        self.reranker = CachedFlashRankReranker()

    def _cache_key(self, query: str, candidate_id: str, top_k: int) -> str:
        """Generate unique cache key for query."""
        key_str = f"{query}:{candidate_id}:{top_k}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def retrieve_with_cache(
        self,
        query: str,
        candidate_id: str,
        top_k: int = 15,
        use_rerank: bool = True
    ) -> List[Document]:
        """
        Retrieve evidence with caching.
        Returns cached results if available, otherwise fetches and caches.
        """
        cache_key = self._cache_key(query, candidate_id, top_k)

        # Check cache
        if cache_key in self._cache:
            logger.debug(f"Cache hit: {cache_key}")
            return self._cache[cache_key]

        # Cache miss - fetch from vectorstore
        try:
            retrieved_docs = vectorstore.similarity_search(
                query=query,
                k=top_k,
                filter={"candidate_id": candidate_id}
            )

            if not retrieved_docs:
                self._cache[cache_key] = []
                return []

            # Rerank if enabled
            if use_rerank:
                passages = [
                    {"id": idx, "text": doc.page_content, "meta": doc.metadata}
                    for idx, doc in enumerate(retrieved_docs)
                ]
                rerank_results = self.reranker.rerank(query, passages, top_k=6)
                top_docs = [
                    Document(page_content=r["text"], metadata=r.get("meta", {}))
                    for r in rerank_results
                ]
            else:
                top_docs = retrieved_docs[:6]

            # Cache result
            if len(self._cache) >= self.max_cache_size:
                # Simple LRU: remove first item
                self._cache.pop(next(iter(self._cache)))

            self._cache[cache_key] = top_docs
            logger.debug(f"Cached {len(top_docs)} docs for {cache_key}")

            return top_docs

        except Exception as e:
            logger.error(f"Error retrieving evidence for {candidate_id}: {e}")
            return []

    def clear_cache(self):
        """Clear all cached results."""
        self._cache.clear()
        logger.info("Evidence cache cleared")


# Global cache instance
_evidence_cache = EvidenceCacheLayer()


def retrieve_candidate_evidence_cached(
    job_id: str,
    candidate_id: str,
    jd_requirements: Dict[str, Any],
    use_cache: bool = True
) -> List[Document]:
    """
    Retrieve evidence for candidate with caching and reranking.
    Signature-compatible with original for easy drop-in replacement.
    """
    skills_query = " ".join(
        jd_requirements.get("required_skills", []) +
        jd_requirements.get("preferred_skills", [])
    )
    query_text = f"{jd_requirements.get('title', '')} {skills_query}".strip()

    if use_cache:
        return _evidence_cache.retrieve_with_cache(
            query=query_text,
            candidate_id=candidate_id,
            top_k=15,
            use_rerank=True
        )
    else:
        # Direct retrieval without cache
        try:
            retrieved_docs = vectorstore.similarity_search(
                query=query_text,
                k=15,
                filter={"candidate_id": candidate_id}
            )
            if not retrieved_docs:
                return []

            passages = [
                {"id": idx, "text": doc.page_content, "meta": doc.metadata}
                for idx, doc in enumerate(retrieved_docs)
            ]
            rerank_results = _evidence_cache.reranker.rerank(query_text, passages, top_k=6)
            return [
                Document(page_content=r["text"], metadata=r.get("meta", {}))
                for r in rerank_results
            ]
        except Exception as e:
            logger.error(f"Error retrieving evidence: {e}")
            return []


def clear_evidence_cache():
    """Clear cached evidence results."""
    _evidence_cache.clear_cache()
