# Intelligent Hybrid RAG Chatbot (RAG Pro)

Welcome to **RAG Pro**, a comprehensive, full-stack, enterprise-grade Retrieval-Augmented Generation (RAG) assistant designed for playbooks, manuals, regulations, and troubleshooting guides. 

This repository leverages **LangChain**, **FastAPI**, **Chroma DB**, and **Groq Cloud (Llama-3)** to deliver highly accurate answers backed by precise document source and page-level citations.

---

## 🛠️ Key Architectural Features

- **Dynamic Document Ingestor**: Supported by a custom loader factory capable of parsing `.pdf`, `.docx`, `.txt`, `.csv`, `.pptx`, `.html`, and `.md` documents.
- **Hybrid Search Engine**: Combines Dense Retrieval (semantic vector search using `Chroma` + `sentence-transformers`) and Sparse Retrieval (keyword search using `BM25`) in a **70/30 weighted ensemble retriever** to offer robust conceptual and keyword matching.
- **Context-Aware LLM Reasoning**: Grounded prompt engineering with Groq's `llama-3.1-8b-instant` to prevent hallucinations and strictly restrict answers to the ingested document context.
- **Source and Page Citations**: Retains file extensions, names, upload dates, and page coordinates (for PDF files) to transparently show where every part of an answer comes from.
- **Premium Glassmorphic Frontend Dashboard**: A sleek, dark-mode user interface designed with fluid animations, interactive file uploads (drag-and-drop), progress indications, status monitoring, and citation highlights.

---

## 📂 Project Structure

Here is an overview of the key components in the [rag_pro folder](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro):

- [server.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/server.py): The entry point for the backend, configuring CORS, routing, static folders, and initializing the retrievers.
- [requirements.txt](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/requirements.txt): List of dependencies needed for parsing, embedding, vector database management, and hosting.
- **app/**: Backend source directory.
  - [app/__init__.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/__init__.py): Initializes app package module namespaces.
  - **api/**: API Endpoints.
    - [endpoints.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/api/endpoints.py): Holds FastAPI routes (`/upload`, `/query`, and `/status`).
  - **loaders/**: Parsers for multiple document formats.
    - [loader_factory.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/loader_factory.py): Directs input files to their respective custom loader builders.
    - [pdf_loader.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/pdf_loader.py): Parses PDF pages via `PyPDFLoader`.
    - [docx_loader.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/docx_loader.py): Extracts DOCX documents using `Docx2txtLoader`.
    - [text_loader.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/text_loader.py): Loads raw text files using `TextLoader`.
    - [csv_loader.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/csv_loader.py): Loads spreadsheets.
    - [ppt_loader.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/ppt_loader.py): Parses PowerPoint presentation contents.
    - [html_loader.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/html_loader.py): Parses webpage HTML.
    - [markdown_loader.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/loaders/markdown_loader.py): Parses unstructured Markdown files.
  - **services/**: Business Logic.
    - [rag_service.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/services/rag_service.py): Manages database creation/updates, text chunking, hybrid retrievers assembly, and query generation.
  - **utils/**: Helper classes.
    - [logger.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/app/utils/logger.py): Configures system logging formats.
- **static/**: Frontend static resources.
  - [index.html](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/index.html): Main layout structuring sidebar file loaders and chat logs.
  - [style.css](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/style.css): Styled animations, glassmorphism, responsive breakpoints, custom inputs, and dynamic styling rules.
  - [app.js](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/static/app.js): Script handling drag-and-drop actions, API integration, and rendering of message citation structures.
- **chroma_db/**: Persisted vector database storage directory.
- **uploaded_files/**: Directory holding processed source playbooks.
- **Testing Utilities**:
  - [test_phase1.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/test_phase1.py): Verifies document upload, chunking, and database indexing.
  - [test_phase2.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/test_phase2.py): Runs query simulations and outputs citations.
  - [find_retriever.py](file:///c:/Users/MekaKishore/workspaces/RAG/rag_pro/find_retriever.py): Locates correct package sources for the Ensemble Retriever class.

---

## ⚡ Setup & Installation

### 1. Prerequisites
- Python 3.10 or later
- Groq Cloud API Key (configured in a `.env` file)

### 2. Install Dependencies
Run the following command to install the required packages:
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a file named `.env` in the `rag_pro` directory:
```env
GROQ_API_KEY=your_groq_api_key_here
```

---

## 🚀 Running the Application

To start the FastAPI web server, execute:
```bash
python -m uvicorn server:app --reload --port 8002
```

Once running:
- **FastAPI backend** will listen on: `http://localhost:8002`
- **Frontend Dashboard** is accessible at: `http://localhost:8002/static/index.html`

---

## 📡 API Reference

### 1. Upload Document
- **Endpoint**: `POST /upload`
- **Content-Type**: `multipart/form-data`
- **Request**: Form field `file` containing the file payload.
- **Response**:
  ```json
  {
    "status": "success",
    "message": "Successfully uploaded and indexed 'manual.pdf'",
    "total_chunks": 124
  }
  ```

### 2. Query chatbot
- **Endpoint**: `POST /query`
- **Content-Type**: `application/json`
- **Request Body**:
  ```json
  {
    "prompt": "What is the parental leave duration?"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "answer": "Employees are eligible for up to 12 weeks of paid parental leave...",
    "citations": [
      {
        "source": "manual.pdf",
        "page": "Page 3",
        "snippet": "..."
      }
    ]
  }
  ```

### 3. System Status
- **Endpoint**: `GET /status`
- **Response**:
  ```json
  {
    "uploaded_files": ["manual.pdf"],
    "total_chunks": 124,
    "indexing_active": true
  }
  ```

---

## 🧪 Testing

We provide two python testing scripts to verify components locally:
1. **Pipeline test**: Run `python test_phase1.py` to upload a dummy file and index it.
2. **QA test**: Run `python test_phase2.py` to send question queries and print responses with page-level citations.
