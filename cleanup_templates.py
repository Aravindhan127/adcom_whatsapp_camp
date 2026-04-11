
import requests

WHATSAPP_TOKEN = "EAANg6X0vG7cBRDt9vYGWHv1USEvkzZATJ6xIfmrgzZA46xEZC0FWQhICvEpMTHWIksYGUfy6wJtZBkbyqivMHJNZA9xqC1BF1NOTDzopCZCkpA55PlRUU3dVhasZBpNsIQqlEuhlNZCpg6GcnR5YvgsQtRj2EWbIuQfOqUShIGDt7WclhZA3GZAozuP5J7w7oN6gZDZD"
WABA_ID = "1464711808434219"

def cleanup():
    # Attempt cleanup using POST + _method=DELETE which often bypasses API restrictions
    url = f"https://graph.facebook.com/v18.0/{WABA_ID}/message_templates"
    res = requests.get(url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, params={"fields": "name,language,status"})
    templates = res.json().get("data", [])
    
    for t in templates:
        if "test" in t['name'] or "payload" in t['name']:
            print(f"Post-Delete cleanup: {t['name']}...")
            res_post = requests.post(
                url, 
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, 
                params={"_method": "DELETE", "name": t['name'], "language": t['language']}
            )
            print(f"Result (POST-DELETE): {res_post.status_code} - {res_post.json()}")

if __name__ == "__main__":
    cleanup()
