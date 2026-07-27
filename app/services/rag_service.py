import os
import json
import datetime
from dotenv import load_dotenv
from langchain_core.documents import Document

# LangChain Imports
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from flashrank import Ranker
from langchain_community.document_compressors import FlashrankRerank

# Project Imports
from app.loaders.loader_factory import get_document_loader
from app.utils.logger import logger

load_dotenv()

UPLOAD_DIR = "./uploaded_files"
CHROMA_DIR = "./chroma_db"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)

# Registry file tracks which files are already indexed (filename → mtime)
# Stored inside chroma_db/ so it persists alongside the embeddings
REGISTRY_PATH = os.path.join(CHROMA_DIR, "index_registry.json")

# BM25 cache file — saves rebuilt BM25 index to disk so restarts are instant
BM25_CACHE_PATH = os.path.join(CHROMA_DIR, "bm25_cache.pkl")

# 1. Initialize models and chains
# Embeddings: local HuggingFace model (no API calls, works with SemanticChunker)
logger.info("Initializing HuggingFace Embeddings Model...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# ─── Chunking Strategy Factory ────────────────────────────────────────────────

def get_text_splitter():
    """
    Reads CHUNKING_STRATEGY from .env and returns the appropriate text splitter.

    Options:
        CHUNKING_STRATEGY=semantic   → SemanticChunker (embedding-based boundaries)
        CHUNKING_STRATEGY=recursive  → RecursiveCharacterTextSplitter (fixed size)

    How SemanticChunker works:
        1. Splits document into individual sentences.
        2. Computes vector embeddings for each sentence.
        3. Measures cosine distance between adjacent sentence embeddings.
        4. Creates a chunk boundary where the distance exceeds the threshold.
           (i.e. where the topic/meaning significantly shifts)

    Breakpoint types:
        percentile      → split where distance > Nth percentile of all distances
        standard_deviation → split where distance > mean + N * std_dev
        interquartile   → split based on IQR outlier detection
        gradient        → split where the gradient of distance changes sharply
    """
    strategy = os.getenv("CHUNKING_STRATEGY", "recursive").lower()

    if strategy == "semantic":
        breakpoint_type   = os.getenv("SEMANTIC_BREAKPOINT_TYPE", "percentile")
        breakpoint_amount = float(os.getenv("SEMANTIC_BREAKPOINT_AMOUNT", "90.0"))
        logger.info(
            f"Chunking strategy: SemanticChunker "
            f"(breakpoint_type={breakpoint_type}, threshold={breakpoint_amount})"
        )
        return SemanticChunker(
            embeddings=embeddings,
            breakpoint_threshold_type=breakpoint_type,
            breakpoint_threshold_amount=breakpoint_amount
        )
    else:
        logger.info("Chunking strategy: RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)")
        return RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

# Load existing Chroma DB
logger.info("Initializing Chroma Vectorstore...")
vectorstore = Chroma(
    persist_directory=CHROMA_DIR,
    embedding_function=embeddings
)

# Initialize Groq LLM (Llama 3.1)
logger.info("Initializing Groq Chat LLM...")
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.3,
    streaming=True
)

# Build RAG Chain
# 1. Query Condensation Prompt (Context-Aware Standalone Query generator)
condense_prompt_template = ChatPromptTemplate.from_template("""
Given the following conversation history and a follow-up question, rephrase the follow-up question to be a STANDALONE question that has all the context of the conversation. 
Do NOT answer the question. Just rephrase it and return ONLY the standalone question text. If the follow-up question is already a standalone question or if the conversation history is empty, return the follow-up question exactly as is.

Conversation History:
{chat_history}

Follow-up Question:
{question}

Standalone Question:
""")

condense_chain = condense_prompt_template | llm | StrOutputParser()

# 2. Main Question Answering Prompt
prompt_template = ChatPromptTemplate.from_template("""
You are an intelligent organizational playbook and troubleshooting assistant. 
Answer the user's question using ONLY the provided context.
If the answer is not in the context, say "I don't know based on the provided documents."

Context:
{context}

Conversation History:
{chat_history}

Question:
{question}

Answer:
""")

rag_chain = prompt_template | llm | StrOutputParser()

# Global variables for BM25, Ensemble, and Compression retrievers
bm25_retriever = None
ensemble_retriever = None
compression_retriever = None
all_documents = []  # List to track all active chunks

# ─── Incremental Index Registry Helpers ──────────────────────────────────────

def load_index_registry() -> dict:
    """
    Loads the registry JSON that tracks which files have been indexed.
    Returns an empty dict if the registry doesn't exist yet.
    """
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load index registry: {e}. Starting fresh.")
    return {}

def save_index_registry(registry: dict):
    """Persists the registry to disk inside chroma_db/."""
    try:
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)
    except Exception as e:
        logger.error(f"Could not save index registry: {e}")

def delete_file_chunks(file_name: str):
    """Removes all stored chunks for a specific file from the Chroma vectorstore."""
    global vectorstore
    try:
        vectorstore._collection.delete(where={"filename": file_name})
        logger.info(f"Removed old chunks for '{file_name}' from vectorstore.")
    except Exception as e:
        logger.warning(f"Could not remove chunks for '{file_name}': {e}")

def save_bm25_cache(retriever):
    """Saves the BM25 retriever to disk so it can be loaded instantly on restart."""
    try:
        import pickle
        with open(BM25_CACHE_PATH, "wb") as f:
            pickle.dump(retriever, f)
        logger.info("BM25 cache saved to disk. ⚡")
    except Exception as e:
        logger.warning(f"Could not save BM25 cache: {e}")

def load_bm25_cache():
    """Loads the BM25 retriever from disk cache. Returns None if not available."""
    try:
        import pickle
        if os.path.exists(BM25_CACHE_PATH):
            with open(BM25_CACHE_PATH, "rb") as f:
                retriever = pickle.load(f)
            logger.info("⚡ BM25 cache loaded from disk — skipping BM25 rebuild.")
            return retriever
    except Exception as e:
        logger.warning(f"Could not load BM25 cache: {e}. Will rebuild from scratch.")
    return None

def rebuild_retrievers():
    """
    Incremental indexing: only chunks and embeds NEW or MODIFIED files.
    Files already present in the Chroma DB are loaded directly — skipping
    re-chunking and re-embedding — making server restarts near-instant.

    Logic:
        1. Compare uploaded_files/ against the index_registry.json
        2. New file      → chunk + embed + add to Chroma
        3. Modified file → delete old chunks + re-chunk + re-embed
        4. Deleted file  → remove chunks from Chroma
        5. Unchanged     → skip entirely (load from Chroma directly) ⚡
    """
    global bm25_retriever, ensemble_retriever, compression_retriever, all_documents, vectorstore

    all_documents = []

    if not os.path.exists(UPLOAD_DIR):
        bm25_retriever = None
        ensemble_retriever = None
        return

    files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]

    # Load the persistent registry
    index_registry = load_index_registry()

    # ── Detect what changed ───────────────────────────────────────────────────
    new_or_modified = []
    for file_name in files:
        file_path = os.path.join(UPLOAD_DIR, file_name)
        current_mtime = os.path.getmtime(file_path)
        if file_name not in index_registry or index_registry[file_name]["mtime"] != current_mtime:
            new_or_modified.append(file_name)

    deleted_files = [f for f in index_registry if f not in files]

    # ── Handle deleted files ──────────────────────────────────────────────────
    for file_name in deleted_files:
        logger.info(f"File deleted: '{file_name}'. Removing chunks from vectorstore...")
        delete_file_chunks(file_name)
        del index_registry[file_name]

    # ── Process new or modified files ─────────────────────────────────────────
    if new_or_modified:
        loaded_docs = []
        for file_name in new_or_modified:
            file_path = os.path.join(UPLOAD_DIR, file_name)
            _, ext = os.path.splitext(file_name.lower())
            status = "Modified" if file_name in index_registry else "New"
            logger.info(f"{status} file detected: '{file_name}'. Indexing...")

            # Remove stale chunks if file was modified
            if file_name in index_registry:
                delete_file_chunks(file_name)

            try:
                loader = get_document_loader(file_path)
                logger.info(f"Selected loader: {loader.__class__.__name__} for file: {file_name}")
                docs = loader.load()
                logger.info(f"Extraction success: extracted {len(docs)} documents/pages from {file_name}")

                upload_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                for doc in docs:
                    doc.metadata["filename"] = file_name
                    doc.metadata["extension"] = ext
                    doc.metadata["upload_timestamp"] = upload_time
                    if "source" not in doc.metadata:
                        doc.metadata["source"] = file_path

                loaded_docs.extend(docs)

                # Register the file with its current mtime
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
            logger.info(
                f"Chunking complete. Strategy: '{os.getenv('CHUNKING_STRATEGY', 'recursive')}' "
                f"| New chunks added: {len(new_chunks)}"
            )
            # Add ONLY new chunks — do NOT delete_collection!
            vectorstore.add_documents(new_chunks)
            logger.info(f"Successfully added {len(new_chunks)} new chunks to Chroma DB.")

    else:
        if not files:
            logger.info("No documents found in upload folder. Retrievers are empty.")
            bm25_retriever = None
            ensemble_retriever = None
            save_index_registry(index_registry)
            return
        logger.info(
            f"⚡ All {len(files)} file(s) already indexed. "
            f"Loading from Chroma DB — skipping re-chunking and re-embedding."
        )

    # Persist updated registry
    save_index_registry(index_registry)

    # ── Reconstruct all_documents from Chroma for BM25 ───────────────────────
    # If no files changed AND BM25 cache exists → load from cache (instant ⚡)
    # If files changed → rebuild BM25 from Chroma and save new cache
    files_changed = bool(new_or_modified or deleted_files)

    if not files_changed:
        # Try loading BM25 from cache first
        cached_bm25 = load_bm25_cache()
        if cached_bm25 is not None:
            bm25_retriever = cached_bm25
            retriever_top_k = int(os.getenv("RETRIEVER_TOP_K", "15"))
            bm25_retriever.k = retriever_top_k

            # Still load all_documents for get_rag_status() chunk count
            try:
                chroma_data = vectorstore.get(include=["documents", "metadatas"])
                if chroma_data and chroma_data.get("documents"):
                    all_documents = [
                        Document(page_content=content, metadata=meta or {})
                        for content, meta in zip(chroma_data["documents"], chroma_data["metadatas"])
                    ]
            except Exception as e:
                logger.warning(f"Could not load documents for status: {e}")

            # Build remaining retrievers using cached BM25
            reranker_top_n = int(os.getenv("RERANKER_TOP_N", "4"))
            hybrid_semantic_weight = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", "0.5"))
            hybrid_keyword_weight = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.5"))
            semantic_retriever = vectorstore.as_retriever(search_kwargs={"k": retriever_top_k})
            ensemble_retriever = EnsembleRetriever(
                retrievers=[semantic_retriever, bm25_retriever],
                weights=[hybrid_semantic_weight, hybrid_keyword_weight]
            )
            try:
                logger.info(f"Integrating FlashRank Reranker (top_n={reranker_top_n})...")
                compressor = FlashrankRerank(top_n=reranker_top_n)
                compression_retriever = ContextualCompressionRetriever(
                    base_compressor=compressor,
                    base_retriever=ensemble_retriever
                )
                logger.info("FlashRank Reranker successfully integrated.")
            except Exception as e:
                logger.error(f"Failed to initialize FlashRank Reranker: {e}. Falling back.")
                compression_retriever = ensemble_retriever
            logger.info("Retrievers successfully rebuilt.")
            return

    # Files changed OR no BM25 cache → full rebuild from Chroma
    try:
        chroma_data = vectorstore.get(include=["documents", "metadatas"])
        if chroma_data and chroma_data.get("documents"):
            all_documents = [
                Document(page_content=content, metadata=meta or {})
                for content, meta in zip(chroma_data["documents"], chroma_data["metadatas"])
            ]
            logger.info(f"Loaded {len(all_documents)} total chunks from Chroma DB for BM25 index.")
    except Exception as e:
        logger.error(f"Failed to load documents from Chroma for BM25: {e}")

    if not all_documents:
        logger.warning("No documents in vectorstore. Retrievers are empty.")
        bm25_retriever = None
        ensemble_retriever = None
        return

    # ── Build retrievers ──────────────────────────────────────────────────────
    retriever_top_k = int(os.getenv("RETRIEVER_TOP_K", "15"))
    reranker_top_n = int(os.getenv("RERANKER_TOP_N", "4"))
    hybrid_semantic_weight = float(os.getenv("HYBRID_SEMANTIC_WEIGHT", "0.5"))
    hybrid_keyword_weight = float(os.getenv("HYBRID_KEYWORD_WEIGHT", "0.5"))

    bm25_retriever = BM25Retriever.from_documents(all_documents)
    bm25_retriever.k = retriever_top_k

    # Save BM25 to cache for fast next restart
    save_bm25_cache(bm25_retriever)

    semantic_retriever = vectorstore.as_retriever(search_kwargs={"k": retriever_top_k})

    ensemble_retriever = EnsembleRetriever(
        retrievers=[semantic_retriever, bm25_retriever],
        weights=[hybrid_semantic_weight, hybrid_keyword_weight]
    )

    try:
        logger.info(f"Integrating FlashRank Reranker (top_n={reranker_top_n})...")
        compressor = FlashrankRerank(top_n=reranker_top_n)
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor,
            base_retriever=ensemble_retriever
        )
        logger.info("FlashRank Reranker successfully integrated.")
    except Exception as e:
        logger.error(f"Failed to initialize FlashRank Reranker: {e}. Falling back to standard hybrid retriever.")
        compression_retriever = ensemble_retriever

    logger.info("Retrievers successfully rebuilt.")


def get_rag_status():
    """
    Returns files currently uploaded, chunk count, indexing status,
    and the active chunking strategy.
    """
    files = []
    if os.path.exists(UPLOAD_DIR):
        files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    return {
        "uploaded_files": files,
        "total_chunks": len(all_documents),
        "indexing_active": ensemble_retriever is not None,
        "chunking_strategy": os.getenv("CHUNKING_STRATEGY", "recursive")
    }

def query_rag_service(prompt: str, chat_history: list = None):
    """
    Executes a RAG query using the hybrid ensemble retriever, FlashRank reranker, and Groq LLM chain.
    Handles conversation memory via query condensation.
    """
    global compression_retriever, ensemble_retriever, rag_chain, condense_chain
    
    active_retriever = compression_retriever if compression_retriever is not None else ensemble_retriever
    if active_retriever is None:
        raise ValueError("No documents have been indexed yet. Please upload files first.")
        
    # Format chat history for prompt templates
    formatted_history = ""
    if chat_history:
        for msg in chat_history:
            role_label = "Human" if msg.role == "user" else "Assistant"
            formatted_history += f"{role_label}: {msg.content}\n"
            
    # Perform query condensation (rewriting) if there is conversational history
    rewritten_prompt = prompt
    if chat_history:
        try:
            rewritten_prompt = condense_chain.invoke({
                "chat_history": formatted_history,
                "question": prompt
            }).strip()
            logger.info(f"RAG Chat History - Original: '{prompt}' | Rewritten standalone: '{rewritten_prompt}'")
        except Exception as e:
            logger.error(f"Failed to condense query: {e}. Using raw prompt instead.")
            
    # Retrieve relevant documents using the rewritten prompt
    try:
        relevant_docs = active_retriever.invoke(rewritten_prompt)
    except Exception as e:
        raise RuntimeError(f"Error retrieving context from database: {e}")

    logger.info(f"--- RAG Debug: Retrieved {len(relevant_docs)} documents for rewritten query '{rewritten_prompt}' ---")
    for idx, doc in enumerate(relevant_docs):
        logger.info(f"Doc {idx + 1} Source: {doc.metadata.get('filename')} | Content snippet: {doc.page_content[:150].replace('\n', ' ')}")
        
    # Prepare citations and text context
    context_chunks = []
    citations = []
    
    for doc in relevant_docs:
        # Retrieve metadata
        filename = doc.metadata.get("filename") or os.path.basename(doc.metadata.get("source", "Unknown Source"))
        page_num = doc.metadata.get("page", None)
        page_str = f"Page {page_num + 1}" if page_num is not None else "Page N/A"
        
        context_chunks.append(doc.page_content)
        citations.append({
            "source": filename,
            "page": page_str,
            "snippet": doc.page_content[:200] + "..."
        })
        
    # Combine context chunks for the prompt
    context_text = "\n\n".join(context_chunks)
    
    # Run the LLM chain (passing context, chat history, and raw prompt question)
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
    """
    Executes a RAG query and yields SSE (Server-Sent Events) formatted strings.
    Yields:
      - 'data: {"type": "citations", "citations": [...]}\n\n'
      - 'data: {"type": "token", "content": "..."}\n\n'
      - 'data: {"type": "end"}\n\n'
    """
    global compression_retriever, ensemble_retriever, rag_chain, condense_chain

    active_retriever = compression_retriever if compression_retriever is not None else ensemble_retriever
    if active_retriever is None:
        yield f"data: {json.dumps({'type': 'error', 'content': 'No documents have been indexed yet. Please upload files first.'})}\n\n"
        return

    # Format chat history for prompt templates
    formatted_history = ""
    if chat_history:
        for msg in chat_history:
            role_label = "Human" if msg.role == "user" else "Assistant"
            formatted_history += f"{role_label}: {msg.content}\n"

    # Perform query condensation (rewriting) if there is conversational history
    rewritten_prompt = prompt
    if chat_history:
        try:
            rewritten_prompt = condense_chain.invoke({
                "chat_history": formatted_history,
                "question": prompt
            }).strip()
            logger.info(f"RAG Stream History - Original: '{prompt}' | Rewritten standalone: '{rewritten_prompt}'")
        except Exception as e:
            logger.error(f"Failed to condense query for stream: {e}. Using raw prompt instead.")

    # Retrieve relevant documents using the rewritten prompt
    try:
        relevant_docs = active_retriever.invoke(rewritten_prompt)
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error retrieving context from database: {e}'})}\n\n"
        return

    logger.info(f"--- RAG Debug: Stream retrieved {len(relevant_docs)} documents for rewritten query '{rewritten_prompt}' ---")

    # Prepare citations and text context
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

    # Yield citations packet first
    yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

    # Combine context chunks for the prompt
    context_text = "\n\n".join(context_chunks)

    # Stream the LLM chain tokens
    try:
        for chunk in rag_chain.stream({
            "context": context_text,
            "chat_history": formatted_history,
            "question": prompt
        }):
            if chunk:
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'Error generating answer from LLM: {e}'})}\n\n"
        return

    yield f"data: {json.dumps({'type': 'end'})}\n\n"

