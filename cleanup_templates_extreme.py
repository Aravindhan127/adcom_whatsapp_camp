
import requests

WHATSAPP_TOKEN = "EAANg6X0vG7cBRDt9vYGWHv1USEvkzZATJ6xIfmrgzZA46xEZC0FWQhICvEpMTHWIksYGUfy6wJtZBkbyqivMHJNZA9xqC1BF1NOTDzopCZCkpA55PlRUU3dVhasZBpNsIQqlEuhlNZCpg6GcnR5YvgsQtRj2EWbIuQfOqUShIGDt7WclhZA3GZAozuP5J7w7oN6gZDZD"
WABA_ID = "1464711808434219"
API_VERSION = "v19.0"

def try_delete(name, lang, tpl_id):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    
    print(f"\n--- Attempting to delete: {name} ({lang}, ID: {tpl_id}) ---")
    
    # Method 1: DELETE {waba}/message_templates?name={name}&language={lang}
    url1 = f"https://graph.facebook.com/{API_VERSION}/{WABA_ID}/message_templates"
    res1 = requests.delete(url1, headers=headers, params={"name": name, "language": lang})
    print(f"M1 (name+lang): {res1.status_code} - {res1.json()}")
    
    # Method 2: DELETE {waba}/message_templates?name={name}
    res2 = requests.delete(url1, headers=headers, params={"name": name})
    print(f"M2 (name only): {res2.status_code} - {res2.json()}")
    
    # Method 3: DELETE {id}
    url3 = f"https://graph.facebook.com/{API_VERSION}/{tpl_id}"
    res3 = requests.delete(url3, headers=headers)
    print(f"M3 (id only): {res3.status_code} - {res3.json()}")

def main():
    url = f"https://graph.facebook.com/{API_VERSION}/{WABA_ID}/message_templates"
    res = requests.get(url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, params={"fields": "name,language,status,id"})
    templates = res.json().get("data", [])
    
    for t in templates:
        if "test" in t['name'] or "payload" in t['name']:
            try_delete(t['name'], t['language'], t['id'])

if __name__ == "__main__":
    main()
