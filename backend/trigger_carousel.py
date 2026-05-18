import logging
import json
from app.core.database import SessionLocal
from app.models.organization import OrganizationConfig
from app.services.meta_api import send_template_message

# Configure logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adcom-api")

def trigger():
    db = SessionLocal()
    try:
        # Get config (using the first one available or a specific one if needed)
        # Assuming single org for standalone or just pick first
        config = db.query(OrganizationConfig).first()
        if not config:
            print("ERROR: No organization config found")
            return

        token = config.access_token
        phone_id = config.phone_number_id
        
        to_number = "7397349160"
        template_name = "carosuel_templete"
        
        # Use Meta Media IDs found in DB
        image_id = "984044507630943"
        video_id = "2439613486452210"
        
        # Updated carousel components structure
        components = [
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "carousel",
                "cards": [
                    {
                        "card_index": 0,
                        "components": [
                            {
                                "type": "header",
                                "parameters": [{"type": "image", "image": {"id": image_id}}]
                            },
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": "Card 1"}]
                            }
                        ]
                    },
                    {
                        "card_index": 1,
                        "components": [
                            {
                                "type": "header",
                                "parameters": [{"type": "image", "image": {"id": image_id}}]
                            },
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": "Card 2"}]
                            }
                        ]
                    },
                    {
                        "card_index": 2,
                        "components": [
                            {
                                "type": "header",
                                "parameters": [{"type": "video", "video": {"id": video_id}}]
                            },
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": "Card 3"}]
                            }
                        ]
                    }
                ]
            }
        ]
        
        print(f"Triggering carousel message to {to_number}...")
        res = send_template_message(
            to=to_number,
            template_name=template_name,
            components=components,
            language="en_US",
            token=token,
            phone_id=phone_id
        )
        
        print("RESULT:")
        print(json.dumps(res, indent=2))
        
    finally:
        db.close()

if __name__ == "__main__":
    trigger()
