from app.core.database import SessionLocal, Base, engine
from app.models.agent import Agent
from app.core.security import get_password_hash

def create_admin():
    db = SessionLocal()
    try:
        # Check if admin already exists
        admin = db.query(Agent).filter(Agent.username == "admin").first()
        if admin:
            print(f"Admin user already exists: {admin.username}")
        else:
            admin_user = Agent(
                username="admin",
                email="admin@adcom.com",
                hashed_password=get_password_hash("admin123"),
                full_name="System Administrator",
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print("Successfully created admin user.")
            print("Username: admin")
            print("Password: admin123")
    except Exception as e:
        print(f"Error creating admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
