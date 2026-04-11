import requests
import json
import time

def get_env():
    env = {}
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                key, val = line.strip().split("=", 1)
                env[key] = val
    return env

config = get_env()
TOKEN = config.get("WHATSAPP_TOKEN")
WABA_ID = config.get("WABA_ID")

def test_payload(name_suffix, components, api_version="v20.0", category="MARKETING"):
    url = f"https://graph.facebook.com/{api_version}/{WABA_ID}/message_templates"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    name = f"test_payload_{name_suffix}_{int(time.time())}"
    payload = {
        "name": name,
        "category": category,
        "language": "en_US",
        "components": components
    }
    
    print(f"--- Testing Payload: {name_suffix} ({category}, {api_version}) ---")
    r = requests.post(url, json=payload, headers=headers)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}\n")
    return r.status_code == 200

if __name__ == "__main__":
    # Variation 1: MARKETING double array
    test_payload("mkt_double", [
        {
            "type": "BODY",
            "text": "Hello {{1}}, test double array.",
            "example": {
                "body_text": [ ["sample_1"] ]
            }
        }
    ], category="MARKETING")
    
    # Variation 2: UTILITY double array
    test_payload("util_double", [
        {
            "type": "BODY",
            "text": "Your utility alert for {{1}}.",
            "example": {
                "body_text": [ ["Account#44"] ]
            }
        }
    ], category="UTILITY")
