import requests
import os
import time

BASE_URL = "http://localhost:8002"

def test_qa():
    print("Step 1: Checking server connection...")
    try:
        requests.get(BASE_URL)
    except Exception:
        print("Error: Server not running.")
        return

    print("\nStep 2: Checking document status...")
    status = requests.get(f"{BASE_URL}/status").json()
    print("Current status:", status)

if __name__ == "__main__":
    test_qa()
