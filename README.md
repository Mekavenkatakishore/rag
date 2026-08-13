# Intelligent Hybrid RAG & AI HR Candidate Matcher (RAG Pro)

Welcome to **RAG Pro**, a comprehensive, full-stack, enterprise-grade AI assistant combining **Playbook & Document Q&A RAG** with an **AI HR Resume & Candidate Matching Assistant**.

This repository leverages **LangChain**, **FastAPI**, **Chroma DB**, **FlashRank Reranker**, and **Groq Cloud (Llama 3.1)** to deliver real-time, grounded document answers alongside deterministic candidate fit rankings backed by precise citation evidence.

---

## 🛠️ Key Architectural Features

### 👤 1. AI HR Candidate Matcher & Resume Screening (Phase 1)
- **Target Job Description Parser**: Extracts structured role requirements, required/preferred skills, minimum experience, and education criteria via Groq LLM.
- **Canonical Skill Normalization**: Built-in skill normalizer (`app/services/skill_normalizer.py`) mapping tech variations (`Postgres` $\rightarrow$ `PostgreSQL`, `ReactJS` $\rightarrow$ `React`, `K8s` $\rightarrow$ `Kubernetes`, `NodeJS` $\rightarrow$ `Node.js`, `Amazon EC2` $\rightarrow$ `AWS`).
- **Deterministic Weighted Scoring Engine**: Application-level Python math (`app/services/scoring_engine.py`) calculating 100% reproducible scores (0–100) without LLM score hallucinations:
  - **Required Skills Fit:** 40%
  - **Relevant Experience:** 25%
  - **Project Relevance:** 15%
  - **Preferred Skills Fit:** 10%
  - **Education Fit:** 5%
  - **Domain Fit:** 5%
- **Fit Status Classification**: Automatically classifies candidates into `Strong Fit (≥80%)`, `Moderate Fit (60-79%)`, and `Weak Fit (<60%)`.
- **Hybrid Evidence Retrieval & FlashRank Reranking**: Filters vector & BM25 chunks by `job_id` and `candidate_id`, followed by FlashRank cross-encoder reranking to fetch top 5–6 supporting evidence passages.
- **Job-Isolated SQLite Persistence**: SQLite database (`app/db/hr_system.db`) tracking jobs (`hr_jobs`), candidate records (`hr_candidates`), profiles (`hr_candidate_profiles`), scores (`hr_candidate_scores`), and evidence quotes (`hr_candidate_evidence`).
- **Candidate Leaderboard & Citation Verification UI**: Ranked candidate leaderboard table with interactive details modal showing score breakdowns, matched/missing skill chips, exact resume quotes, document names, and page numbers.
- **Candidate Session Clear**: "Clear All Data" header button purging candidate records, scores, and disk files for fresh screening sessions.

---

### 📚 2. General RAG Playbook Assistant
- **Dynamic Multi-Format Ingestor**: Loader factory supporting `.pdf`, `.docx`, `.txt`, `.csv`, `.pptx`, `.html`, and `.md` documents.
- **Hybrid Search Engine**: Combines Dense Retrieval (`ChromaDB` + `sentence-transformers/all-MiniLM-L6-v2`) and Sparse Retrieval (`BM25Retriever`) in a weighted ensemble.
- **Stage 2 Contextual Reranking**: Uses local **FlashRank Cross-Encoder** model to re-score candidate passages and compress context down to top 4 relevant chunks.
- **⚡ Real-Time SSE Token Streaming**: Word-by-word LLM token streaming via **Server-Sent Events (SSE)** using `POST /query/stream` and Groq's `llama-3.1-8b-instant`.
- **⚡ Incremental Indexing & BM25 Pickle Cache**: Change detection via `index_registry.json` and persistent `bm25_cache.pkl` — sub-5-second server startup time.
- **🔐 JWT Authentication**: User registration, login, PBKDF2 password hashing with salt, and bearer token authorization.
- **🗑️ Document Lifecycle Management**: Delete button in UI sidebar (`DELETE /files/{filename}`) cleaning up disk files, Chroma vectorstore entries, and index metadata.
- **🐳 Docker Containerization**: Production `Dockerfile`, `docker-compose.yml`, `.dockerignore`, and volume mounts.

---

## 📂 Project Structure

- [server.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/server.py): Main ASGI server entry point; initializes databases, mounts API routers, CORS, and static UI routes.
- [Dockerfile](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/Dockerfile): Production Docker configuration (Python 3.11-slim + C++ build tools).
- [docker-compose.yml](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/docker-compose.yml): Docker Compose configuration with volume mounts (`uploaded_files`, `chroma_db`, `app/db`).
- [requirements.txt](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/requirements.txt): Python dependencies.
- **app/**: Backend application code.
  - **api/**: FastAPI route handlers:
    - [endpoints.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/endpoints.py): `/upload`, `/query`, `/query/stream`, `DELETE /files/{filename}`, `/status`.
    - [hr_endpoints.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/hr_endpoints.py): Job-scoped HR routes (`POST /hr/jobs`, upload JD, upload resumes, candidate analysis, leaderboard, candidate details, candidate chat, clear session).
    - [auth.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/auth.py): User `/auth/register` and `/auth/login`.
    - [deps.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/deps.py): JWT authentication dependency.
  - **db/**: Database persistence layer:
    - [hr_db.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/db/hr_db.py): SQLite storage for HR jobs, candidates, profiles, scores, and citations.
    - [user_db.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/db/user_db.py): SQLite storage for user accounts and PBKDF2 password hashing.
  - **loaders/**: Loader factory parsing multiple document formats (`pdf`, `docx`, `csv`, `ppt`, `html`, `md`, `txt`).
  - **services/**: Core Business Logic:
    - [hr_service.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/services/hr_service.py): JD parsing, batch resume ingestion, hybrid candidate evidence retrieval, FlashRank reranking, and LLM evidence extraction.
    - [scoring_engine.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/services/scoring_engine.py): Deterministic candidate match score calculator.
    - [skill_normalizer.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/services/skill_normalizer.py): Canonical tech skill mapper.
    - [rag_service.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/services/rag_service.py): Incremental indexing, hybrid search, FlashRank reranking, SSE streaming generator, and BM25 cache.
- **static/**: Frontend dark-mode dashboard ([index.html](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/index.html), [style.css](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/style.css), [app.js](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/app.js)).
- **tests/**: Test suite ([test_hr_matching.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/tests/test_hr_matching.py)).

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
python -m uvicorn server:app --reload --port 8002
```
Access the application at: **`http://localhost:8002`**

---

## 🧪 Running Automated Tests

Run the HR Candidate Matcher unit test suite:
```bash
python -m unittest tests/test_hr_matching.py
```

---

## 📡 API Reference

### 1. User Registration & Login
- `POST /auth/register` — Body: `{"username": "...", "email": "...", "password": "..."}`
- `POST /auth/login` — Body: `{"username": "...", "password": "..."}` $\rightarrow$ Returns JWT Access Token.

### 2. AI HR Candidate Matcher Endpoints
- `POST /hr/jobs` — Body: `{"title": "Role Title"}` $\rightarrow$ Creates new job container.
- `POST /hr/jobs/{job_id}/upload-jd` — Form: `file` (PDF, DOCX, TXT) $\rightarrow$ Uploads and parses JD requirements.
- `POST /hr/jobs/{job_id}/upload-resumes` — Form: `files` (batch PDFs/DOCXs) $\rightarrow$ Indexes candidate resumes with metadata.
- `POST /hr/jobs/{job_id}/analyze` — Triggers hybrid evidence retrieval, FlashRank reranking, and deterministic candidate scoring.
- `GET /hr/jobs/{job_id}/leaderboard` — Returns candidate rankings and leaderboard JSON.
- `GET /hr/jobs/{job_id}/candidates/{candidate_id}` — Returns candidate profile, score breakdown metrics, and exact evidence quotes with page citations.
- `POST /hr/jobs/{job_id}/chat` — Body: `{"prompt": "..."}` $\rightarrow$ HR Q&A about candidates in active job.
- `POST /hr/jobs/{job_id}/clear` — Purges candidate records, scores, evidence, and uploaded disk files for a specific job.

### 3. General RAG Playbook Endpoints
- `POST /upload` — `multipart/form-data` with `file`.
- `POST /query/stream` — Body: `{"prompt": "...", "chat_history": [...]}` $\rightarrow$ Returns `text/event-stream` SSE tokens.
- `DELETE /files/{filename}` — Removes document from disk, vectorstore, and index registry.
