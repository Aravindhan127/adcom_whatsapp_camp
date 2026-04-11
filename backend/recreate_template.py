import os
import requests
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, timezone

load_dotenv()

token = jwt.encode(
    {'sub': 'admin', 'role': 'admin', 'exp': datetime.now(timezone.utc) + timedelta(minutes=60)},
    os.getenv('JWT_SECRET_KEY'),
    algorithm='HS256'
)
headers = {'Authorization': f'Bearer {token}'}

# Delete any existing
res = requests.get('http://localhost:8000/templates/', headers=headers)
if res.status_code == 200:
    for t in res.json():
        if t['name'].lower() == 'week1_intro_message':
            requests.delete(f"http://localhost:8000/templates/{t['id']}", headers=headers)

payload = {
    'name': 'week1_intro_msg',
    'category': 'MARKETING',
    'language': 'en',
    'submit_to_meta': True,
    'components': [
        {
            'type': 'BODY',
            'text': '👋 Hi {{1}},\nGreat connecting with you via {{2}}!\n\nADCOM Consultancy helps entrepreneurs like you accelerate growth through business process optimization & revenue strategy.\n\nOur Core Services:\n• Business Process Consulting\n• Growth Framework Implementation\n• Sales & Marketing Strategy\n\n✨ Top 3 Benefits: Higher profit margins | Streamlined operations | Sustainable growth\n\n📘 Download your free PDF: “5D Framework for Your Business Growth” → {{3}}\n\nBest regards,\nADCOM Consultancy Team'
        }
    ]
}

r = requests.post(
    'http://localhost:8000/templates/',
    headers=headers,
    json=payload
)

print(r.status_code)
print(r.text)
