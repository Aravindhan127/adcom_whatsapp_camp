import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def verify():
    db = SessionLocal()
    try:
        # Check last campaign status
        res = db.execute(text("SELECT id, name, status FROM campaigns ORDER BY created_at DESC LIMIT 1")).fetchone()
        if res:
            print(f"Latest Campaign: {res[1]} ({res[0]}) - STATUS: {res[2]}")
        else:
            print("No campaigns found.")
            
        # Check if campaign_runs row exists for this campaign
        if res:
            run = db.execute(text(f"SELECT status FROM campaign_runs WHERE campaign_id = '{res[0]}' ORDER BY started_at DESC LIMIT 1")).fetchone()
            if run:
                print(f"Latest Run Status: {run[0]}")
            else:
                print("No runs found for this campaign.")
    finally:
        db.close()

if __name__ == "__main__":
    verify()
