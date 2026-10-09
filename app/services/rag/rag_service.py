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
from app.services.rag.generation_service import condense_chain, rag_chain, no_context_chain

UPLOAD_DIR = settings.UPLOAD_DIR
CHROMA_DIR = settings.CHROMA_PATH

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)

llm = get_llm(temperature=0.3)

# Phrases the rag_chain prompt (generation_service.py) is instructed to use when
# it falls back to general knowledge because the retrieved context didn't cover
# the question. Used to detect that case so the retrieved-but-unused chunks
# aren't shown to the user as if they were the answer's actual source.
_GENERAL_KNOWLEDGE_MARKERS = (
    "couldn't find this in your uploaded documents",
    "could not find this in your uploaded documents",
    "based on general knowledge",
)

def _used_general_knowledge(answer_text: str) -> bool:
    lowered = (answer_text or "").lower()
    return any(marker in lowered for marker in _GENERAL_KNOWLEDGE_MARKERS)

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
    """Executes a full RAG query.

    When no documents are indexed at all, falls back to answering from the LLM's
    own general knowledge (clearly a different code path from the normal RAG
    answer, which itself is also instructed to fall back to general knowledge,
    clearly labeled, whenever the retrieved context doesn't cover the question).
    """
    global compression_retriever, ensemble_retriever
    active_retriever = compression_retriever if compression_retriever is not None else ensemble_retriever

    formatted_history = ""
    if chat_history:
        for msg in chat_history:
            role_label = "Human" if msg.role == "user" else "Assistant"
            formatted_history += f"{role_label}: {msg.content}\n"

    if active_retriever is None:
        try:
            answer = no_context_chain.invoke({"chat_history": formatted_history, "question": prompt})
        except Exception as e:
            raise RuntimeError(f"Error generating answer from LLM: {e}")
        return {"status": "success", "answer": answer, "citations": []}

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

    # If the model fell back to general knowledge, the retrieved chunks weren't
    # actually the source of the answer — don't present them as if they were.
    if _used_general_knowledge(answer):
        citations = []

    return {
        "status": "success",
        "answer": answer,
        "citations": citations
    }

def stream_query_rag_service(prompt: str, chat_history: list = None):
    """Executes streaming RAG query yielding SSE events.

    When no documents are indexed at all, streams a general-knowledge answer
    instead of erroring out — same fallback principle as query_rag_service().
    """
    global compression_retriever, ensemble_retriever
    active_retriever = compression_retriever if compression_retriever is not None else ensemble_retriever

    formatted_history = ""
    if chat_history:
        for msg in chat_history:
            role_label = "Human" if msg.role == "user" else "Assistant"
            formatted_history += f"{role_label}: {msg.content}\n"

    if active_retriever is None:
        yield f"data: {json.dumps({'type': 'citations', 'citations': []})}\n\n"
        try:
            for chunk in no_context_chain.stream({"chat_history": formatted_history, "question": prompt}):
                if chunk:
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Error generating answer: {e}'})}\n\n"
            return
        yield f"data: {json.dumps({'type': 'end'})}\n\n"
        return

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

    # Citations aren't sent immediately: if the model ends up falling back to
    # general knowledge (because the retrieved chunks didn't actually cover the
    # question), those chunks must NOT be shown as the answer's source. So the
    # first ~160 characters of the answer are buffered just long enough to check
    # for the fallback marker before committing to a citations list — after that,
    # tokens stream through live as before.
    context_text = "\n\n".join(context_chunks)
    BUFFER_DECISION_LIMIT = 160
    buffer = ""
    decided = False

    def _flush_decision(buffered_text: str):
        final_citations = [] if _used_general_knowledge(buffered_text) else citations
        return f"data: {json.dumps({'type': 'citations', 'citations': final_citations})}\n\n"

    try:
        for chunk in rag_chain.stream({
            "context": context_text,
            "chat_history": formatted_history,
            "question": prompt
        }):
            if not chunk:
                continue
            if not decided:
                buffer += chunk
                if _used_general_knowledge(buffer) or len(buffer) >= BUFFER_DECISION_LIMIT:
                    decided = True
                    yield _flush_decision(buffer)
                    yield f"data: {json.dumps({'type': 'token', 'content': buffer})}\n\n"
                    buffer = ""
            else:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        if not decided:
            # The whole answer was shorter than the buffer limit — decide now.
            yield _flush_decision(buffer)
            if buffer:
                yield f"data: {json.dumps({'type': 'token', 'content': buffer})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error generating answer: {e}'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'end'})}\n\n"
