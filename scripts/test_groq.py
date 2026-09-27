import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

print(f"Testing Groq API key: {api_key[:10]}...")

# 1. Fetch available models from Groq
url = "https://api.groq.com/openai/v1/models"
res = requests.get(url, headers=headers)
print("Models status code:", res.status_code)
if res.status_code == 200:
    data = res.json()
    model_ids = [m["id"] for m in data.get("data", [])]
    print("Available Groq Models:", model_ids)
else:
    print("Error fetching models:", res.text)
