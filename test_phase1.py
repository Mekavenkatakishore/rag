import requests
import os

BASE_URL = "http://localhost:8002"

def test_pipeline():
    print("Step 1: Checking if server is running...")
    try:
        r = requests.get(BASE_URL)
        print("Server status response:", r.json())
    except Exception as e:
        print("Error: FastAPI server is not running on port 8002. Start it first using:")
        print("python -m uvicorn server:app --reload --port 8002")
        return

    print("\nStep 2: Creating a temporary test file...")
    test_file_path = "test_doc.txt"
    with open(test_file_path, "w", encoding="utf-8") as f:
        f.write(
            "Company XYZ parental leave policy details:\n"
            "Employees are eligible for up to 12 weeks of paid parental leave after 1 year of employment.\n"
            "Unused vacation days cannot be carried over to the next year, according to policy HR-2026."
        )
    print(f"Created {test_file_path}")

    try:
        print(f"\nStep 3: Uploading {test_file_path} to FastAPI /upload...")
        with open(test_file_path, "rb") as f:
            files = {"file": (test_file_path, f, "text/plain")}
            response = requests.post(f"{BASE_URL}/upload", files=files)
        
        print("Upload Response Status Code:", response.status_code)
        print("Upload Response Content:", response.json())
        
        print("\nStep 4: Fetching index status from /status...")
        status_resp = requests.get(f"{BASE_URL}/status")
        print("Status Response:", status_resp.json())
        
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            print("\nCleaned up local test file.")

if __name__ == "__main__":
    test_pipeline()
