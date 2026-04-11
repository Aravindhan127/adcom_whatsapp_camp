from app.core.database import SessionLocal
from sqlalchemy import text

def list_tables():
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [row[0] for row in result]
        print(f"Tables: {tables}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_tables()
