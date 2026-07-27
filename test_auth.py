"""
test_auth.py
────────────
End-to-end verification script for the JWT Authentication system.

Run this while the server is running on port 8002:
    python -m uvicorn server:app --reload --port 8002

Then in a separate terminal:
    python test_auth.py
"""

import requests

BASE = "http://localhost:8002"

# Test user credentials
USERNAME = "testuser_auth"
EMAIL    = "testuser@ragpro.dev"
PASSWORD = "securepass123"

print("=" * 55)
print("  RAG Pro — JWT Authentication Test Suite")
print("=" * 55)


# ─── Test 1: Register a new user ──────────────────────────────
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


# ─── Test 2: Login with wrong password ─────────────────────────
print("\n[2] Testing POST /auth/login with WRONG password ...")
res = requests.post(f"{BASE}/auth/login", json={
    "username": USERNAME,
    "password": "wrongpassword"
})
if res.status_code == 401:
    print(f"    ✅ Correctly rejected: {res.json()['detail']}")
else:
    print(f"    ❌ Expected 401, got {res.status_code}: {res.json()}")


# ─── Test 3: Login with correct credentials ────────────────────
print("\n[3] Testing POST /auth/login with CORRECT credentials ...")
res = requests.post(f"{BASE}/auth/login", json={
    "username": USERNAME,
    "password": PASSWORD
})
if res.status_code == 200:
    token = res.json()["access_token"]
    print(f"    ✅ Login successful! Token issued.")
    print(f"       Token (first 40 chars): {token[:40]}...")
else:
    print(f"    ❌ Login failed {res.status_code}: {res.json()}")
    exit(1)


# ─── Test 4: Access /auth/me with valid token ──────────────────
print("\n[4] Testing GET /auth/me with valid token ...")
res = requests.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {token}"})
if res.status_code == 200:
    data = res.json()
    print(f"    ✅ Profile fetched: username='{data['username']}', email='{data['email']}'")
else:
    print(f"    ❌ Unexpected status {res.status_code}: {res.json()}")


# ─── Test 5: Access /query WITHOUT token ───────────────────────
print("\n[5] Testing POST /query WITHOUT token (should be 401) ...")
res = requests.post(f"{BASE}/query", json={"prompt": "What is in the document?"})
if res.status_code == 401:
    print(f"    ✅ Correctly blocked: {res.json()['detail']}")
else:
    print(f"    ❌ Expected 401, got {res.status_code}: {res.json()}")


# ─── Test 6: Access /query WITH valid token ────────────────────
print("\n[6] Testing POST /query WITH valid token ...")
res = requests.post(
    f"{BASE}/query",
    headers={"Authorization": f"Bearer {token}"},
    json={"prompt": "What is in the document?", "chat_history": []}
)
if res.status_code == 200:
    data = res.json()
    print(f"    ✅ Query processed! Answer (first 100 chars):")
    print(f"       {data.get('answer', '')[:100]}...")
elif res.status_code == 400:
    print(f"    ✅ Token accepted! (No documents indexed yet — expected error: {res.json()['detail']})")
else:
    print(f"    ❌ Unexpected status {res.status_code}: {res.json()}")


# ─── Test 7: Access /status (no token required) ────────────────
print("\n[7] Testing GET /status (no token required) ...")
res = requests.get(f"{BASE}/status")
if res.status_code == 200:
    data = res.json()
    print(f"    ✅ Status accessible. Files: {data['uploaded_files']}, Active: {data['indexing_active']}")
else:
    print(f"    ❌ Unexpected status {res.status_code}")


print("\n" + "=" * 55)
print("  All tests complete!")
print("=" * 55)
