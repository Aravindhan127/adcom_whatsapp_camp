import sys
import os
sys.path.append(os.getcwd())
from sqlalchemy import text
from app.core.database import SessionLocal

def check_schema():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'campaigns'"))
        columns = [row[0] for row in result]
        if 'is_deleted' in columns:
            print("SUCCESS: is_deleted column exists.")
        else:
            print("FAILURE: is_deleted column missing.")
    except Exception as e:
        print(f"ERROR: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    check_schema()
