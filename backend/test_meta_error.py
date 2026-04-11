import os
from dotenv import load_dotenv
import asyncio
import json

load_dotenv()
from app.services.meta_api import create_meta_template

def run():
    res = create_meta_template(
        'Week1_Intro_Message', 
        'MARKETING', 
        'en', 
        [{'type': 'BODY', 'text': '👋 Hi {{1}},\nGreat connecting with you via {{2}}!\n\nADCOM Consultancy helps entrepreneurs like you accelerate growth through business process optimization & revenue strategy.\n\nOur Core Services:\n• Business Process Consulting\n• Growth Framework Implementation\n• Sales & Marketing Strategy\n\n✨ Top 3 Benefits: Higher profit margins | Streamlined operations | Sustainable growth\n\n📘 Download your free PDF: “5D Framework for Your Business Growth” → {{3}}'}]
    )
    print(json.dumps(res, indent=2))

if __name__ == '__main__':
    run()
