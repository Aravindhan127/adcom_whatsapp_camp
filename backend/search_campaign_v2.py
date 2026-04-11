import psycopg2
import uuid

dbs = ['adcom_standalone', 'grow_plus', 'grow_plus_dev', 'test', 'RBAC', 'lovelink_db', 'postgres']
target_id = 'dc1d14cb-9c27-4208-82ee-babc4ce11205'

for db_name in dbs:
    print(f"Checking database: {db_name}...")
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user='postgres',
            password='root',
            host='127.0.0.1',
            port='5432'
        )
        cur = conn.cursor()
        
        # Check campaigns table
        cur.execute("SELECT count(*) FROM pg_tables WHERE tablename = 'campaigns'")
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT id, name FROM campaigns WHERE id = %s", (target_id,))
            res = cur.fetchone()
            if res:
                print(f"!!! FOUND CAMPAIGN in {db_name}: {res[1]} ({res[0]})")
        
        # Check campaign_runs table just in case
        cur.execute("SELECT count(*) FROM pg_tables WHERE tablename = 'campaign_runs'")
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT id FROM campaign_runs WHERE id = %s", (target_id,))
            if cur.fetchone():
                print(f"!!! FOUND CAMPAIGN RUN in {db_name}: {target_id}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error connecting to {db_name}: {e}")
