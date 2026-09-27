import os
import json
import datetime
from langchain_core.documents import Document

from app.core.config import settings
from app.loaders.loader_factory import get_document_loader
from app.utils.logger import logger
from app.core.llm_factory import get_llm

from app.services.rag.ingestion_service import (
    get_text_splitter,
    load_index_registry,
    save_index_registry,
)
from app.services.rag.retrieval_service import (
    vectorstore,
    create_hybrid_retriever,
)
from app.services.rag.reranking_service import build_compression_retriever
from app.services.rag.generation_service import condense_chain, rag_chain

UPLOAD_DIR = settings.UPLOAD_DIR
CHROMA_DIR = settings.CHROMA_PATH

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)

llm = get_llm(temperature=0.3)

bm25_retriever = None
ensemble_retriever = None
compression_retriever = None
all_documents = []

def delete_file_chunks(file_name: str):
    """Removes stored chunks for a file from vectorstore."""
    try:
        vectorstore._collection.delete(where={"filename": file_name})
        logger.info(f"Removed old chunks for '{file_name}' from vectorstore.")
    except Exception as e:
        logger.warning(f"Could not remove chunks for '{file_name}': {e}")

def rebuild_retrievers():
    """Incremental indexing orchestration."""
    global bm25_retriever, ensemble_retriever, compression_retriever, all_documents

    all_documents = []

    if not os.path.exists(UPLOAD_DIR):
        bm25_retriever = None
        ensemble_retriever = None
        compression_retriever = None
        return

    files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    index_registry = load_index_registry()

    new_or_modified = []
    for file_name in files:
        file_path = os.path.join(UPLOAD_DIR, file_name)
        current_mtime = os.path.getmtime(file_path)
        if file_name not in index_registry or index_registry[file_name]["mtime"] != current_mtime:
            new_or_modified.append(file_name)

    deleted_files = [f for f in index_registry if f not in files]

    for file_name in deleted_files:
        logger.info(f"File deleted: '{file_name}'. Removing chunks...")
        delete_file_chunks(file_name)
        del index_registry[file_name]

    if new_or_modified:
        loaded_docs = []
        for file_name in new_or_modified:
            file_path = os.path.join(UPLOAD_DIR, file_name)
            _, ext = os.path.splitext(file_name.lower())
            if file_name in index_registry:
                delete_file_chunks(file_name)

            try:
                loader = get_document_loader(file_path)
                docs = loader.load()
                upload_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                for doc in docs:
                    doc.metadata["filename"] = file_name
                    doc.metadata["extension"] = ext
                    doc.metadata["upload_timestamp"] = upload_time
                    if "source" not in doc.metadata:
                        doc.metadata["source"] = file_path

                loaded_docs.extend(docs)
                index_registry[file_name] = {
                    "mtime": os.path.getmtime(file_path),
                    "indexed_at": datetime.datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error(f"Extraction failure for file {file_name}: {e}")
                continue

        if loaded_docs:
            splitter = get_text_splitter()
            new_chunks = splitter.split_documents(loaded_docs)
            vectorstore.add_documents(new_chunks)

    save_index_registry(index_registry)

    try:
        chroma_data = vectorstore.get(include=["documents", "metadatas"])
        if chroma_data and chroma_data.get("documents"):
            all_documents = [
                Document(page_content=content, metadata=meta or {})
                for content, meta in zip(chroma_data["documents"], chroma_data["metadatas"])
            ]
    except Exception as e:
        logger.error(f"Failed to load documents from Chroma: {e}")

    files_changed = bool(new_or_modified or deleted_files)
    bm25_retriever, ensemble_retriever = create_hybrid_retriever(all_documents, files_changed=files_changed)
    compression_retriever = build_compression_retriever(ensemble_retriever)

def get_rag_status():
    """Returns indexing status."""
    files = []
    if os.path.exists(UPLOAD_DIR):
        files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    return {
        "uploaded_files": files,
        "total_chunks": len(all_documents),
        "indexing_active": ensemble_retriever is not None,
        "chunking_strategy": settings.CHUNKING_STRATEGY
    }

def query_rag_service(prompt: str, chat_history: list = None):
    """Executes a full RAG query."""
    global compression_retriever, ensemble_retriever
    active_retriever = compression_retriever if compression_retriever is not None else ensemble_retriever
    if active_retriever is None:
        raise ValueError("No documents have been indexed yet. Please upload files first.")

    formatted_history = ""
    if chat_history:
        for msg in chat_history:
            role_label = "Human" if msg.role == "user" else "Assistant"
            formatted_history += f"{role_label}: {msg.content}\n"

    rewritten_prompt = prompt
    if chat_history:
        try:
            rewritten_prompt = condense_chain.invoke({
                "chat_history": formatted_history,
                "question": prompt
            }).strip()
        except Exception as e:
            logger.error(f"Failed to condense query: {e}. Using raw prompt.")

    try:
        relevant_docs = active_retriever.invoke(rewritten_prompt)
    except Exception as e:
        raise RuntimeError(f"Error retrieving context from database: {e}")

    context_chunks = []
    citations = []
    for doc in relevant_docs:
        filename = doc.metadata.get("filename") or os.path.basename(doc.metadata.get("source", "Unknown Source"))
        page_num = doc.metadata.get("page", None)
        page_str = f"Page {page_num + 1}" if page_num is not None else "Page N/A"

        context_chunks.append(doc.page_content)
        citations.append({
            "source": filename,
            "page": page_str,
            "snippet": doc.page_content[:200] + "..."
        })

    context_text = "\n\n".join(context_chunks)

    try:
        answer = rag_chain.invoke({
            "context": context_text,
            "chat_history": formatted_history,
            "question": prompt
        })
    except Exception as e:
        raise RuntimeError(f"Error generating answer from LLM: {e}")

    return {
        "status": "success",
        "answer": answer,
        "citations": citations
    }

def stream_query_rag_service(prompt: str, chat_history: list = None):
    """Executes streaming RAG query yielding SSE events."""
    global compression_retriever, ensemble_retriever
    active_retriever = compression_retriever if compression_retriever is not None else ensemble_retriever
    if active_retriever is None:
        yield f"data: {json.dumps({'type': 'error', 'content': 'No documents have been indexed yet. Please upload files first.'})}\n\n"
        return

    formatted_history = ""
    if chat_history:
        for msg in chat_history:
            role_label = "Human" if msg.role == "user" else "Assistant"
            formatted_history += f"{role_label}: {msg.content}\n"

    rewritten_prompt = prompt
    if chat_history:
        try:
            rewritten_prompt = condense_chain.invoke({
                "chat_history": formatted_history,
                "question": prompt
            }).strip()
        except Exception as e:
            logger.error(f"Failed to condense query for stream: {e}")

    try:
        relevant_docs = active_retriever.invoke(rewritten_prompt)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error retrieving context: {e}'})}\n\n"
        return

    context_chunks = []
    citations = []
    for doc in relevant_docs:
        filename = doc.metadata.get("filename") or os.path.basename(doc.metadata.get("source", "Unknown Source"))
        page_num = doc.metadata.get("page", None)
        page_str = f"Page {page_num + 1}" if page_num is not None else "Page N/A"

        context_chunks.append(doc.page_content)
        citations.append({
            "source": filename,
            "page": page_str,
            "snippet": doc.page_content[:200] + "..."
        })

    yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
    context_text = "\n\n".join(context_chunks)

    try:
        for chunk in rag_chain.stream({
            "context": context_text,
            "chat_history": formatted_history,
            "question": prompt
        }):
            if chunk:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error generating answer: {e}'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'end'})}\n\n"
