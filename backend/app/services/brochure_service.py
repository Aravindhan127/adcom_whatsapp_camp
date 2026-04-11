from sqlalchemy.orm import Session
import os
import requests

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")

# Mapping of brochure titles to their Meta Media IDs
BROCHURE_MAPPING = {
    "Digital Transformation": {
        "media_id": "790241857471603",
        "filename": "Digital_Transformation_Brochure.pdf",
        "caption": "Here is the brochure for Digital Transformation services."
    },
    "Finance & Audit": {
        "media_id": "5062790713947298",
        "filename": "Audit_Process_Finance_Compliance.pdf",
        "caption": "Attached is our Finance and Audit services brochure."
    }
}

def handle_brochure_request(db: Session, wa_id: str, button_text: str) -> bool:
    """
    Check if the user request is for a brochure and send it.
    """
    if button_text in BROCHURE_MAPPING:
        brochure = BROCHURE_MAPPING[button_text]
        url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "document",
            "document": {
                "id": brochure["media_id"],
                "filename": brochure["filename"],
                "caption": brochure["caption"]
            }
        }
        
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        return r.status_code == 200
        
    return False
