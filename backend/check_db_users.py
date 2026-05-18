from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import os
import sys

# Add current dir to path to import app
sys.path.append(os.getcwd())

from app.models.agent import Agent
from app.models.rbac import Role

DATABASE_URL = "postgresql://postgres:root@127.0.0.1:5432/adcom_standalone"

engine = create_engine(DATABASE_URL)
with Session(engine) as session:
    users = session.query(Agent).all()
    print("--- Agents in DB ---")
    for u in users:
        role_slug = session.query(Role.slug).filter(Role.id == u.role_id).scalar()
        print(f"ID: {u.id} | User: {u.username} | Role String: {u.role} | Role Obj Slug: {role_slug} | Org: {u.organization_id}")
