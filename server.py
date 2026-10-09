import os
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Project Imports
from app.api.endpoints import router as api_router
from app.api.auth import auth_router
from app.api.hr_endpoints import router as hr_router
from app.api.agent_endpoints import router as agent_router
from app.services.rag_service import rebuild_retrievers
from app.db.user_db import initialize_db
from app.db.hr_db import initialize_hr_db
from app.core.exceptions import RAGProException
from app.utils.logger import logger

app = FastAPI(title="Intelligent Hybrid RAG & Agentic AI HR Assistant")

# ─── Global Exception Handlers ───────────────────────────────────────────────
# Every error path funnels through one of these so (a) it is always logged — to
# both the console and logs/rag_pro.log — with enough detail to diagnose, and
# (b) the client always gets back the same JSON envelope: {"status": "error",
# "message": "..."}. The frontend relies on this shape to reliably surface a
# visible error to the user, instead of silently failing or only logging to
# the browser console.

@app.exception_handler(RAGProException)
async def ragpro_exception_handler(request: Request, exc: RAGProException):
    """Handles our own domain exceptions (AuthenticationError, JobNotFoundError, etc.)."""
    logger.warning(f"[{request.method} {request.url.path}] {exc.__class__.__name__}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message, "error_type": exc.__class__.__name__},
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Normalizes every HTTPException (raised throughout the routers) into one JSON shape."""
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    log_fn = logger.warning if exc.status_code < 500 else logger.error
    log_fn(f"[{request.method} {request.url.path}] HTTP {exc.status_code}: {message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": message, "detail": message},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Normalizes Pydantic/FastAPI request validation errors (422s)."""
    errors = exc.errors()
    message = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors) or "Invalid request."
    logger.warning(f"[{request.method} {request.url.path}] Validation error: {message}")
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": message, "detail": errors},
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catches anything not handled above so the app never crashes silently.

    Full traceback is always logged server-side (console + logs/rag_pro.log) for
    debugging, while the client only receives a safe, generic message — internal
    error details are never leaked over the API.
    """
    logger.exception(f"[{request.method} {request.url.path}] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An unexpected server error occurred. Please try again."},
    )

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
        logger.exception(f"Failed to initialize databases: {e}")
    try:
        rebuild_retrievers()
    except Exception as e:
        logger.exception(f"Failed to build initial retrievers during startup: {e}")
