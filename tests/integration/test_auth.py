"""
test_auth.py
────────────
Integration test script for JWT Authentication system using FastAPI TestClient.
Works in CI/CD without requiring an external running server.
"""

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

USERNAME = "testuser_auth"
EMAIL = "testuser@ragpro.dev"
PASSWORD = "securepass123"

def test_auth_flow():
    print("=" * 55)
    print("  RAG Pro — JWT Authentication Test Suite")
    print("=" * 55)

    print("\n[1] Testing POST /auth/register ...")
    res = client.post("/auth/register", json={
        "username": USERNAME,
        "email": EMAIL,
        "password": PASSWORD
    })
    assert res.status_code in (201, 409)
    if res.status_code == 201:
        print(f"    ✅ Registered successfully: {res.json()['message']}")
    elif res.status_code == 409:
        print(f"    ⚠️  User already exists (OK for repeated runs): {res.json()['detail']}")

    print("\n[2] Testing POST /auth/login with WRONG password ...")
    res = client.post("/auth/login", json={
        "username": USERNAME,
        "password": "wrongpassword"
    })
    assert res.status_code == 401
    print(f"    ✅ Correctly rejected: {res.json()['detail']}")

    print("\n[3] Testing POST /auth/login with CORRECT credentials ...")
    res = client.post("/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    assert res.status_code == 200
    token = res.json()["access_token"]
    print(f"    ✅ Login successful! Token issued.")

    print("\n[4] Testing GET /auth/me with valid token ...")
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == USERNAME
    print(f"    ✅ Profile fetched: username='{data['username']}', email='{data['email']}'")

if __name__ == "__main__":
    test_auth_flow()
