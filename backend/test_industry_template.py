import os, requests, json
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, timezone

load_dotenv()
BASE = "http://localhost:8000"
token = jwt.encode(
    {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
    os.getenv("JWT_SECRET_KEY"), algorithm="HS256"
)
headers = {"Authorization": f"Bearer {token}"}

# Test the exact payload the user is sending
payload = {
    "name": "industry_specific_case_study",
    "category": "MARKETING",
    "language": "en_US",
    "submit_to_meta": True,
    "components": [
        {"type": "HEADER", "format": "TEXT", "text": "Industry-Specific Case Study"},
        {
            "type": "BODY",
            "text": "Hi {{1}},\n\nWe've helped companies just like yours achieve remarkable results.\n\nCase Study: {{2}}\n\nKey Results:\n• {{3}} revenue increase\n• {{4}} cost reduction\n• {{5}} efficiency improvement\n\nWant similar results for your business?\n\nBook a free consultation: {{6}}\n\nBest regards,\nADCOM Consultancy Team"
        },
        {"type": "FOOTER", "text": "Reply STOP to unsubscribe"}
    ]
}

print("Submitting template to API...")
r = requests.post(f"{BASE}/templates/", headers=headers, json=payload)
print(f"Status: {r.status_code}")
print(json.dumps(r.json(), indent=2))
