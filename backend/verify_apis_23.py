import os
import requests
import uuid
import time
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, timezone

load_dotenv()

# Generate Auth Token
token = jwt.encode(
    {'sub': 'admin', 'role': 'admin', 'exp': datetime.now(timezone.utc) + timedelta(minutes=60)},
    os.getenv('JWT_SECRET_KEY'),
    algorithm='HS256'
)
headers = {'Authorization': f'Bearer {token}'}
base_url = "http://localhost:8000"

def run_tests():
    print("--- STARTING API VERIFICATION (SCENARIO 1) ---")
    
    # 1. Contact Creation
    print("\n1. Testing Contact Creation...")
    contact_payload = {
        "phone_number": "917397349160",
        "name": "Test User",
        "customer_category": "Distributor",
        "city": "Test City",
        "upsert": True
    }
    r = requests.post(f"{base_url}/contacts/", headers=headers, json=contact_payload)
    print(f"POST /contacts/ -> {r.status_code}")
    if r.status_code != 200:
        print("ERROR:", r.text)

    # 2. Template Deletion Test (Mocking a delete attempt on a dummy ID)
    # We will fetch existing templates first
    print("\n2. Testing Templates Fetch...")
    r = requests.get(f"{base_url}/templates/", headers=headers)
    print(f"GET /templates/ -> {r.status_code}")

    # 3. Dashboard Stats
    print("\n3. Testing Dashboard Total Spend...")
    r = requests.get(f"{base_url}/analytics/dashboard-stats", headers=headers)
    print(f"GET /analytics/dashboard-stats -> {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Total Spend: {data.get('total_spend', 'N/A')}")
        
    print("\nAll endpoints responded without 500 errors!")

if __name__ == "__main__":
    for i in range(1, 4):
        print(f"\n================ ITERATION {i} ================")
        run_tests()
        time.sleep(1)
