"""
test_auth.py
────────────
Integration test script for JWT Authentication system.
"""

import requests

BASE = "http://localhost:8002"

USERNAME = "testuser_auth"
EMAIL = "testuser@ragpro.dev"
PASSWORD = "securepass123"

def test_auth_flow():
    print("=" * 55)
    print("  RAG Pro — JWT Authentication Test Suite")
    print("=" * 55)

    print("\n[1] Testing POST /auth/register ...")
    res = requests.post(f"{BASE}/auth/register", json={
        "username": USERNAME,
        "email": EMAIL,
        "password": PASSWORD
    })
    if res.status_code == 201:
        print(f"    ✅ Registered successfully: {res.json()['message']}")
    elif res.status_code == 409:
        print(f"    ⚠️  User already exists (OK for repeated runs): {res.json()['detail']}")
    else:
        print(f"    ❌ Unexpected status {res.status_code}: {res.json()}")

    print("\n[2] Testing POST /auth/login with WRONG password ...")
    res = requests.post(f"{BASE}/auth/login", json={
        "username": USERNAME,
        "password": "wrongpassword"
    })
    if res.status_code == 401:
        print(f"    ✅ Correctly rejected: {res.json()['detail']}")
    else:
        print(f"    ❌ Expected 401, got {res.status_code}: {res.json()}")

    print("\n[3] Testing POST /auth/login with CORRECT credentials ...")
    res = requests.post(f"{BASE}/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    if res.status_code == 200:
        token = res.json()["access_token"]
        print(f"    ✅ Login successful! Token issued.")
    else:
        print(f"    ❌ Login failed {res.status_code}: {res.json()}")
        return

    print("\n[4] Testing GET /auth/me with valid token ...")
    res = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
    if res.status_code == 200:
        data = res.json()
        print(f"    ✅ Profile fetched: username='{data['username']}', email='{data['email']}'")
    else:
        print(f"    ❌ Unexpected status {res.status_code}: {res.json()}")

if __name__ == "__main__":
    test_auth_flow()
