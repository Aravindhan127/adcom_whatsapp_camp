"""
Test: Delete a template locally + from Meta, then Sync, confirm it does NOT come back.
"""
import os, requests, time, jwt
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()
BASE = "http://localhost:8000"
token = jwt.encode(
    {"sub": "admin", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
    os.getenv("JWT_SECRET_KEY"), algorithm="HS256"
)
headers = {"Authorization": f"Bearer {token}"}

PASS = "✅ PASS"
FAIL = "❌ FAIL"

def check(label, cond, detail=""):
    status = PASS if cond else FAIL
    print(f"  {status}  {label}" + (f"  ({detail})" if detail else ""))
    return cond

print("\n=== TEMPLATE DELETE + SYNC CYCLE TEST ===\n")

# Step 1: Create a test template and submit to Meta
tpl_name = f"delete_sync_test_{int(time.time())}"
print(f"1. Creating template '{tpl_name}' and submitting to Meta...")
r = requests.post(f"{BASE}/templates/", headers=headers, json={
    "name": tpl_name,
    "category": "MARKETING",
    "language": "en",
    "submit_to_meta": True,
    "components": [
        {"type": "BODY", "text": f"Hello {{{{1}}}}, this is a delete-sync test.\n\nBest regards,\nADCOM Team"}
    ]
})
check("Template created (200)", r.status_code == 200, f"Got {r.status_code}: {r.text[:100]}")
if r.status_code != 200:
    print("Cannot continue — template creation failed.")
    exit(1)

tpl_id = r.json()["id"]
tpl_status = r.json()["status"]
print(f"   Template ID={tpl_id}, Status={tpl_status}")

# Step 2: Delete the template
print(f"\n2. Deleting template '{tpl_name}' (should delete from Meta too)...")
r = requests.delete(f"{BASE}/templates/{tpl_id}", headers=headers)
check("Delete returned 200", r.status_code == 200, f"Got {r.status_code}: {r.text[:150]}")
print(f"   Response: {r.json()}")

# Step 3: Confirm it's gone locally
print(f"\n3. Confirming template is gone from local DB...")
r = requests.get(f"{BASE}/templates/", headers=headers)
names = [t["name"] for t in r.json()]
check("Template NOT in local list after delete", tpl_name not in names, f"Local templates: {names}")

# Step 4: Sync from Meta
print(f"\n4. Syncing from Meta (template should NOT come back)...")
r = requests.post(f"{BASE}/templates/sync", headers=headers)
check("Sync returned 200", r.status_code == 200, r.text[:100])
print(f"   Sync result: {r.json()}")

# Step 5: Confirm it's STILL gone after sync
print(f"\n5. Confirming template STILL gone after sync...")
r = requests.get(f"{BASE}/templates/", headers=headers)
names = [t["name"] for t in r.json()]
check("Template NOT re-imported by sync", tpl_name not in names)

print("\n=== TEST COMPLETE ===\n")
