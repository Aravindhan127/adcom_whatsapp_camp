import uuid
from app.core.database import SessionLocal
from app.models.contact import Contact, ContactList
from app.models.campaign import Campaign

def seed_mock_contacts():
    db = SessionLocal()
    try:
        # 1. Target Campaign and its List
        campaign_id = uuid.UUID("dc1d14cb-9c27-4208-82ee-babc4ce11205")
        campaign = db.query(Campaign).get(campaign_id)
        
        if not campaign:
            print(f"Campaign {campaign_id} not found. Creating a dummy one.")
            list_id = uuid.uuid4()
            campaign = Campaign(
                id=campaign_id,
                name="sales",
                template_name="hello_world",
                contact_list_id=list_id,
                status="draft"
            )
            db.add(campaign)
            db.commit()
        
        list_id = campaign.contact_list_id
        print(f"Targeting Contact List ID: {list_id}")

        # 2. Ensure Contact List exists
        contact_list = db.query(ContactList).get(list_id)
        if not contact_list:
            print(f"Creating Contact List: {list_id}")
            contact_list = ContactList(
                id=list_id,
                name="Mock Sales List",
                description="Seeded for testing"
            )
            db.add(contact_list)
            db.commit()

        # 3. Add Mock Contacts
        mock_data = [
            {"name": "John Doe", "phone_number": "1234567890"},
            {"name": "Jane Smith", "phone_number": "0987654321"},
            {"name": "WhatsApp Test", "phone_number": "918000000001"},
            {"name": "Campaign Lead 1", "phone_number": "918000000002"},
            {"name": "Campaign Lead 2", "phone_number": "918000000003"},
        ]

        count = 0
        for entry in mock_data:
            existing = db.query(Contact).filter(Contact.phone_number == entry["phone_number"], Contact.list_id == list_id).first()
            if not existing:
                contact = Contact(
                    id=uuid.uuid4(),
                    name=entry["name"],
                    phone_number=entry["phone_number"],
                    list_id=list_id,
                    added_by=uuid.UUID("00000000-0000-0000-0000-000000000000") # Assume system/admin
                )
                db.add(contact)
                count += 1
        
        db.commit()
        print(f"Successfully seeded {count} new contacts into list {list_id}")

    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_mock_contacts()
