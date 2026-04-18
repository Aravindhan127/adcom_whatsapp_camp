"""
Migration Script: Remove unique constraint from whatsapp_messages.meta_message_id
BE-FIX BE-17: The unique constraint caused IntegrityError when the same phone number
failed with the same error code in different campaigns, crashing the entire batch.

Run this ONCE before restarting services:
    cd backend
    python migrate_remove_unique.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import sqlalchemy as sa

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env file")

engine = sa.create_engine(DATABASE_URL)

def get_unique_constraint_name(conn, table_name, column_name):
    """Find the exact constraint name from pg_constraint."""
    result = conn.execute(sa.text("""
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey)
        WHERE rel.relname = :table
          AND att.attname = :column
          AND con.contype = 'u'
    """), {"table": table_name, "column": column_name})
    row = result.fetchone()
    return row[0] if row else None

def run_migration():
    with engine.connect() as conn:
        print("Checking for unique constraint on whatsapp_messages.meta_message_id...")
        constraint_name = get_unique_constraint_name(conn, "whatsapp_messages", "meta_message_id")

        if constraint_name:
            print(f"Found constraint: '{constraint_name}'. Dropping it...")
            conn.execute(sa.text(f'ALTER TABLE whatsapp_messages DROP CONSTRAINT IF EXISTS "{constraint_name}"'))
            conn.commit()
            print(f"[OK] Constraint '{constraint_name}' dropped successfully.")
        else:
            print("[OK] No unique constraint found on meta_message_id -- already clean or never existed.")

        # Verify index still exists (we keep non-unique index for performance)
        idx_result = conn.execute(sa.text("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'whatsapp_messages'
            AND indexname LIKE '%meta_message_id%'
        """))
        indexes = [r[0] for r in idx_result.fetchall()]
        if indexes:
            print(f"[OK] Non-unique index(es) still in place: {indexes}")
        else:
            print("[WARN] No index on meta_message_id found. Consider adding one for lookup performance.")

        print("\nMigration complete.")

if __name__ == "__main__":
    run_migration()
