from flashrank import Ranker
from langchain_community.document_compressors import FlashrankRerank
from langchain_classic.retrievers import ContextualCompressionRetriever

from app.core.config import settings
from app.utils.logger import logger

def build_compression_retriever(base_retriever):
    """Integrates FlashRank Reranker over base hybrid retriever."""
    if base_retriever is None:
        return None
    try:
        reranker_top_n = settings.RERANKER_TOP_N
        logger.info(f"Integrating FlashRank Reranker (top_n={reranker_top_n})...")
        compressor = FlashrankRerank(top_n=reranker_top_n)
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=base_retriever
        )
        logger.info("FlashRank Reranker successfully integrated.")
        return compression_retriever
    except Exception as e:
        logger.error(f"Failed to initialize FlashRank Reranker: {e}. Falling back.")
        return base_retriever
