import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)
columns = inspector.get_columns('campaigns')
print(f"Columns for campaigns: {[c['name'] for c in columns]}")
