from app.core.database import SessionLocal, engine, Base
from sqlalchemy import text, inspect
from app.models.settings import SystemSettings
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.contact import Contact, ContactList
from app.models.campaign import Campaign
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db-ensure")

def ensure_schema():
    db = SessionLocal()
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # 1. Create missing tables
        if 'system_settings' not in tables:
            logger.info("Creating system_settings table...")
            Base.metadata.tables['system_settings'].create(engine)
            db.commit()
        
        if 'whatsapp_messages' not in tables:
             logger.info("Creating whatsapp_messages table...")
             Base.metadata.tables['whatsapp_messages'].create(engine)
             db.commit()
             tables.append('whatsapp_messages') # Re-fetch or manually add
        
        # 2. Check for missing columns in whatsapp_messages
        msg_cols = [c['name'] for c in inspector.get_columns('whatsapp_messages')]
        required_msg_cols = [
            ('direction', 'VARCHAR(10)'),
            ('message_type', "VARCHAR(20) DEFAULT 'text'"),
            ('delivery_status', "VARCHAR(20) DEFAULT 'sent'"),
            ('status_error', 'TEXT'),
            ('template_name', 'VARCHAR(255)'),
            ('campaign_id', 'UUID'),
            ('llm_cost_usd', 'DOUBLE PRECISION DEFAULT 0.0'),
            ('llm_cost_inr', 'DOUBLE PRECISION DEFAULT 0.0'),
            ('whatsapp_cost', 'DOUBLE PRECISION DEFAULT 0.0')
        ]
        
        for col, col_type in required_msg_cols:
            if col not in msg_cols:
                logger.info(f"Adding column {col} to whatsapp_messages...")
                db.execute(text(f"ALTER TABLE whatsapp_messages ADD COLUMN {col} {col_type}"))
        
        db.commit()
        
        # 3. Ensure default settings row
        SystemSettings.get_settings(db)
        db.commit()
        
        logger.info("Database schema is up to date.")
        
    except Exception as e:
        logger.error(f"Error ensuring DB schema: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    ensure_schema()
