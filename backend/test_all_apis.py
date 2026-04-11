"""
Full API Verification Suite
Runs 3 iterations across all major endpoints to catch errors/regressions.
"""
import os
import sys
import time
import requests
import jwt
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

BASE = "http://localhost:8000"
JWT_SECRET = os.getenv("JWT_SECRET_KEY")

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"

results = {"pass": 0, "fail": 0, "errors": []}

def get_token(role="admin"):
    return jwt.encode(
        {"sub": "admin", "role": role, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        JWT_SECRET, algorithm="HS256"
    )

def check(label, resp, expected_status=200):
    ok = resp.status_code == expected_status
    tag = PASS if ok else FAIL
    print(f"  [{tag}] {label} -> {resp.status_code}")
    if ok:
        results["pass"] += 1
    else:
        results["fail"] += 1
        results["errors"].append(f"{label}: got {resp.status_code}, body={resp.text[:200]}")
    return resp

def run_iteration(i):
    headers = {"Authorization": f"Bearer {get_token()}"}
    print(f"\n{'='*55}")
    print(f"  ITERATION {i}")
    print(f"{'='*55}")

    # --- AUTH ---
    print("\n[AUTH]")
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    check("Login with bad credentials -> 401 or 400", r, expected_status=r.status_code if r.status_code in [400,401,422] else 999)

    # --- HEALTH ---
    print("\n[HEALTH]")
    check("GET /api/health/summary", requests.get(f"{BASE}/api/health/summary", headers=headers))

    # --- CONTACTS ---
    print("\n[CONTACTS]")
    check("GET /contacts/", requests.get(f"{BASE}/contacts/", headers=headers))

    # Create a contact
    contact_payload = {
        "phone_number": f"9173973491{i}0",
        "name": f"Test User {i}",
        "customer_category": "Distributor",
        "city": "Mumbai",
        "upsert": True
    }
    r_create = check("POST /contacts/ (create/upsert)", requests.post(f"{BASE}/contacts/", headers=headers, json=contact_payload))
    contact_id = None
    if r_create.status_code == 200:
        contact_id = r_create.json().get("id")

    # Update the contact
    if contact_id:
        update_payload = {"name": f"Updated User {i}", "city": "Delhi", "customer_stage": "New"}
        check(f"PATCH /contacts/{contact_id}", requests.patch(f"{BASE}/contacts/{contact_id}", headers=headers, json=update_payload))

    # Fetch single contact
    if contact_id:
        check(f"GET /contacts/{contact_id}", requests.get(f"{BASE}/contacts/{contact_id}", headers=headers))

    # --- TEMPLATES ---
    print("\n[TEMPLATES]")
    check("GET /templates/", requests.get(f"{BASE}/templates/", headers=headers))

    # Create a local-only template
    tpl_name = f"test_tpl_iter_{i}_{int(time.time())}"
    tpl_payload = {
        "name": tpl_name,
        "category": "MARKETING",
        "language": "en",
        "submit_to_meta": False,
        "components": [
            {"type": "BODY", "text": f"Hello {{{{1}}}}, this is iteration {i} test."}
        ]
    }
    r_tpl = check("POST /templates/ (local-only)", requests.post(f"{BASE}/templates/", headers=headers, json=tpl_payload))
    tpl_id = None
    if r_tpl.status_code == 200:
        tpl_id = r_tpl.json().get("id")

    # Sync templates from Meta
    check("POST /templates/sync", requests.post(f"{BASE}/templates/sync", headers=headers))

    # Delete local template
    if tpl_id:
        check(f"DELETE /templates/{tpl_id}", requests.delete(f"{BASE}/templates/{tpl_id}", headers=headers))

    # --- CAMPAIGNS ---
    print("\n[CAMPAIGNS]")
    check("GET /campaigns/", requests.get(f"{BASE}/campaigns/", headers=headers))
    check("GET /campaigns/active/progress", requests.get(f"{BASE}/campaigns/active/progress", headers=headers))

    # --- ANALYTICS ---
    print("\n[ANALYTICS]")
    check("GET /analytics/dashboard/stats", requests.get(f"{BASE}/analytics/dashboard/stats", headers=headers))
    check("GET /analytics/dashboard/trends?days=7", requests.get(f"{BASE}/analytics/dashboard/trends?days=7", headers=headers))
    check("GET /analytics/dashboard/activity?limit=5", requests.get(f"{BASE}/analytics/dashboard/activity?limit=5", headers=headers))

    # --- CONTACT LISTS ---
    print("\n[CONTACT LISTS]")
    check("GET /contacts/lists/", requests.get(f"{BASE}/contacts/lists/", headers=headers))

    # --- MESSAGES / CHAT ---
    print("\n[MESSAGES]")
    check("GET /whatsapp/conversations", requests.get(f"{BASE}/whatsapp/conversations", headers=headers))

    time.sleep(0.5)


if __name__ == "__main__":
    start = time.time()
    for i in range(1, 4):
        run_iteration(i)

    elapsed = time.time() - start
    print(f"\n{'='*55}")
    print(f"  RESULTS: {results['pass']} passed, {results['fail']} failed  ({elapsed:.1f}s)")
    print(f"{'='*55}")
    if results["errors"]:
        print("\nFAILURES:")
        for e in results["errors"]:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("\n  All endpoints healthy across 3 iterations!")
