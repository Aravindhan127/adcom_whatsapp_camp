from sqlalchemy import create_url
from app.core.database import SessionLocal
from app.models.agent import Agent

def check_agents():
    db = SessionLocal()
    try:
        agents = db.query(Agent).all()
        if not agents:
            print("No agents found in the database.")
        else:
            print(f"Found {len(agents)} agent(s):")
            for agent in agents:
                print(f"Username: {agent.username}, Email: {agent.email}")
    except Exception as e:
        print(f"Error checking agents: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_agents()
