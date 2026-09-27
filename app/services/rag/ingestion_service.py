import os
import json
import pickle
import datetime
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings
from app.loaders.loader_factory import get_document_loader
from app.utils.logger import logger

REGISTRY_PATH = os.path.join(settings.CHROMA_PATH, "index_registry.json")
BM25_CACHE_PATH = os.path.join(settings.CHROMA_PATH, "bm25_cache.pkl")

# Initialize HuggingFace embeddings
embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL)

def get_text_splitter():
    """Factory returning text splitter (SemanticChunker or RecursiveCharacterTextSplitter)."""
    strategy = settings.CHUNKING_STRATEGY.lower()

    if strategy == "semantic":
        breakpoint_type = os.getenv("SEMANTIC_BREAKPOINT_TYPE", "percentile")
        breakpoint_amount = float(os.getenv("SEMANTIC_BREAKPOINT_AMOUNT", "90.0"))
        logger.info(f"Chunking strategy: SemanticChunker ({breakpoint_type}={breakpoint_amount})")
        return SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type=breakpoint_type,
            breakpoint_threshold_amount=breakpoint_amount
        )
    else:
        logger.info(f"Chunking strategy: RecursiveCharacterTextSplitter ({settings.CHUNK_SIZE}, {settings.CHUNK_OVERLAP})")
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )

def load_index_registry() -> dict:
    """Loads index registry tracking indexed files."""
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load index registry: {e}. Starting fresh.")
    return {}

def save_index_registry(registry: dict):
    """Persists index registry to disk."""
    try:
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save index registry: {e}")

def save_bm25_cache(retriever):
    """Saves BM25 retriever to cache."""
    try:
        with open(BM25_CACHE_PATH, "wb") as f:
            pickle.dump(retriever, f)
        logger.info("BM25 cache saved to disk. ⚡")
    except Exception as e:
        logger.warning(f"Could not save BM25 cache: {e}")

def load_bm25_cache():
    """Loads BM25 retriever from cache."""
    try:
        if os.path.exists(BM25_CACHE_PATH):
            with open(BM25_CACHE_PATH, "rb") as f:
                retriever = pickle.load(f)
            logger.info("⚡ BM25 cache loaded from disk.")
            return retriever
    except Exception as e:
        logger.warning(f"Could not load BM25 cache: {e}. Will rebuild.")
    return None
