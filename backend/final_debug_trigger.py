import json
import os
from app.core.database import SessionLocal
from app.models.organization import OrganizationConfig
from app.services.meta_api import upload_media, send_template_message

def full_debug_trigger():
    db = SessionLocal()
    try:
        config = db.query(OrganizationConfig).first()
        if not config:
            print("No organization config found!")
            return
        
        token = config.access_token
        phone_id = config.phone_number_id
        
        image_path = "test_carousel_image.png"
        if not os.path.exists(image_path):
            print(f"File not found: {image_path}")
            return
            
        # 1. Upload Media
        print(f"Uploading {image_path} to Meta...")
        upload_res = upload_media(image_path, media_type="image", token=token, phone_id=phone_id)
        print(f"Upload Result: {json.dumps(upload_res, indent=2)}")
        
        media_id = upload_res.get("id")
        if not media_id:
            print("Failed to get Media ID!")
            return
            
        # 2. Prepare Carousel Payload
        template_name = "carosuel_templete"
        to_number = "917397349160"
        
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
                                "parameters": [{"type": "image", "image": {"id": media_id}}]
                            },
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": "Card 1 Test"}]
                            }
                        ]
                    },
                    {
                        "card_index": 1,
                        "components": [
                            {
                                "type": "header",
                                "parameters": [{"type": "image", "image": {"id": media_id}}]
                            },
                            {
                                "type": "body",
                                "parameters": [{"type": "text", "text": "Card 2 Test"}]
                            }
                        ]
                    }
                ]
            }
        ]
        
        # Note: Template has 3 cards, but I'll try sending 2 first as some APIs allow partial.
        # Actually, let's send 3 to be safe as the template expects it.
        components[1]["cards"].append({
            "card_index": 2,
            "components": [
                {
                    "type": "header",
                    "parameters": [{"type": "video", "video": {"link": "https://www.w3schools.com/html/mov_bbb.mp4"}}]
                },
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": "Card 3 Video"}]
                }
            ]
        })
        
        print(f"Triggering carousel to {to_number}...")
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
    full_debug_trigger()
