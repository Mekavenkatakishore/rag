import os
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

from app.core.config import settings
from app.services.rag.ingestion_service import embeddings, load_bm25_cache, save_bm25_cache
from app.utils.logger import logger

os.makedirs(settings.CHROMA_PATH, exist_ok=True)

# Shared Chroma vectorstore instance
vectorstore = Chroma(
    persist_directory=settings.CHROMA_PATH,
    embedding_function=embeddings
)

def create_hybrid_retriever(all_documents: list, files_changed: bool = True):
    """Creates/rebuilds Hybrid EnsembleRetriever (BM25 + Chroma)."""
    retriever_top_k = settings.RETRIEVER_TOP_K
    hybrid_semantic_weight = settings.HYBRID_SEMANTIC_WEIGHT
    hybrid_keyword_weight = settings.HYBRID_KEYWORD_WEIGHT

    bm25_retriever = None

    if not files_changed:
        cached_bm25 = load_bm25_cache()
        if cached_bm25 is not None:
            bm25_retriever = cached_bm25
            bm25_retriever.k = retriever_top_k

    if bm25_retriever is None and all_documents:
        bm25_retriever = BM25Retriever.from_documents(all_documents)
        bm25_retriever.k = retriever_top_k
        save_bm25_cache(bm25_retriever)

    if bm25_retriever is None:
        logger.warning("BM25 retriever could not be initialized.")
        return None, None

    semantic_retriever = vectorstore.as_retriever(search_kwargs={"k": retriever_top_k})

    ensemble_retriever = EnsembleRetriever(
        retrievers=[semantic_retriever, bm25_retriever],
        weights=[hybrid_semantic_weight, hybrid_keyword_weight]
    )

    return bm25_retriever, ensemble_retriever
