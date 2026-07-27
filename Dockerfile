# 1. Base OS image: Python 3.11 lightweight Linux (slim)
FROM python:3.11-slim

# 2. Configure Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 3. Install Linux C++ build tools required by PyTorch, OpenMP, and ChromaDB
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 4. Set application working directory inside container
WORKDIR /app

# 5. Copy requirements.txt first for fast Docker layer caching
COPY requirements.txt .

# 6. Install all Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy all source code into the container
COPY . .

# 8. Create storage directories for persistent data
RUN mkdir -p uploaded_files chroma_db app/db

# 9. Expose application port 8002
EXPOSE 8002

# 10. Launch FastAPI app via Uvicorn bound to 0.0.0.0
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]
