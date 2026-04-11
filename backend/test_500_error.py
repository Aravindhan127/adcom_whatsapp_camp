import os
import requests
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET_KEY")

def get_token():
    return jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        JWT_SECRET, algorithm="HS256"
    )

res = requests.post(
    "http://localhost:8000/campaigns/1df755c5-8656-4a87-9dac-d15850eba010/start",
    headers={"Authorization": f"Bearer {get_token()}"}
)

print("Status:", res.status_code)
print("Response:", res.text)
