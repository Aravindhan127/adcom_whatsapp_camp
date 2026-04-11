import os
from dotenv import load_dotenv
import requests
import json

load_dotenv()

WABA_ID = os.getenv("WABA_ID") or '1464711808434219'
TOKEN = os.getenv("WHATSAPP_TOKEN")

payload = {
    'name': 'week1_intro_message', 
    'category': 'MARKETING', 
    'language': 'en', 
    'components': [
        {
            'type': 'BODY', 
            'text': '👋 Hi {{1}},\nGreat connecting with you via {{2}}!\n\nADCOM Consultancy helps entrepreneurs like you accelerate growth through business process optimization & revenue strategy.\n\nOur Core Services:\n• Business Process Consulting\n• Growth Framework Implementation\n• Sales & Marketing Strategy\n\n✨ Top 3 Benefits: Higher profit margins | Streamlined operations | Sustainable growth\n\n📘 Download your free PDF: “5D Framework for Your Business Growth” → {{3}}\n\nBest regards,\nADCOM Consultancy Team',
            'example': {'body_text': [['SampleName', 'SampleSource', 'https://samplelink.com']]}
        }
    ]
}

url = f"https://graph.facebook.com/v19.0/{WABA_ID}/message_templates"
r = requests.post(url, headers={'Authorization': 'Bearer ' + TOKEN}, json=payload)
print(r.status_code)
print(json.dumps(r.json(), indent=2))
