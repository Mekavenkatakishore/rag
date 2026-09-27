# Intelligent Hybrid RAG Playbook & Agentic AI HR Assistant

This documentation details the complete architecture of the **RAG Pro** platform, featuring **Clean Layered Architecture** and an **Agentic AI Layer** powered by **LangGraph** and **LangChain Tools**.

---

## 📂 1. Project Directory Structure

```text
rag_pro/
│
├── server.py                        # FastAPI entrypoint (mounts /api, /auth, /hr, /agent, static UI)
├── requirements.txt                 # Dependencies (including langgraph)
├── Dockerfile & docker-compose.yml  # Containerization
├── .env & .env.example              # Centralized environment variables
│
├── app/                             # Core Backend Application
│   ├── core/                        # Infrastructure & Settings
│   │   ├── config.py               # Centralized settings (Pydantic Settings wrapper)
│   │   ├── security.py             # Security primitives (PBKDF2 hashing & JWT encoding/decoding)
│   │   ├── llm_factory.py          # Centralized Groq LLM client factory with auto-discovery
│   │   └── exceptions.py           # Application exception hierarchy
│   │
│   ├── agent/                       # 🤖 Agentic AI Layer (LangGraph & LangChain)
│   │   ├── __init__.py
│   │   ├── llm.py                  # Re-exports core ChatGroq factory
│   │   ├── state.py                # AgentState schema (messages, intent, logs, approval flags)
│   │   ├── prompts.py              # Intent classification prompt template
│   │   ├── router.py               # Conditional edge router & approval gate
│   │   ├── graph.py                # StateGraph workflow assembly with MemorySaver checkpointer
│   │   ├── tools/                  # LangChain @tool Wrappers
│   │   │   ├── rag_tools.py        # search_hr_knowledge tool (hybrid RAG search)
│   │   │   ├── hr_tools.py         # match_candidates, get_candidate_details, generate_interview_questions, generate_candidate_summary
│   │   │   └── action_tools.py     # draft_candidate_email, send_candidate_email (Human Approval)
│   │   └── nodes/                  # Graph Workflow Nodes
│   │       ├── analysis.py         # analyze_query_node (LLM query intent classifier)
│   │       ├── execution.py        # tool_execution_node (executes selected agent tool)
│   │       └── response.py         # response_generation_node (synthesizes final answer & activity log)
│   │
│   ├── schemas/                     # Data Validation Layer (Pydantic Models)
│   │   ├── rag_schemas.py          # Query, upload, streaming, status schemas
│   │   ├── hr_schemas.py           # Job container, candidate, leaderboard, chat schemas
│   │   ├── auth_schemas.py         # User registration & login schemas
│   │   └── agent_schemas.py        # Agent chat, approve, reject, status schemas
│   │
│   ├── db/                          # Database Access Layer (SQLite)
│   │   ├── base_db.py              # Context manager for connection pooling & transactions
│   │   ├── hr_db.py                # HR jobs, candidate profiles, scores & citation queries
│   │   └── user_db.py              # User authentication queries
│   │
│   ├── loaders/                     # Document Parsing Loader Factory
│   │   ├── base.py                 # Abstract loader interface wrapper
│   │   ├── loader_factory.py       # File extension dispatch loader factory
│   │   └── [pdf/docx/txt/csv/ppt/html/md]_loader.py
│   │
│   ├── services/                    # Modular Business Services (Independent Layer)
│   │   ├── rag/                    # Modular RAG Package (ingestion, retrieval, reranking, generation)
│   │   ├── hr/                     # Modular HR Package (jd_parser, resume_parser, scoring, evidence)
│   │   └── auth/                   # Authentication Package
│   │
│   ├── api/                         # Thin API Controllers
│   │   ├── endpoints.py            # RAG playbook routes (/upload, /query/stream, /files/{filename})
│   │   ├── hr_endpoints.py         # Candidate screening routes (/hr/jobs/*)
│   │   ├── auth.py                 # Auth routes (/auth/register, /auth/login)
│   │   ├── agent_endpoints.py      # Agentic AI routes (/agent/chat, /agent/approve, /agent/reject)
│   │   └── deps.py                 # JWT Bearer token dependency
│   │
│   └── utils/
│       └── logger.py               # Standardized logging
│
├── static/                          # Dark mode frontend UI (index.html, style.css, app.js)
├── tests/                           # Consolidated Test Suite
│   ├── unit/                       # Unit tests (test_hr_matching.py)
│   ├── agent/                      # Agent tests (test_graph.py)
│   ├── integration/                # Integration tests (test_auth.py)
│   ├── e2e/                        # End-to-End API tests (test_phase1.py, test_phase2.py)
│   └── benchmarks/                 # Performance benchmarks (test_semantic_chunking.py)
│
└── scripts/                         # Diagnostic & helper scripts (diag.py, find_retriever.py, test_groq.py)
```

---

## ⚙️ 2. Agentic AI Architecture & Control Flow

```text
                                User Request
                                     │
                                     ▼
                          FastAPI POST /agent/chat
                                     │
                                     ▼
                           StateGraph (LangGraph)
                                     │
                        ┌────────────┴────────────┐
                        ▼                         ▼
              analyze_query_node          MemorySaver Checkpointer
             (Intent Classification)       (Session State per thread_id)
                        │
                        ▼
                route_by_intent
                        │
         ┌──────────────┼──────────────┬──────────────┐
         ▼              ▼              ▼              ▼
    search_hr     match_candidate  get_details   draft_email / send
    _knowledge       s_tool          _tool          _email_tool
         │              │              │              │
         ▼              ▼              ▼              ▼
  rag_service.py hr_service.py     hr_db.py     Human Approval Gate
                                                      │
                                               ┌──────┴──────┐
                                               ▼             ▼
                                           Approved       Rejected
```

---

## 🔐 3. Human-in-the-Loop Approval Policy

Sensitive actions (such as dispatching emails to candidates) toggle `approval_required = True` and set `approval_status = "pending"`. The workflow pauses and returns an explicit `PENDING APPROVAL` state to the client UI.

* **POST `/agent/approve`**: HR User approves $\rightarrow$ Agent resumes execution and dispatches the action.
* **POST `/agent/reject`**: HR User rejects $\rightarrow$ Action is cancelled safely with zero side effects.