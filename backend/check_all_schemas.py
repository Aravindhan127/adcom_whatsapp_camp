import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

for table in ['campaigns', 'campaign_runs', 'whatsapp_messages', 'whatsapp_conversations', 'whatsapp_templates']:
    try:
        columns = inspector.get_columns(table)
        print(f"Columns for {table}: {[c['name'] for c in columns]}")
    except:
        print(f"Table {table} does not exist.")
