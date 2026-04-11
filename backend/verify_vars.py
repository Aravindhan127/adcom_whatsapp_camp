
import os
import sys
# Add backend to path to allow imports
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.contact import Contact
import uuid

db = SessionLocal()
try:
    print("--- TESTING VARIABLE RESOLUTION ---")
    # 1. Setup mock contact
    contact = Contact(
        phone_number="+910000000000",
        name="Antigravity Test",
        company_name="DeepMind AI",
        city="London"
    )
    
    # 2. Mock Campaign with variables mapping
    campaign = Campaign(
        name="Test Var Campaign",
        template_name="hero_welcome",
        template_params={
            "1": "contact.name",
            "2": "contact.company_name",
            "3": "Exclusive Early Access",
            "4": "contact.city"
        }
    )

    # 3. Simulation of Worker Logic
    param_keys = sorted(campaign.template_params.keys(), key=lambda x: int(x) if x.isdigit() else 999)
    body_parameters = []
    
    print(f"Extracting variables for contact: {contact.name}")
    for pk in param_keys:
        mapping = campaign.template_params[pk]
        val = ""
        
        if isinstance(mapping, str) and mapping.startswith("contact."):
            field_name = mapping.split(".")[1]
            val = getattr(contact, field_name, "N/A")
        else:
            val = mapping # Static text
            
        body_parameters.append({"type": "text", "text": str(val)})
    
    # 4. Results
    print("\nResulting Body Parameters Payload:")
    for i, p in enumerate(body_parameters):
        print(f"  {{{{{i+1}}}}}: {p['text']}")

    # Validation
    assert body_parameters[0]['text'] == "Antigravity Test"
    assert body_parameters[1]['text'] == "DeepMind AI"
    assert body_parameters[2]['text'] == "Exclusive Early Access"
    assert body_parameters[3]['text'] == "London"
    print("\nSUCCESS: All variables resolved correctly.")

except Exception as e:
    print(f"\nFAILURE: {str(e)}")
finally:
    db.close()
