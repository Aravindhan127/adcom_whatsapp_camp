import uuid
from sqlalchemy.orm import Session
from app.models.rbac import Role, Permission
from app.models.agent import Agent
import logging

logger = logging.getLogger("adcom-api")

def init_rbac(db: Session):
    """
    Initialize roles and permissions in the database.
    This is called on application startup to ensure consistency.
    """
    try:
        # 1. Define Permissions
        permissions_data = [
            # Campaigns
            {"name": "Create Campaign", "slug": "campaign.create"},
            {"name": "Start Campaign", "slug": "campaign.start"},
            {"name": "Delete Campaign", "slug": "campaign.delete"},
            {"name": "View Campaigns", "slug": "campaign.view"},
            # Contacts
            {"name": "Manage Contacts", "slug": "contact.manage"},
            {"name": "Import Contacts", "slug": "contact.import"},
            {"name": "Delete Contacts", "slug": "contact.delete"},
            {"name": "View Contacts", "slug": "contact.view"},
            # Templates
            {"name": "View Templates", "slug": "template.view"},
            {"name": "Manage Templates", "slug": "template.manage"},
            {"name": "Sync Templates", "slug": "template.sync"},
            # Organizations
            {"name": "Manage Organization", "slug": "org.manage"},
            # System
            {"name": "Global Admin", "slug": "system.admin"},
        ]
        
        db_permissions = {}
        for p in permissions_data:
            perm = db.query(Permission).filter(Permission.slug == p["slug"]).first()
            if not perm:
                perm = Permission(**p)
                db.add(perm)
                db.flush()
            db_permissions[p["slug"]] = perm
        
        # 2. Define Roles
        roles_data = [
            {
                "name": "Super Admin", 
                "slug": "super_admin", 
                "can_bypass_isolation": True,
                "permissions": list(db_permissions.values()) # Everything
            },
            {
                "name": "Admin", 
                "slug": "admin", 
                "can_bypass_isolation": False,
                "permissions": [
                    db_permissions[s] for s in [
                        "campaign.create", "campaign.start", "campaign.delete", "campaign.view",
                        "contact.manage", "contact.import", "contact.delete", "contact.view",
                        "template.manage", "template.sync", "template.view", "org.manage"
                    ]
                ]
            },
            {
                "name": "Agent", 
                "slug": "agent", 
                "can_bypass_isolation": False,
                "permissions": [
                    db_permissions[s] for s in [
                        "campaign.view", "campaign.create", "campaign.start", "contact.view", "template.view", "template.manage", "template.sync"
                    ]
                ]
            },
        ]
        
        for r in roles_data:
            role = db.query(Role).filter(Role.slug == r["slug"]).first()
            permissions = r.pop("permissions")
            if not role:
                role = Role(**r)
                role.permissions = permissions
                db.add(role)
                db.flush()
                logger.info(f"Created role: {role.name}")
            else:
                # Force update permissions for existing roles
                role.permissions = permissions
                role.can_bypass_isolation = r.get("can_bypass_isolation", role.can_bypass_isolation)
                db.flush()
                logger.info(f"Updated permissions for role: {role.name}")
        
        db.commit()
        
        # 3. Migration: Assign/Fix roles based on legacy 'role' column
        # Fix superadmin mismatch first
        super_admin_role = db.query(Role).filter(Role.slug == "super_admin").first()
        if super_admin_role:
            # Force update any agent with legacy "superadmin" or "super_admin" string to the correct role object
            legacy_superadmins = db.query(Agent).filter(Agent.role.in_(["superadmin", "super_admin"])).all()
            for sa in legacy_superadmins:
                if sa.role_id != super_admin_role.id:
                    sa.role_id = super_admin_role.id
                    logger.info(f"Fixed role for Super Admin: {sa.username}")
        
        # Then migrate any remaining null role_id
        agents_to_migrate = db.query(Agent).filter(Agent.role_id == None).all()
        if agents_to_migrate:
            print(f"RBAC: Migrating {len(agents_to_migrate)} agents to new system...")
            all_roles = db.query(Role).all()
            role_map = {r.slug: r.id for r in all_roles}
            
            for agent in agents_to_migrate:
                # Normalize legacy role strings
                role_slug = (agent.role or "agent").lower().strip().replace(" ", "_")
                if role_slug == "superadmin":
                    role_slug = "super_admin"
                
                agent.role_id = role_map.get(role_slug, role_map["agent"])
                agent.role = role_slug # Update legacy column too for consistency
                print(f"RBAC: Migrated user '{agent.username}' to role '{role_slug}'")
            
            print("RBAC: Agent role migration completed.")
        else:
            print("RBAC: All users already have assigned roles.")
        
        db.commit()
            
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to initialize RBAC: {e}")
        raise e
