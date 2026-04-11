from app.core.database import SessionLocal, engine
from sqlalchemy import text
import sys

def check_schema():
    db = SessionLocal()
    try:
        print("Checking whatsapp_messages table schema...")
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'whatsapp_messages'"))
        columns = [row[0] for row in result]
        print(f"Columns: {columns}")
        
        print("\nChecking system_settings table row status...")
        result_s = db.execute(text("SELECT count(*) FROM system_settings"))
        count = result_s.scalar()
        print(f"Settings count: {count}")
        
    except Exception as e:
        print(f"Error checking DB schema: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    check_schema()
