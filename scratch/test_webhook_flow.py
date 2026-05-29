import sys
import os
from unittest.mock import patch

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))

from fastapi.testclient import TestClient
from main import app
from app.core.database import SessionLocal
from app.models.organization import Organization, OrganizationConfig
from app.models.contact import Contact
from app.models.interactive_flow import InteractiveFlow
from app.models.whatsapp_chat_model import WhatsAppMessage

client = TestClient(app)

def test_interactive_flow_webhook():
    db = SessionLocal()
    try:
        print("\n--- STARTING WEBHOOK INTERACTIVE FLOW TEST ---")
        
        # 1. Setup Test Organization and Config
        org = db.query(Organization).filter(Organization.name == "Test Flow Org").first()
        if not org:
            org = Organization(name="Test Flow Org")
            db.add(org)
            db.commit()
            db.refresh(org)
        print(f"Using Organization: {org.name} ({org.id})")
        
        org_config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == org.id).first()
        if not org_config:
            org_config = OrganizationConfig(
                organization_id=org.id,
                phone_number_id="1234567890",
                access_token="fake_token_for_flow_test",
                whatsapp_business_id="fake_waba_id"
            )
            db.add(org_config)
            db.commit()
            db.refresh(org_config)
        print(f"Using Org Config: Phone Number ID={org_config.phone_number_id}")

        # 2. Setup Test Contact
        test_phone = "919999999999"
        contact = db.query(Contact).filter(Contact.phone_number == test_phone, Contact.organization_id == org.id).first()
        if not contact:
            contact = Contact(
                phone_number=test_phone,
                name="Flow Tester",
                organization_id=org.id,
                status="valid"
            )
            db.add(contact)
            db.commit()
            db.refresh(contact)
        print(f"Using Contact: {contact.name} ({contact.phone_number})")

        # 3. Setup Test Interactive Flow (Text Response)
        trigger = "TEST_TRIGGER_TEXT"
        flow = db.query(InteractiveFlow).filter(InteractiveFlow.trigger_keyword == trigger, InteractiveFlow.organization_id == org.id).first()
        if flow:
            db.delete(flow)
            db.commit()
            
        flow = InteractiveFlow(
            name="Test Text Flow",
            trigger_keyword=trigger,
            response_type="text",
            response_text="Hello {{contact.name}}, your flow trigger worked! Phone: {{contact.phone}}",
            organization_id=org.id,
            is_active=True
        )
        db.add(flow)
        db.commit()
        db.refresh(flow)
        print(f"Created Interactive Flow Rule: Trigger={flow.trigger_keyword}")

        # 4. Construct Mock WhatsApp Webhook Payload
        # We simulate a button reply interactive message click
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "888888888888",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "16505553333",
                                    "phone_number_id": org_config.phone_number_id
                                },
                                "contacts": [
                                    {
                                        "profile": {
                                            "name": "Flow Tester"
                                        },
                                        "wa_id": test_phone
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": test_phone,
                                        "id": f"wamid.HBgLOT{uuid_sec()}",
                                        "timestamp": "1665094111",
                                        "type": "interactive",
                                        "interactive": {
                                            "type": "button_reply",
                                            "button_reply": {
                                                "id": trigger,
                                                "title": "Trigger Test Button"
                                            }
                                        }
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }

        # 5. Mock meta_send_msg and execute the request
        with patch("app.routes.webhook_routes.meta_send_msg") as mock_send:
            print("Sending mock webhook request...")
            response = client.post("/api/webhook", json=webhook_payload)
            print(f"Webhook response: {response.status_code} - {response.text}")
            
            # Assert route returned successfully
            assert response.status_code == 200, "Webhook request failed"
            
            # Assert the mock send was called
            assert mock_send.called, "meta_send_msg was not called"
            called_args, called_kwargs = mock_send.call_args
            print(f"meta_send_msg called with: to={called_kwargs.get('to')}, text='{called_kwargs.get('text')}'")
            
            # Assert text replacements were made correctly
            expected_text = f"Hello {contact.name}, your flow trigger worked! Phone: {contact.phone_number}"
            assert called_kwargs.get("text") == expected_text, f"Text replacement mismatch: {called_kwargs.get('text')}"
            assert called_kwargs.get("to") == test_phone
            assert called_kwargs.get("token") == org_config.access_token
            assert called_kwargs.get("phone_id") == org_config.phone_number_id

        # 6. Verify message logging in DB
        db.expire_all()
        # Find the outbound logged message
        logged_msg = db.query(WhatsAppMessage).filter(
            WhatsAppMessage.wa_id == test_phone,
            WhatsAppMessage.direction == "out"
        ).order_by(WhatsAppMessage.created_at.desc()).first()
        
        assert logged_msg is not None, "Automated response message was not logged in DB"
        print(f"Outbound message successfully logged in DB. Message: '{logged_msg.message}'")
        assert logged_msg.message == expected_text
        
        print("\n[SUCCESS] Webhook Interactive Flow matched and processed correctly!")

    except Exception as e:
        import traceback
        print(f"\n[FAILURE] Test error: {e}")
        traceback.print_exc()
        raise e
    finally:
        # Clean up database records
        print("Cleaning up test data...")
        if 'flow' in locals():
            db.delete(flow)
        if 'contact' in locals():
            db.delete(contact)
        db.commit()
        db.close()

def uuid_sec():
    import uuid
    return uuid.uuid4().hex[:10]

if __name__ == "__main__":
    test_interactive_flow_webhook()
