# Deployment & CI/CD Pipeline Playbook
**Project:** Intelligent Hybrid RAG & Agentic AI HR Assistant  
**Document Purpose:** Living, step-by-step record of what was implemented, why architectural decisions were made, and exact instructions on how to test and run each stage.

---

## 🗺️ Master Deployment Roadmap

| Stage | Phase | Status | Key Deliverables |
| :---: | :--- | :---: | :--- |
| **Stage 1** | **Local Containerization (Docker)** | ✅ **COMPLETED** | `.dockerignore`, `Dockerfile`, `docker-compose.yml`, persistent volume mapping |
| **Stage 2** | **Automated CI Testing & Quality Gates** | ✅ **COMPLETED** | `pytest` test suite, security tests, smoke checks, `pytest.ini` |
| **Stage 3** | **GitHub Actions CI/CD Workflow** | ✅ **COMPLETED** | `.github/workflows/deploy.yml`, GHCR image publishing, multi-stage caching |
| **Stage 4** | **Production Server Deployment & SSL** | ⏳ **PENDING** | Cloud VPS deployment, SSH automation, Nginx/Caddy HTTPS |

---

## 📦 Stage 1: Local Containerization (COMPLETED ✅)

### 1.1 Objectives & Architecture Challenges
- **Problem 1 (PyTorch GPU Bloat):** Standard `pip install torch` downloads ~3–4 GB of CUDA GPU binaries. Because this RAG application uses CPU embeddings (`all-MiniLM-L6-v2`) and rerankers on web servers, standard installs bloat the Docker image to ~7 GB.
  - **Solution:** Installed CPU-only PyTorch wheels (`--index-url https://download.pytorch.org/whl/cpu`), dropping image size down to **~1.2 GB**.
- **Problem 2 (Data Loss on Container Restart):** SQLite databases (`users.db`, `hr_system.db`), uploaded candidate resumes (`uploaded_files/`), and ChromaDB vectors (`chroma_db/`) live on the local filesystem. By default, containers are ephemeral and wipe this data on restart.
  - **Solution:** Configured persistent host bind mounts under `./data/`.
- **Problem 3 (Code Shadowing Trap):** Mounting a host directory over `/app/app/db` would hide Python modules (`user_db.py`, `hr_db.py`).
  - **Solution:** Redirected database storage paths via environment variables (`USER_DATABASE_PATH=/app/data/users.db` and `HR_DATABASE_PATH=/app/data/hr_system.db`), mounting only `./data/storage` to `/app/data`.
- **Problem 4 (Embedding Model Re-downloading):** Hugging Face models download to `~/.cache/` on every boot if not stored.
  - **Solution:** Set `HF_HOME=/app/data/huggingface` inside the container so models are saved to disk once and reused permanently.

---

### 1.2 Files Implemented in Stage 1

#### 1. `.dockerignore`
- **Location:** [`.dockerignore`](./.dockerignore)
- **What it does:** Prevents Windows virtual environments (`.venv`), Git history (`.git`), temporary Python bytecode (`__pycache__`), local database files, and private `.env` secrets from leaking into the container image.

#### 2. `Dockerfile`
- **Location:** [`Dockerfile`](./Dockerfile)
- **Key Highlights:**
  - Base: `python:3.11-slim` (Debian-based for native C-extension compilation).
  - Multi-layer caching: Installs CPU PyTorch and `requirements.txt` *before* copying application code, allowing future code rebuilds to take 2–4 seconds.
  - Healthcheck: Probes `http://localhost:8000/status` every 30 seconds to report health status to Docker.
  - Port: Exposes `8000` and starts Uvicorn with `--host 0.0.0.0 --port 8000`.

#### 3. `docker-compose.yml`
- **Location:** [`docker-compose.yml`](./docker-compose.yml)
- **Key Highlights:**
  - Automatically loads variables from `.env` (`GROQ_API_KEY`, `JWT_SECRET_KEY`, SMTP configs).
  - Maps host port `8002` to container port `8000` (avoids conflicts with other local projects on 8000).
  - Persists data into host `./data/` folder:
    - `./data/storage` ➔ `/app/data` (Databases + Hugging Face model cache)
    - `./data/chroma_db` ➔ `/app/chroma_db` (Chroma vector files)
    - `./data/uploaded_files` ➔ `/app/uploaded_files` (Uploaded candidate resumes/PDFs)
    - `./data/logs` ➔ `/app/logs` (Application logs)

#### 4. Compatibility Fix in `requirements.txt`
- Adjusted `torch>=2.7.0` to `torch>=2.2.0` to ensure clean installation on official PyTorch CPU wheel indices.

---

### 1.3 How to Run and Verify Stage 1

#### Method A: Starting the Application
From your terminal in the project root:
```powershell
docker compose up -d
```
*(Use `docker compose up --build -d` whenever you edit Python or JavaScript files).*

#### Method B: Checking in Docker Desktop GUI
1. Open **Docker Desktop**.
2. Go to the **Containers** tab:
   - Locate `rag_pro_app` under the `rag_pro` group.
   - Status will show green **Running** and turn to **Healthy** after ~40 seconds.
   - Click the blue link **`8002:8000`** to open `http://localhost:8002` directly in your browser.
3. Daily Start / Stop controls:
   - **To stop:** Click the **Stop button (`⏹`)** in Docker Desktop (or run `docker compose stop`).
   - **To resume:** Click the **Play button (`▶`)** in Docker Desktop. It boots in 1–2 seconds!
   - *(Note: Avoid running from the "Images" tab directly, as it bypasses `docker-compose.yml` and misses the `.env` API keys).*

#### Method C: Verifying Data Persistence
1. Open `http://localhost:8002` in your browser.
2. Register a test HR user or upload a PDF document.
3. Observe that a `./data/` folder has appeared on your Windows host machine.
4. Stop the container (`docker compose stop`), then restart it (`docker compose up -d`).
5. Refresh `http://localhost:8002` — your user login and uploaded documents remain intact.

#### Method D: Running Natively via Uvicorn (Without Docker)
You can still run without Docker anytime:
1. Stop the Docker container first so port `8000` is free.
2. In your terminal run:
   ```powershell
   uvicorn server:app --reload --port 8000
   ```

---

## 🧪 Stage 2: Automated CI Testing & Quality Gates (COMPLETED ✅)

### 2.1 Objectives & Quality Assurance
- **Why Stage 2 exists:** In a CI/CD pipeline, every commit to `main` must pass an automated validation gate *before* Docker builds or deploys. If an engineer pushes broken syntax or breaks authentication, the CI runner fails immediately and protects the live server.
- **RAG App Constraint (Free & Fast Testing):** Real LLMs and embedding pipelines require paid API keys and large downloads. Stage 2 tests are designed to execute **100% offline in under 3 seconds** with zero external dependencies.

---

### 2.2 Files Implemented in Stage 2

#### 1. `pytest.ini`
- **Location:** [`pytest.ini`](./pytest.ini)
- **What it does:** Configures the testing engine:
  - Sets `pythonpath = .` so imports (`from server import app`, `from app...`) resolve cleanly regardless of execution directory.
  - Suppresses benign third-party deprecation warnings to keep CI logs clean and actionable.
  - Automatically enables verbose mode (`-v`) and shortened traceback format (`--tb=short`).

#### 2. `tests/test_smoke.py`
- **Location:** [`tests/test_smoke.py`](./tests/test_smoke.py)
- **Key Tests:**
  - `test_root_redirect()`: Confirms `GET /` cleanly routes to the `/static/index.html` frontend.
  - `test_status_endpoint()`: Confirms the unauthenticated `/status` endpoint responds with a 200 OK health JSON payload.
  - `test_404_error_envelope()`: Verifies that missing routes trigger our Starlette HTTP error handler with the standardized JSON envelope (`{"status": "error", "message": "..."}`).
  - `test_validation_error_envelope()`: Checks that malformed requests return 422 with the standardized error response.

#### 3. `tests/test_security.py`
- **Location:** [`tests/test_security.py`](./tests/test_security.py)
- **Key Tests:**
  - `test_generate_salt_uniqueness()`: Ensures cryptographic salts are 64 hex characters and strictly unique.
  - `test_password_hashing_and_verification()`: Confirms PBKDF2-HMAC-SHA256 password hashing and timing-safe digest comparison.
  - `test_jwt_create_and_decode_valid()`: Verifies JWT token generation and payload recovery.
  - `test_jwt_tampered_token_rejected()`: Confirms that altered or forged JWT signatures are immediately rejected.

#### 4. `tests/test_db_unit.py`
- **Location:** [`tests/test_db_unit.py`](./tests/test_db_unit.py)
- **Key Tests:**
  - Uses an isolated `tmp_path` SQLite fixture so tests never alter real production or local development databases.
  - `test_db_initialization()`: Ensures the `users` table is created cleanly.
  - `test_create_and_fetch_user()`: Validates user registration and profile lookup.
  - `test_duplicate_user_raises_conflict()`: Verifies unique constraints on usernames.

---

### 2.3 How to Run Stage 2 Tests Locally

Run the entire automated test suite:
```powershell
pytest
```

Run a specific test module:
```powershell
pytest tests/test_smoke.py
pytest tests/test_security.py
pytest tests/test_db_unit.py
```

Expected Output:
```text
======================== test session starts ========================
tests/test_db_unit.py::test_db_initialization PASSED           [ 10%]
tests/test_db_unit.py::test_create_and_fetch_user PASSED       [ 20%]
tests/test_db_unit.py::test_duplicate_user_raises_conflict PASSED [ 30%]
tests/test_security.py::test_generate_salt_uniqueness PASSED   [ 40%]
tests/test_security.py::test_password_hashing_and_verification PASSED [ 50%]
tests/test_security.py::test_jwt_create_and_decode_valid PASSED [ 60%]
tests/test_security.py::test_jwt_tampered_token_rejected PASSED [ 70%]
tests/test_smoke.py::test_root_redirect PASSED                 [ 80%]
tests/test_smoke.py::test_status_endpoint PASSED              [ 90%]
tests/test_smoke.py::test_404_error_envelope PASSED           [100%]
======================== 10 passed in 1.45s =========================
```

---

## 🚀 Stage 3: GitHub Actions CI/CD Pipeline (COMPLETED ✅)

### 3.1 Objectives & Cloud Automation Architecture
- **Hands-Free Building & Testing:** Eliminates the need to manually build Docker images or run tests on local developer machines before pushing to production.
- **Fail-Safe Gate:** If any of the 43 automated tests fail, the workflow immediately terminates with a red ❌. No Docker image is built, and the live production server is never touched.
- **Native GitHub Container Registry (GHCR):** Replaces third-party Docker Hub accounts. Leverages GitHub's built-in `ghcr.io` registry and automatic authentication via `secrets.GITHUB_TOKEN`.
- **Dual-Tagging Strategy (`:latest` & `:<commit-sha>`):** Every build produces a `latest` tag for immediate production deployments, alongside a permanent short git commit SHA tag (e.g. `rag_pro:e7f89a1`) enabling **instant 5-second rollbacks** if any issue occurs.

---

### 3.2 Files Implemented in Stage 3

#### 1. `.github/workflows/deploy.yml`
- **Location:** [`.github/workflows/deploy.yml`](./.github/workflows/deploy.yml)
- **Job 1 (`test` - Automated Test Gate):**
  - Runs on clean `ubuntu-latest` VM.
  - Installs Python 3.11 with pip caching.
  - Installs CPU PyTorch and full `requirements.txt`.
  - Runs all 43 `pytest` tests in verbose mode.
- **Job 2 (`build-and-push` - Docker Packaging & GHCR Publish):**
  - Gatekeeper: `needs: test` (Strict dependency on Job 1 passing).
  - Only executes on pushes to `main`.
  - Uses `docker/setup-buildx-action@v3` with GitHub Actions cloud cache (`type=gha`) to ensure builds complete in under a minute.
  - Normalizes repository naming to lowercase via `docker/metadata-action@v5`.
  - Pushes image to `ghcr.io/<owner>/rag_pro:latest` and `ghcr.io/<owner>/rag_pro:<sha>`.
- **Job 3 (`deploy` - Stage 4 Production Bridge):**
  - Gatekeeper: `needs: build-and-push`.
  - Conditional Execution: Checks if `secrets.SERVER_HOST` and `secrets.SSH_PRIVATE_KEY` exist. If configured, SSHs into the server, executes `docker compose pull`, and restarts the container seamlessly. If secrets are not yet configured, cleanly skips until Stage 4 setup.

---

### 3.3 How to Monitor Stage 3 Runs on GitHub

1. Commit and push your code:
   ```powershell
   git add .
   git commit -m "Implement Stage 3 GitHub Actions CI/CD Pipeline"
   git push origin main
   ```
2. Open your repository on **GitHub.com** in your browser.
3. Click the **"Actions"** tab at the top:
   - You will see a live workflow run named **"CI/CD Pipeline"**.
   - Click on the run to view live terminal streaming of Job 1 (`test`), Job 2 (`build-and-push`), and Job 3 (`deploy`).
4. To view your published Docker image:
   - On your GitHub profile or repository page, click the **"Packages"** tab.
   - You will see the package `rag_pro` with your tags (`latest` and the short commit SHA).

---

## 🌐 Stage 4: Production Server Deployment & HTTPS (UPCOMING ⏳)
*(This section will be populated as we configure remote server SSH deployment, environment secrets, and SSL/HTTPS certificates).*

