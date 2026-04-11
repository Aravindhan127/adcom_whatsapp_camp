import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("--- Testing List Templates ---")
    r = requests.get(f"{BASE_URL}/templates/")
    print(f"Status: {r.status_code}, Response: {r.text}")

    print("\n--- Testing Sync Templates ---")
    r = requests.post(f"{BASE_URL}/templates/sync")
    print(f"Status: {r.status_code}, Response: {r.text}")

    print("\n--- Testing Create Template (with variables) ---")
    unique_id = int(time.time())
    payload = {
        "name": f"test_tpl_{unique_id}",
        "category": "UTILITY",
        "language": "en_US",
        "components": [
            {
                "type": "BODY",
                "text": "Hello {{1}}, your order {{2}} has been processed. Team {{3}}"
            }
        ],
        "submit_to_meta": True
    }
    r = requests.post(f"{BASE_URL}/templates/", json=payload)
    print(f"Status: {r.status_code}, Response: {r.text}")

    print("\n--- Testing Health Check ---")
    r = requests.get(f"{BASE_URL}/api/health/db")
    print(f"Status: {r.status_code}, Response: {r.text}")

if __name__ == "__main__":
    test_api()
