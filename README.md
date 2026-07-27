# Intelligent Hybrid RAG Chatbot (RAG Pro)

Welcome to **RAG Pro**, a comprehensive, full-stack, enterprise-grade Retrieval-Augmented Generation (RAG) assistant designed for playbooks, manuals, regulations, and troubleshooting guides. 

This repository leverages **LangChain**, **FastAPI**, **Chroma DB**, **FlashRank Reranker**, and **Groq Cloud (Llama 3.1)** to deliver real-time, highly accurate answers backed by precise document source and page-level citations.

---

## 🛠️ Key Architectural Features

- **Dynamic Multi-Format Ingestor**: Supported by a custom loader factory capable of parsing `.pdf`, `.docx`, `.txt`, `.csv`, `.pptx`, `.html`, and `.md` documents.
- **Hybrid Search Engine**: Combines Dense Retrieval (semantic vector search via `Chroma` + `sentence-transformers`) and Sparse Retrieval (keyword search via `BM25`) in a weighted ensemble retriever.
- **Stage 2 Contextual Reranking**: Uses a local **FlashRank Cross-Encoder** model to re-score candidate chunks and compress context down to the top 4 most relevant chunks.
- **⚡ Real-Time SSE Token Streaming**: Streams LLM output tokens word-by-word into the UI via **Server-Sent Events (SSE)** using `POST /query/stream` and Groq's `llama-3.1-8b-instant`.
- **⚡ Incremental Indexing & BM25 Pickle Cache**: Smart change detection via `index_registry.json` and persistent `bm25_cache.pkl` — skips re-chunking/re-embedding on server restarts for sub-5-second startup times.
- **🔐 JWT Authentication**: Built-in user registration, login, PBKDF2 password hashing with salt, and bearer token authorization.
- **🗑️ Document Lifecycle Management**: Delete button on each uploaded file in the UI sidebar (`DELETE /files/{filename}`) that automatically cleans up disk files, Chroma vectorstore entries, and index registry metadata.
- **🐳 Docker Containerization**: Includes production `Dockerfile`, `docker-compose.yml`, `.dockerignore`, and volume mounts for 1-command deployment.

---

## 📂 Project Structure

- [server.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/server.py): Entry point for backend server; mounts routes, configures CORS, static UI redirect, and triggers startup indexing.
- [Dockerfile](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/Dockerfile): Production Docker container configuration (Python 3.11-slim + C++ build tools).
- [docker-compose.yml](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/docker-compose.yml): Docker Compose file with persistent volume mounts (`uploaded_files`, `chroma_db`, `app/db`).
- [requirements.txt](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/requirements.txt): List of Python dependencies.
- **app/**: Backend source directory.
  - **api/**: FastAPI routes:
    - [endpoints.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/endpoints.py): `/upload`, `/query`, `/query/stream`, `DELETE /files/{filename}`, `/status`.
    - [auth.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/auth.py): `/auth/register` and `/auth/login`.
    - [deps.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/deps.py): JWT authentication dependency.
  - **db/**: User database layer:
    - [user_db.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/db/user_db.py): SQLite user database storage and PBKDF2 password hashing.
  - **loaders/**: Parsers for multiple document formats (`pdf`, `docx`, `csv`, `ppt`, `html`, `md`, `txt`).
  - **services/**: Business Logic:
    - [rag_service.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/services/rag_service.py): Manages incremental indexing, hybrid search, FlashRank reranking, SSE streaming generator, and BM25 cache.
- **static/**: Frontend dark-mode UI dashboard ([index.html](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/index.html), [style.css](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/style.css), [app.js](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/app.js)).

---

## ⚡ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Groq Cloud API Key (configured in `.env`)

### 2. Environment Variables
Create a `.env` file in the project root:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
JWT_SECRET_KEY=your_super_secret_jwt_key
CHUNKING_STRATEGY=recursive
RETRIEVER_TOP_K=15
RERANKER_TOP_N=4
HYBRID_SEMANTIC_WEIGHT=0.5
HYBRID_KEYWORD_WEIGHT=0.5
```

### 3. Install Dependencies & Run Locally
```bash
pip install -r requirements.txt
python -m uvicorn server:app --port 8002
```
Access the application directly at: **`http://localhost:8002`**

---

## 🐳 Docker Deployment

### Run with Docker Compose
```bash
docker-compose up --build
```

### Cloud Deployment (AWS App Runner / Railway / Render)
1. Push repository to GitHub.
2. Connect to AWS App Runner / Railway.
3. The platform automatically detects `Dockerfile` and deploys to a public HTTPS URL.

---

## 📡 API Reference

### 1. User Registration & Login
- `POST /auth/register` — Body: `{"username": "...", "email": "...", "password": "..."}`
- `POST /auth/login` — Body: `{"username": "...", "password": "..."}` → Returns JWT Access Token.

### 2. Upload Document
- `POST /upload` — `multipart/form-data` with `file`. Header: `Authorization: Bearer <token>`.

### 3. Stream Query (SSE - Word-by-Word)
- `POST /query/stream` — Body: `{"prompt": "...", "chat_history": [...]}`. Header: `Authorization: Bearer <token>`.
- Returns: `text/event-stream` with citation payload and real-time LLM tokens.

### 4. Delete File
- `DELETE /files/{filename}` — Header: `Authorization: Bearer <token>`. Removes document from disk, vectorstore, and index registry.

