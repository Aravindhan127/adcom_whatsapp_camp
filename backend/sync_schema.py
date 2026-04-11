import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def sync_schema():
    db = SessionLocal()
    try:
        # Table -> [('col', 'type')]
        schemas = {
            'campaigns': [
                ('name', "VARCHAR(255)"),
                ('template_name', "VARCHAR(255)"),
                ('status', "VARCHAR(20) DEFAULT 'draft'"),
                ('contact_list_id', "UUID"),
                ('total_contacts', "INTEGER DEFAULT 0"),
                ('sent_count', "INTEGER DEFAULT 0"),
                ('delivered_count', "INTEGER DEFAULT 0"),
                ('read_count', "INTEGER DEFAULT 0"),
                ('failed_count', "INTEGER DEFAULT 0"),
                ('on_hold_count', "INTEGER DEFAULT 0"),
                ('failure_reason', "VARCHAR(255)"),
                ('total_cost_inr', "DOUBLE PRECISION DEFAULT 0.0"),
                ('total_cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
                ('scheduled_at', "TIMESTAMP WITH TIME ZONE"),
                ('completed_at', "TIMESTAMP WITH TIME ZONE")
            ],
            'campaign_runs': [
                ('on_hold_since', "TIMESTAMP WITH TIME ZONE"),
                ('failure_reason', "VARCHAR(255)"),
                ('on_hold_count', "INTEGER DEFAULT 0"),
                ('processed_count', "INTEGER DEFAULT 0"),
                ('success_count', "INTEGER DEFAULT 0"),
                ('failed_count', "INTEGER DEFAULT 0"),
                ('total_cost_inr', "DOUBLE PRECISION DEFAULT 0.0"),
                ('total_cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
                ('last_processed_offset', "INTEGER DEFAULT 0"),
                ('started_at', "TIMESTAMP WITH TIME ZONE"),
                ('completed_at', "TIMESTAMP WITH TIME ZONE"),
                ('total_contacts', "INTEGER DEFAULT 0")
            ],
            'whatsapp_messages': [
                ('campaign_id', "UUID"),
                ('whatsapp_cost', "DOUBLE PRECISION DEFAULT 0.0"),
                ('template_name', "VARCHAR(255)"),
                ('input_tokens', "INTEGER DEFAULT 0"),
                ('output_tokens', "INTEGER DEFAULT 0"),
                ('llm_cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
                ('llm_cost_inr', "DOUBLE PRECISION DEFAULT 0.0")
            ],
            'whatsapp_conversations': [
                ('billing_status', "VARCHAR(20) DEFAULT 'pending'"),
                ('cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
                ('cost_inr', "DOUBLE PRECISION DEFAULT 0.0"),
                ('rate_usd', "DOUBLE PRECISION DEFAULT 0.0"),
                ('rate_inr', "DOUBLE PRECISION DEFAULT 0.0"),
                ('exchange_rate', "DOUBLE PRECISION DEFAULT 84.0"),
                ('conversation_count', "INTEGER DEFAULT 0"),
                ('cumulative_cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
                ('cumulative_cost_inr', "DOUBLE PRECISION DEFAULT 0.0"),
                ('last_user_reply_at', "TIMESTAMP WITH TIME ZONE"),
                ('window_expires_at', "TIMESTAMP WITH TIME ZONE"),
                ('needs_agent', "BOOLEAN DEFAULT FALSE"),
                ('meta_message_id', "VARCHAR(255)")
            ]
        }

        for table, columns in schemas.items():
            print(f"Checking columns for {table}...")
            # Get existing columns
            res = db.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"))
            existing = [row[0] for row in res]
            
            for col, col_type in columns:
                if col not in existing:
                    print(f"  Adding {col} to {table}...")
                    db.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                else:
                    print(f"  Column {col} already exists in {table}")
        
        db.commit()
        print("Full Schema Sync Complete.")
    except Exception as e:
        print(f"Sync Failure: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_schema()
