import requests
import json

WHATSAPP_TOKEN = "EAANg6X0vG7cBRDt9vYGWHv1USEvkzZATJ6xIfmrgzZA46xEZC0FWQhICvEpMTHWIksYGUfy6wJtZBkbyqivMHJNZA9xqC1BF1NOTDzopCZCkpA55PlRUU3dVhasZBpNsIQqlEuhlNZCpg6GcnR5YvgsQtRj2EWbIuQfOqUShIGDt7WclhZA3GZAozuP5J7w7oN6gZDZD"

def recover_creds():
    print("--- Attempting to recover Meta Credentials ---")
    
    # 1. Get Me info (App ID)
    me_url = "https://graph.facebook.com/v21.0/me?fields=id,name,app_id"
    res = requests.get(me_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
    print(f"Me Info: {res.status_code}")
    print(json.dumps(res.json(), indent=2))
    
    # 2. Get Debug Token info (Verify scopes and maybe better IDs)
    debug_url = f"https://graph.facebook.com/debug_token?input_token={WHATSAPP_TOKEN}"
    # This requires an App Access Token or Admin Token, usually the User Token works if it's for the same app
    res = requests.get(debug_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
    print(f"\nDebug Token: {res.status_code}")
    print(json.dumps(res.json(), indent=2))

    # 3. List WhatsApp Business Accounts
    waba_id = "1464711808434219"
    print(f"\nUsing WABA_ID: {waba_id}")
    
    # 4. List Phone Numbers for this WABA
    phones_url = f"https://graph.facebook.com/v21.0/{waba_id}/phone_numbers"
    res = requests.get(phones_url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"})
    print(f"Phone Numbers: {res.status_code}")
    print(json.dumps(res.json(), indent=2))

if __name__ == "__main__":
    recover_creds()
