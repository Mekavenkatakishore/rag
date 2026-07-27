import requests
import time

BASE_URL = "http://localhost:8002"

def test_qa():
    print("Step 1: Checking server connection...")
    try:
        requests.get(BASE_URL)
    except Exception:
        print("Error: Server not running. Start it using: python -m uvicorn server:app --reload --port 8002")
        return

    print("\nStep 2: Checking document status...")
    status = requests.get(f"{BASE_URL}/status").json()
    print("Current status:", status)

    if not status["uploaded_files"]:
        print("\nNo files found. Uploading test file first...")
        test_file_path = "test_doc.txt"
        
        # Check if test_doc.txt already exists locally or recreate it
        if not os.path.exists(test_file_path):
            with open(test_file_path, "w", encoding="utf-8") as f:
                f.write(
                    "Company XYZ parental leave policy details:\n"
                    "Employees are eligible for up to 12 weeks of paid parental leave after 1 year of employment.\n"
                    "Unused vacation days cannot be carried over to the next year, according to policy HR-2026."
                )
        
        with open(test_file_path, "rb") as f:
            requests.post(f"{BASE_URL}/upload", files={"file": (test_file_path, f, "text/plain")})
        print("Test file uploaded and indexed.")

    # List of queries to test
    queries = [
        "What is the parental leave policy?",
        "Can I carry over unused vacation days to next year?",
        "What is the policy code for carrying over vacation?"
    ]

    for i, q in enumerate(queries, 1):
        print(f"\n--- Query {i}: '{q}' ---")
        try:
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/query",
                json={"prompt": q}
            )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                print(f"Answer (Time taken: {elapsed:.2f}s):")
                print(result.get("answer"))
                print("\nCitations:")
                for citation in result.get("citations", []):
                    print(f"- Source: {citation['source']}, Page: {citation['page']}")
            else:
                print("Query Failed with status code:", response.status_code)
                print("Error Details:", response.text)
        except Exception as e:
            print("Request error:", e)

if __name__ == "__main__":
    import os
    test_qa()
