import requests
import logging
import json
import time
from app.core.config import settings
import re

logger = logging.getLogger("adcom-api")

TOKEN = settings.WHATSAPP_TOKEN
WABA_ID = settings.WABA_ID
PHONE_ID = settings.PHONE_NUMBER_ID
API_VERSION = "v19.0"

def _normalize_comp_placeholders(text: str) -> str:
    """
    Ensure placeholders are sequential {{1}}, {{2}}, etc.
    Meta's Management API is strict about sequential indexing.
    """
    if not text: return text
    placeholders = re.findall(r"\{\{(\d+)\}\}", text)
    if not placeholders: return text
    
    unique_placeholders = []
    for p in placeholders:
        if p not in unique_placeholders:
            unique_placeholders.append(p)
    
    mapping = {old: str(i+1) for i, old in enumerate(unique_placeholders)}
    
    result = text
    # Replace in reverse order of index length to avoid partial replacement (e.g. {{11}})
    for old, new in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
        result = result.replace(f"{{{{{old}}}}}", f"{{{{TEMP_{new}}}}}")
    
    result = result.replace("TEMP_", "")

    # Meta doesn't allow leading or trailing variables
    # We use regex to handle potential trailing whitespace or control characters
    
    # 1. FIX LEADING: if starts with variable, prepend period
    if re.match(r'^\s*\{\{\d+\}\}', result):
        result = ". " + result.lstrip()
        
    # 2. FIX TRAILING: if ends with variable, append period
    if re.search(r'\{\{\d+\}\}\s*$', result):
        result = result.rstrip() + " ."
        
    logger.info(f"NORMALIZATION: Original: {text!r} -> Final: {result!r}")
    return result

def create_meta_template(name: str, category: str, language: str, components: list):
    """
    Create a template on Meta. 
    Fixes: Flat body_text example for Management API and proper Header Handle usage.
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{WABA_ID}/message_templates"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    # Meta Management API expects a FLAT list for examples
    # and sequential variables.
    processed_components = []
    for comp in components:
        new_comp = comp.copy()
        
        # 1. Normalize Body Text / Header Text
        if "text" in new_comp:
            new_comp["text"] = _normalize_comp_placeholders(new_comp["text"])

        # 2. Fix Example Structure (Management API expects a list OF lists)
        if new_comp.get("type") == "BODY" and "{{" in new_comp.get("text", ""):
            # Auto-generate 'example' if missing entirely
            if "example" not in new_comp:
                new_comp["example"] = {"body_text": [[]]}
            
            # Ensure body_text exists and is a list
            if "body_text" not in new_comp["example"] or not isinstance(new_comp["example"]["body_text"], list):
                new_comp["example"]["body_text"] = [[]]

            # If it's a flat list, wrap it: [s1, s2] -> [[s1, s2]]
            example_data = new_comp["example"]["body_text"]
            if len(example_data) > 0 and not isinstance(example_data[0], list):
                new_comp["example"]["body_text"] = [example_data]
            
            # Now ensure we have at least one inner list
            if len(new_comp["example"]["body_text"]) == 0:
                new_comp["example"]["body_text"] = [[]]
            
            inner_list = new_comp["example"]["body_text"][0]
            
            # Ensure we have enough sample values in the first inner list
            var_count = len(re.findall(r"\{\{\d+\}\}", new_comp["text"]))
            while len(inner_list) < var_count:
                inner_list.append(f"sample_{len(inner_list)+1}")
            
            new_comp["example"]["body_text"] = [inner_list]

        # 3. Handle Media Header Examples
        if new_comp.get("type") == "HEADER" and new_comp.get("format") in ["IMAGE", "VIDEO", "DOCUMENT"]:
            if "example" in new_comp and "header_handle" in new_comp["example"]:
                # Ensure it's a list with at least one handle
                handles = new_comp["example"]["header_handle"]
                if isinstance(handles, str):
                    new_comp["example"]["header_handle"] = [handles]
            elif "example" not in new_comp:
                # Meta REQUIRES an example handle for media headers during creation
                logger.warning(f"Media header found without example handle for {name}. This will likely fail.")

        processed_components.append(new_comp)

    payload = {
        "name": name,
        "category": category,
        "language": language,
        "components": processed_components
    }

    logger.info(f"META API REQUEST: {name} | Payload: {json.dumps(payload, ensure_ascii=False)}")

    try:
        res = requests.post(url, headers=headers, json=payload)
        data = res.json()
        
        if res.status_code != 200:
            logger.error(f"META API FAILURE: {name} | Status: {res.status_code} | Trace: {data.get('error', {}).get('fbtrace_id')}")
            # Dump to error log for debugging
            with open("meta_debug_error.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- ERROR DUMP ---\n{json.dumps({'timestamp': time.time(), 'status_code': res.status_code, 'name': name, 'payload_sent': payload, 'meta_response': data}, indent=2, ensure_ascii=False)}\n")
            
            return {"error": data.get("error", {}).get("message", "Unknown Meta Error"), "code": data.get("error", {}).get("code"), "status": res.status_code}
            
        return data
    except Exception as e:
        logger.error(f"Exception in create_meta_template: {str(e)}")
        return {"error": str(e)}

def delete_meta_template(name: str, language: str = None):
    """Delete a template from Meta."""
    url = f"https://graph.facebook.com/{API_VERSION}/{WABA_ID}/message_templates"
    params = {"name": name}
    if language:
        params["language"] = language
        
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    try:
        res = requests.delete(url, headers=headers, params=params)
        data = res.json()
        if res.status_code != 200:
            return {"error": data.get("error", {}).get("message", "Delete failed"), "code": data.get("error", {}).get("code"), "status": res.status_code}
        return data
    except Exception as e:
        return {"error": str(e)}

def get_meta_templates_status():
    """Fetch all templates and their status from Meta."""
    url = f"https://graph.facebook.com/{API_VERSION}/{WABA_ID}/message_templates"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    try:
        # Fetching basic fields + rejection_reason if available
        res = requests.get(url, headers=headers, params={"fields": "name,status,category,language,components,id,rejection_reason"})
        data = res.json()
        if res.status_code != 200:
            return {"error": data.get("error", {}).get("message", "Sync failed")}
        return data
    except Exception as e:
        return {"error": str(e)}

def create_resumable_upload_session(file_name: str, file_size: int, file_type: str):
    """Step 1: Create a session for media upload (used in template examples)."""
    url = f"https://graph.facebook.com/{API_VERSION}/{settings.META_APP_ID}/uploads"
    params = {
        "file_name": file_name,
        "file_length": file_size,
        "file_type": file_type,
        "access_token": TOKEN
    }
    
    try:
        res = requests.post(url, params=params)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def upload_file_content(session_id: str, file_content: bytes):
    """Step 2: Upload the actual bytes to the session to get handle 'h'."""
    url = f"https://graph.facebook.com/{API_VERSION}/{session_id}"
    headers = {
        "Authorization": f"OAuth {TOKEN}",
        "file_offset": "0"
    }
    
    try:
        res = requests.post(url, headers=headers, data=file_content)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def send_template_message(to: str, template_name: str, components: list, language: str = "en_US"):
    """Send a template message via the Messages API."""
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components
        }
    }

    try:
        res = requests.post(url, headers=headers, json=payload)
        data = res.json()
        if res.status_code != 200:
            return {"error": data.get("error", {}).get("message", "Send failed"), "code": data.get("error", {}).get("code")}
        return data
    except Exception as e:
        return {"error": str(e)}

def upload_media(file_path: str, media_type: str = "image"):
    """
    Step 1: Permanent upload to Meta Media API (for live chat messages).
    Returns the media 'id' needed for sending.
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_ID}/media"
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # Map media types to mime types if possible, or just use the file extension
    mime_type = "image/jpeg"
    if media_type == "document": mime_type = "application/pdf"
    elif media_type == "video": mime_type = "video/mp4"
    elif media_type == "audio": mime_type = "audio/mpeg"

    try:
        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f, mime_type),
                "type": (None, media_type),
                "messaging_product": (None, "whatsapp")
            }
            res = requests.post(url, headers=headers, files=files)
            return res.json()
    except Exception as e:
        return {"error": str(e)}

def send_whatsapp_message(to: str, text: str = None, media_id: str = None, media_type: str = "text"):
    """
    Flexible live-chat message sender supporting text, image, document, etc.
    """
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type
    }

    if media_type == "text":
        payload["text"] = {"body": text}
    else:
        # media_id might be the ID returned from upload_media
        payload[media_type] = {"id": media_id}
        if text and media_type in ["image", "video", "document"]:
             payload[media_type]["caption"] = text

    try:
        res = requests.post(url, headers=headers, json=payload)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

import os # Ensure os is imported
