import os
import uuid
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

CAMPAIGN_ID = "cdb52e1b-108e-4155-9995-41cac0e37629"

def check():
    with engine.connect() as conn:
        res = conn.execute(text(f"SELECT id, name, template_name, contact_list_id FROM campaigns WHERE id = '{CAMPAIGN_ID}'")).fetchone()
        if not res:
            print(f"Campaign {CAMPAIGN_ID} NOT FOUND.")
            return

        print(f"Campaign found: {res[1]} (Template: {res[2]}, List: {res[3]})")
        
        # Check template
        tpl = conn.execute(text(f"SELECT status FROM whatsapp_templates WHERE name = '{res[2]}'")).fetchone()
        if tpl:
            print(f"Template Status: {tpl[0]}")
        else:
            print(f"Template '{res[2]}' NOT FOUND in database.")

        # Check contact list
        count = conn.execute(text(f"SELECT count(*) FROM contacts WHERE list_id = '{res[3]}';")).fetchone()[0]
        print(f"Contacts in list: {count}")

if __name__ == "__main__":
    check()
