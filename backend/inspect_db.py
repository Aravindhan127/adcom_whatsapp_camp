from sqlalchemy import create_engine, inspect
import os

DATABASE_URL = "postgresql://postgres:root@127.0.0.1:5432/adcom_standalone"

engine = create_engine(DATABASE_URL)
try:
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print("--- Tables in DB ---")
    for t in tables:
        print(f"- {t}")
        if t == "organization_configs":
            columns = inspector.get_columns(t)
            for c in columns:
                print(f"  * {c['name']} ({c['type']})")
except Exception as e:
    print(f"Error: {e}")
