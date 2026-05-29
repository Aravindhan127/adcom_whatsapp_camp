import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))

from app.core.database import SessionLocal
from app.models.agent import Agent

db = SessionLocal()
try:
    agents = db.query(Agent).all()
    print("Found agents:")
    for a in agents:
        print(f"ID: {a.id} | Username: {a.username} | Email: {a.email}")
finally:
    db.close()
