# ─── Python 3.11 Slim Base Image ──────────────────────────────────────────────
FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable immediate log output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install minimal OS build tools and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (optimizes image size down from ~7GB to ~1.2GB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install application dependencies (cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application codebase
COPY . .

# Ensure persistent directories exist inside the container
RUN mkdir -p /app/data /app/uploaded_files /app/chroma_db /app/logs

# Document the port FastAPI/Uvicorn listens on
EXPOSE 8000

# Docker Healthcheck (probes the unauthenticated /status endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
  CMD curl -f http://localhost:8000/status || exit 1

# Start the application using Uvicorn
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

