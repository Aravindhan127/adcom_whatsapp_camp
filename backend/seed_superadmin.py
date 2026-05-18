import sqlite3
import uuid
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_superadmin():
    conn = sqlite3.connect('adcom.db')
    cursor = conn.cursor()
    
    hashed_pw = pwd_context.hash("admin123")
    user_id = str(uuid.uuid4()).replace('-', '')
    role_id = "4b845667046944a9b10f168eac286a19"
    
    try:
        cursor.execute("""
            INSERT INTO agents (id, username, email, hashed_password, full_name, role, role_id, is_active, token_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, "superadmin", "superadmin@adcom.com", hashed_pw, "System Super Admin", "superadmin", role_id, 1, 1))
        conn.commit()
        print("Super Admin 'superadmin' created successfully with password 'admin123'")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_superadmin()
