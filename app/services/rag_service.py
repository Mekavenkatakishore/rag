"""
rag_service.py (Facade Wrapper for Backward Compatibility)
────────────────────────────────────────────────────────
Forwards calls to app.services.rag package.
"""

from app.services.rag.rag_service import (
    UPLOAD_DIR,
    CHROMA_DIR,
    vectorstore,
    all_documents,
    rebuild_retrievers,
    get_rag_status,
    query_rag_service,
    stream_query_rag_service,
    delete_file_chunks,
    load_index_registry,
    save_index_registry,
    get_text_splitter,
    llm,
)

__all__ = [
    "UPLOAD_DIR",
    "CHROMA_DIR",
    "vectorstore",
    "all_documents",
    "rebuild_retrievers",
    "get_rag_status",
    "query_rag_service",
    "stream_query_rag_service",
    "delete_file_chunks",
    "load_index_registry",
    "save_index_registry",
    "get_text_splitter",
    "llm",
]
