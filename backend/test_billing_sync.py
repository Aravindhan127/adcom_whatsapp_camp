import requests
import os

token = "EAANg6X0vG7cBRDt9vYGWHv1USEvkzZATJ6xIfmrgzZA46xEZC0FWQhICvEpMTHWIksYGUfy6wJtZBkbyqivMHJNZA9xqC1BF1NOTDzopCZCkpA55PlRUU3dVhasZBpNsIQqlEuhlNZCpg6GcnR5YvgsQtRj2EWbIuQfOqUShIGDt7WclhZA3GZAozuP5J7w7oN6gZDZD"
waba_id = "1464711808434219"

def test_billing_api():
    # Attempt 1: Check WABA fields for billing
    url = f"https://graph.facebook.com/v18.0/{waba_id}?fields=currency,timezone_id,message_template_namespace"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"--- Testing WABA {waba_id} ---")
    r = requests.get(url, headers=headers)
    print(f"Basic Fields: {r.status_code} - {r.text}")

    # Attempt 2: Check for 'billing_config' or 'credit_line' (if available in some versions)
    url_v2 = f"https://graph.facebook.com/v18.0/{waba_id}?fields=billing_config,line_of_credit_info"
    r2 = requests.get(url_v2, headers=headers)
    print(f"Billing Fields: {r2.status_code} - {r2.text}")

    # Attempt 3: Get Business ID and check invoices (requires business_management)
    # First get business ID from WABA
    url_biz = f"https://graph.facebook.com/v18.0/{waba_id}?fields=owner_business_info"
    r3 = requests.get(url_biz, headers=headers)
    print(f"Owner Business: {r3.status_code} - {r3.text}")
    
    if r3.status_code == 200:
        biz_id = r3.json().get("owner_business_info", {}).get("id")
        if biz_id:
            print(f"--- Testing Business {biz_id} ---")
            url_inv = f"https://graph.facebook.com/v18.0/{biz_id}/business_invoices"
            r4 = requests.get(url_inv, headers=headers)
            print(f"Invoices: {r4.status_code} - {r4.text}")

if __name__ == "__main__":
    test_billing_api()
