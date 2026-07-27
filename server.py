import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# Project Imports
from app.api.endpoints import router as api_router
from app.api.auth import auth_router
from app.services.rag_service import rebuild_retrievers
from app.db.user_db import initialize_db
from app.utils.logger import logger

app = FastAPI(title="Intelligent Hybrid RAG Chatbot")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include RAG API endpoints
app.include_router(api_router)

# Include Auth endpoints (prefixed with /auth)
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# Serve Static Files
STATIC_DIR = "./static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    """Redirect root URL directly to the web UI."""
    return RedirectResponse(url="/static/index.html")

# Build initial index and initialize DB on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    # Initialize the SQLite users database
    try:
        initialize_db()
        logger.info("Users database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize users database: {e}")
    # Rebuild the RAG index
    try:
        rebuild_retrievers()
    except Exception as e:
        logger.error(f"Failed to build initial retrievers during startup: {e}")
