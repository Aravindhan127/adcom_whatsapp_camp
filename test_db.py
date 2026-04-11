
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('backend/.env')
db_url = os.getenv('DATABASE_URL')

def test_db():
    print(f"Testing connection to {db_url}...")
    try:
        conn = psycopg2.connect(db_url)
        print("Successfully connected to the database.")
        conn.close()
    except Exception as e:
        print(f"Error connecting to database: {e}")

if __name__ == "__main__":
    test_db()
