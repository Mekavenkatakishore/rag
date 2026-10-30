"""
test_smoke.py
─────────────
Automated smoke tests to verify FastAPI app startup, routing, and error normalization.
These tests run in under 2 seconds and require zero external API calls.
"""

from fastapi.testclient import TestClient
from server import app

client = TestClient(app, follow_redirects=False)

def test_root_redirect():
    """Verify GET / redirects client directly to web UI."""
    response = client.get("/")
    assert response.status_code in (200, 307)
    if response.status_code == 307:
        assert response.headers["location"] == "/static/index.html"

def test_status_endpoint():
    """Verify unauthenticated /status endpoint responds with healthy JSON."""
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "indexing_active" in data or "uploaded_files" in data or "total_chunks" in data

def test_404_error_envelope():
    """Verify non-existent paths return standardized error envelope."""
    response = client.get("/api/v1/non_existent_path")
    assert response.status_code == 404
    data = response.json()
    assert data.get("status") == "error"
    assert "message" in data

def test_validation_error_envelope():
    """Verify malformed requests return 422 with standardized error envelope."""
    response = client.post("/auth/login", json={"bad_field": 123})
    assert response.status_code == 422
    data = response.json()
    assert data.get("status") == "error"
    assert "detail" in data

