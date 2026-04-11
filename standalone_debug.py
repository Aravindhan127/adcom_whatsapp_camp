
import requests

WHATSAPP_TOKEN = "EAANg6X0vG7cBRDt9vYGWHv1USEvkzZATJ6xIfmrgzZA46xEZC0FWQhICvEpMTHWIksYGUfy6wJtZBkbyqivMHJNZA9xqC1BF1NOTDzopCZCkpA55PlRUU3dVhasZBpNsIQqlEuhlNZCpg6GcnR5YvgsQtRj2EWbIuQfOqUShIGDt7WclhZA3GZAozuP5J7w7oN6gZDZD"
WABA_ID = "1464711808434219"

def debug():
    url = f"https://graph.facebook.com/v18.0/{WABA_ID}/message_templates"
    print(f"Fetching from: {url}")
    # Fetch more fields
    res = requests.get(url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, params={"fields": "name,status,id,language"})
    data = res.json()
    
    templates = data.get("data", [])
    found = False
    for t in templates:
        if "test_payload" in t['name']:
            found = True
            name = t['name']
            lang = t.get('language', 'en_US')
            print(f"Found target template: {name} (Lang: {lang}). Attempting deletion with language...")
            
            # Attempt 1: Delete by name and language
            del_res = requests.delete(url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, params={"name": name, "language": lang})
            print(f"Deletion (name+lang) Status: {del_res.status_code}")
            print(f"Deletion (name+lang) Body: {del_res.json()}")
            
            # Attempt 2: Delete by name only (should delete all languages)
            if del_res.status_code != 200:
                print(f"Attempting deletion (name only) for {name}...")
                del_res_name = requests.delete(url, headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}, params={"name": name})
                print(f"Deletion (name only) Status: {del_res_name.status_code}")
                print(f"Deletion (name only) Body: {del_res_name.json()}")
    
if __name__ == "__main__":
    debug()
