import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# Project Imports
from app.api.endpoints import router as api_router
from app.api.auth import auth_router
from app.api.hr_endpoints import router as hr_router
from app.api.agent_endpoints import router as agent_router
from app.services.rag_service import rebuild_retrievers
from app.db.user_db import initialize_db
from app.db.hr_db import initialize_hr_db
from app.utils.logger import logger

app = FastAPI(title="Intelligent Hybrid RAG & Agentic AI HR Assistant")

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

# Include HR Candidate Matcher endpoints (prefixed with /hr)
app.include_router(hr_router, prefix="/hr", tags=["hr"])

# Include Agentic AI endpoints (prefixed with /agent)
app.include_router(agent_router, prefix="/agent", tags=["agent"])

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
    try:
        initialize_db()
        initialize_hr_db()
        logger.info("Databases initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize databases: {e}")
    try:
        rebuild_retrievers()
    except Exception as e:
        logger.error(f"Failed to build initial retrievers during startup: {e}")
