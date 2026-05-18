import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sys
import os

# Add the current directory to sys.path to import app modules
sys.path.append(os.getcwd())

from app.core.config import settings
from app.models.agent import Agent
from app.models.rbac import Role

def fix_roles():
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    
    try:
        print("Starting role synchronization fix...")
        
        # 1. Get all roles
        roles = db.query(Role).all()
        role_map = {r.slug: r.id for r in roles}
        
        if "super_admin" not in role_map:
            print("ERROR: super_admin role not found in database!")
            return

        # 2. Find all agents
        agents = db.query(Agent).all()
        fixed_count = 0
        
        for agent in agents:
            # Normalization logic
            role_slug = agent.role or "agent"
            if role_slug == "superadmin":
                role_slug = "super_admin"
            
            # Get target role ID
            target_role_id = role_map.get(role_slug, role_map["agent"])
            
            if agent.role_id != target_role_id:
                print(f"Fixing role for {agent.username}: {agent.role} -> {role_slug} (ID: {target_role_id})")
                agent.role_id = target_role_id
                fixed_count += 1
        
        db.commit()
        print(f"Successfully fixed {fixed_count} agents.")
        
    except Exception as e:
        db.rollback()
        print(f"Error during fix: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_roles()
