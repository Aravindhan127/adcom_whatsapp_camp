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

payload = {
    'name': 'week1_intro_message',
    'category': 'MARKETING',
    'language': 'en',
    'components': [
        {
            'type': 'BODY',
            'text': '👋 Hi {{1}},\nGreat connecting with you via {{2}}!\n\nADCOM Consultancy helps entrepreneurs like you accelerate growth through business process optimization & revenue strategy.\n\nOur Core Services:\n• Business Process Consulting\n• Growth Framework Implementation\n• Sales & Marketing Strategy\n\n✨ Top 3 Benefits: Higher profit margins | Streamlined operations | Sustainable growth\n\n📘 Download your free PDF: “5D Framework for Your Business Growth” → {{3}}'
        }
    ]
}

r = requests.post(
    'http://localhost:8000/templates/',
    headers={'Authorization': f'Bearer {token}'},
    json=payload
)

print(r.status_code)
print(r.text)
