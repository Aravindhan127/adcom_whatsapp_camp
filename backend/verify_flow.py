import requests
import time
import sys
import os

BASE_URL = "http://127.0.0.1:8000"

def check_health():
    print("Checking API Health...")
    try:
        r = requests.get(f"{BASE_URL}/api/health/summary", timeout=10)
        if r.status_code == 200:
            data = r.json()
            print(f"Overall Status: {data.get('overall')}")
            print(f"DB Status: {data.get('db', {}).get('status')}")
            print(f"Redis Status: {data.get('redis', {}).get('status')}")
            return data.get('overall') == 'healthy'
        else:
            print(f"Health check failed with status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Error connecting to API: {e}")
    return False

def check_dashboard_stats():
    print("\nChecking Dashboard Stats Spend...")
    try:
        r = requests.get(f"{BASE_URL}/analytics/dashboard/stats", timeout=10)
        if r.status_code == 200:
            data = r.json()
            spend = data.get('costs', {}).get('total_inr')
            print(f"Total Spend (INR): {spend}")
            return spend > 0
        else:
            print(f"Stats check failed with status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"Error checking stats: {e}")
    return False

def check_root():
    print("\nChecking Root Endpoint...")
    try:
        r = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"Response: {r.json()}")
        return r.status_code == 200
    except Exception as e:
        print(f"Root check failed: {e}")
    return False

if __name__ == "__main__":
    print("=== Adcom Application Verification Tool ===\n")
    
    health_ok = check_health()
    stats_ok = check_dashboard_stats()
    root_ok = check_root()
    
    if health_ok and stats_ok and root_ok:
        print("\n[SUCCESS] Basic application flow and connectivity verified.")
        sys.exit(0)
    else:
        print("\n[FAILURE] One or more health checks failed. Check logs.")
        sys.exit(1)
