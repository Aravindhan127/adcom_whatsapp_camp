import requests
import logging
import json
import time
from app.core.config import settings
import re
import os
import mimetypes

logger = logging.getLogger("adcom-api")
logger.info("DEBUG: Meta API module reloaded with OS and MIMETYPES imports.")

# MOVED: Credentials must come from OrganizationConfig at runtime.
# Global defaults removed to prevent hardcoded credential leaks.
API_VERSION = "v19.0"

# BE-FIX: Setup a global resilient session for Meta API
# This handles Error 10053 (Connection Aborted) by automatically retrying.
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

def _get_resilient_session():
    session = requests.Session()
    # Retry on 500, 502, 503, 504 and connection errors
    retries = Retry(
        total=3, 
        backoff_factor=1, 
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "OPTIONS", "DELETE"]
    )
    # Configure adapter
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

session = _get_resilient_session()

def _normalize_comp_placeholders(text: str) -> str:
    """
    Ensure placeholders are sequential {{1}}, {{2}}, etc.
    Meta's Management API is strict about sequential indexing and leading/trailing variables.
    """
    if not text: return text
    
    # First, handle sequentiality
    placeholders = re.findall(r"\{\{(\d+)\}\}", text)
    if placeholders:
        unique_placeholders = []
        for p in placeholders:
            if p not in unique_placeholders:
                unique_placeholders.append(p)
        
        mapping = {old: str(i+1) for i, old in enumerate(unique_placeholders)}
        
        # Replace in reverse order of index length
        for old, new in sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True):
            text = text.replace(f"{{{{{old}}}}}", f"{{{{TEMP_{new}}}}}")
        text = text.replace("TEMP_", "")

    # ──────────────────────────────────────────────────────────────
    # BE-FIX: Aggressive Leading/Trailing Validation (Rule 100 Error)
    # Meta rejects: '{{1}}', '{{1}} .', '. {{1}}'
    # ──────────────────────────────────────────────────────────────
    
    # 1. FIX LEADING: if starts with variable (even with spaces/punctuation)
    if re.match(r'^[^\w]*\{\{\d+\}\}', text):
        text = "Ref: " + text.lstrip()
        
    # 2. FIX TRAILING: if ends with variable (even with spaces/punctuation)
    # We remove whitespace and punctuation at the end to check if it lands on a variable
    if re.search(r'\{\{\d+\}\}[^\w]*$', text):
        # We append ' Thanks' or similar substantive text to satisfy the validator
        text = text.rstrip().rstrip('.') + ". Regards."

    logger.info(f"NORMALIZATION: Final: {text!r}")
    return text

def _normalize_buttons(buttons: list) -> list:
    """
    Normalize buttons for Meta API compliance.
    Remaps OTP types, removes unsupported button types, and strips custom fields like 'id' or 'button_id'.
    """
    normalized = []
    for btn in buttons:
        btn = btn.copy()
        btn_type = btn.get("type", "").upper()
        if btn_type:
            btn["type"] = btn_type
        # Remap legacy COPY_CODE → OTP (Meta's actual type)
        if btn_type == "COPY_CODE":
            btn["type"] = "OTP"
            btn_type = "OTP"
        # MARKETING_OPT_OUT is NOT a valid Meta type — drop it
        if btn_type == "MARKETING_OPT_OUT":
            logger.warning("Dropping unsupported button type MARKETING_OPT_OUT")
            continue
        # OTP buttons must carry otp_type field
        if btn_type == "OTP":
            btn["otp_type"] = btn.get("otp_type", "COPY_CODE")
        
        # Remove custom fields that Meta rejects
        btn.pop("id", None)
        btn.pop("button_id", None)
        
        normalized.append(btn)
    return normalized

def update_meta_template(template_id: str, components: list, category: str = None, token: str = None):
    """
    Update an existing template on Meta using its ID.
    This allows editing without deletion, bypassing the 30-day lockout.
    """
    return patch_meta_template(template_id, components, category, token=token)

def patch_meta_template(template_id: str, components: list, category: str = None, token: str = None):
    """
    Update an existing template on Meta using its ID.
    This allows editing without deletion, bypassing the 30-day lockout.
    """
    use_token = token
    if not use_token:
        raise ValueError("Meta Access Token is mandatory for template patching")
    url = f"https://graph.facebook.com/{API_VERSION}/{template_id}"
    headers = {
        "Authorization": f"Bearer {use_token}",
        "Content-Type": "application/json"
    }

    processed_components = []
    for comp in components:
        new_comp = comp.copy()
        
        # 1. Normalize Body Text / Header Text
        if "text" in new_comp:
            new_comp["text"] = _normalize_comp_placeholders(new_comp["text"])

        comp_type = new_comp.get("type", "").upper()
        if comp_type:
            new_comp["type"] = comp_type

        # 2. Fix Example Structure
        if comp_type == "BODY" and "{{" in new_comp.get("text", ""):
            if "example" not in new_comp:
                new_comp["example"] = {"body_text": [[]]}
            if "body_text" not in new_comp["example"] or not isinstance(new_comp["example"]["body_text"], list):
                new_comp["example"]["body_text"] = [[]]
            example_data = new_comp["example"]["body_text"]
            if len(example_data) > 0 and not isinstance(example_data[0], list):
                new_comp["example"]["body_text"] = [example_data]
            if len(new_comp["example"]["body_text"]) == 0:
                new_comp["example"]["body_text"] = [[]]
            
            inner_list = new_comp["example"]["body_text"][0]
            var_count = len(re.findall(r"\{\{\d+\}\}", new_comp["text"]))
            while len(inner_list) < var_count:
                inner_list.append(f"sample_{len(inner_list)+1}")
            if len(inner_list) > var_count:
                inner_list = inner_list[:var_count]
                
            new_comp["example"]["body_text"] = [inner_list]

        # 3. Handle Media Header Examples
        if comp_type == "HEADER" and new_comp.get("format", "").upper() in ["IMAGE", "VIDEO", "DOCUMENT"]:
            if "format" in new_comp:
                new_comp["format"] = new_comp["format"].upper()
            if "example" in new_comp and "header_handle" in new_comp["example"]:
                handles = new_comp["example"]["header_handle"]
                if isinstance(handles, str):
                    new_comp["example"]["header_handle"] = [handles]

        # 4. Normalize BUTTONS for Meta API compliance
        # Valid Meta types: QUICK_REPLY, URL, PHONE_NUMBER, OTP, VOICE_CALL,
        #   VIDEO_CALL, FLOW, CATALOG, MPM, POSTBACK, BOOKING_STATUS,
        #   PAYMENT_REQUEST, REQUEST_CONTACT_INFO
        if comp_type == "BUTTONS" and "buttons" in new_comp:
            new_comp["buttons"] = _normalize_buttons(new_comp["buttons"])

        # 5. Handle CAROUSEL type
        if comp_type == "CAROUSEL" and "cards" in new_comp:
            processed_cards = []
            for idx, card in enumerate(new_comp["cards"]):
                new_card = card.copy()
                if "components" in new_card:
                    card_comps = []
                    for ccomp in new_card["components"]:
                        nccomp = ccomp.copy()
                        if "text" in nccomp:
                            nccomp["text"] = _normalize_comp_placeholders(nccomp["text"])
                        
                        ccomp_type = nccomp.get("type", "").upper()
                        if ccomp_type:
                            nccomp["type"] = ccomp_type
                        # Example generation for card body
                        if ccomp_type == "BODY" and "{{" in nccomp.get("text", ""):
                            if "example" not in nccomp:
                                nccomp["example"] = {"body_text": [[]]}
                            inner_list = nccomp["example"]["body_text"][0]
                            var_count = len(re.findall(r"\{\{\d+\}\}", nccomp["text"]))
                            while len(inner_list) < var_count:
                                inner_list.append(f"sample_{len(inner_list)+1}")
                            nccomp["example"]["body_text"] = [inner_list[:var_count]]
                        
                        # Handle card media handles
                        if ccomp_type == "HEADER" and nccomp.get("format", "").upper() in ["IMAGE", "VIDEO"]:
                            if "format" in nccomp:
                                nccomp["format"] = nccomp["format"].upper()
                            if "example" in nccomp and "header_handle" in nccomp["example"]:
                                handles = nccomp["example"]["header_handle"]
                                if isinstance(handles, str):
                                    handles = [handles]
                                
                                cleaned_handles = []
                                for h in handles:
                                    h_str = str(h).strip()
                                    # BE-FIX: Split if multiple handles are concatenated with newlines/spaces
                                    sub_handles = [sh.strip() for sh in h_str.replace("\n", " ").split(" ") if sh.strip()]
                                    for sh in sub_handles:
                                        # VALIDATION: Check for direct URLs in handles
                                        if sh.startswith(("http://", "https://")):
                                            return {
                                                "error": f"Invalid Media Handle: Card {idx+1} is using a direct URL. Carousel templates must use uploaded media handles.",
                                                "status": 400
                                            }
                                        cleaned_handles.append(sh)
                                
                                # Meta expects exactly ONE handle per card in the example
                                if cleaned_handles:
                                    nccomp["example"]["header_handle"] = [cleaned_handles[0]]
                        
                        # 6. Normalize buttons INSIDE carousel cards
                        if ccomp_type == "BUTTONS" and "buttons" in nccomp:
                            nccomp["buttons"] = _normalize_buttons(nccomp["buttons"])

                        card_comps.append(nccomp)
                    new_card["components"] = card_comps
                processed_cards.append(new_card)
            new_comp["cards"] = processed_cards

        processed_components.append(new_comp)

    payload = {
        "components": processed_components
    }
    if category:
        payload["category"] = category

    logger.info(f"META API UPDATE REQUEST: {template_id} | Payload: {json.dumps(payload, ensure_ascii=False)}")
    with open("patch_debug.log", "a", encoding="utf-8") as f:
        f.write(f"\n--- {time.ctime()} ---\nID: {template_id}\nPayload: {json.dumps(payload, indent=2)}\n")

    try:
        res = session.post(url, headers=headers, json=payload, timeout=20)
        data = res.json()
        
        if res.status_code != 200:
            logger.error(f"META API UPDATE FAILURE: {template_id} | Status: {res.status_code}")
            with open("meta_debug_error.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- UPDATE ERROR ---\n{json.dumps({'timestamp': time.time(), 'status_code': res.status_code, 'id': template_id, 'response': data}, indent=2)}\n")
            
            error_data = data.get("error", {})
            error_msg = error_data.get("error_user_msg") or error_data.get("message") or "Update failed on Meta"
            return {
                "error": error_msg, 
                "code": error_data.get("code"), 
                "subcode": error_data.get("error_subcode"),
                "status": res.status_code
            }
            
        return data
    except Exception as e:
        logger.error(f"Exception in update_meta_template: {str(e)}")
        return {"error": str(e)}

def create_meta_template(name: str, category: str, language: str, components: list, token: str = None, waba_id: str = None):
    """
    Create a template on Meta. 
    Fixes: Flat body_text example for Management API and proper Header Handle usage.
    """
    use_token = token
    use_waba = waba_id
    if not use_token or not use_waba:
        raise ValueError("Meta Access Token and WABA ID are mandatory for template creation")
    url = f"https://graph.facebook.com/{API_VERSION}/{use_waba}/message_templates"
    headers = {
        "Authorization": f"Bearer {use_token}",
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

        comp_type = new_comp.get("type", "").upper()
        if comp_type:
            new_comp["type"] = comp_type

        # 2. Fix Example Structure (Management API expects a list OF lists)
        if comp_type == "BODY" and "{{" in new_comp.get("text", ""):
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
        if comp_type == "HEADER" and new_comp.get("format", "").upper() in ["IMAGE", "VIDEO", "DOCUMENT"]:
            if "format" in new_comp:
                new_comp["format"] = new_comp["format"].upper()
            if "example" in new_comp and "header_handle" in new_comp["example"]:
                # Ensure it's a list with at least one handle
                handles = new_comp["example"]["header_handle"]
                if isinstance(handles, str):
                    new_comp["example"]["header_handle"] = [handles]
            elif "example" not in new_comp:
                # Meta REQUIRES an example handle for media headers during creation
                logger.warning(f"Media header found without example handle for {name}. This will likely fail.")

        # 4. Normalize BUTTONS for Meta API compliance
        # Valid Meta types: QUICK_REPLY, URL, PHONE_NUMBER, OTP, VOICE_CALL,
        #   VIDEO_CALL, FLOW, CATALOG, MPM, POSTBACK, BOOKING_STATUS,
        #   PAYMENT_REQUEST, REQUEST_CONTACT_INFO
        if comp_type == "BUTTONS" and "buttons" in new_comp:
            new_comp["buttons"] = _normalize_buttons(new_comp["buttons"])

        # 5. Handle CAROUSEL type
        if comp_type == "CAROUSEL" and "cards" in new_comp:
            processed_cards = []
            for card in new_comp["cards"]:
                new_card = card.copy()
                if "components" in new_card:
                    card_comps = []
                    for ccomp in new_card["components"]:
                        nccomp = ccomp.copy()
                        if "text" in nccomp:
                            nccomp["text"] = _normalize_comp_placeholders(nccomp["text"])
                        
                        ccomp_type = nccomp.get("type", "").upper()
                        if ccomp_type:
                            nccomp["type"] = ccomp_type
                        # Example generation for card body
                        if ccomp_type == "BODY" and "{{" in nccomp.get("text", ""):
                            if "example" not in nccomp:
                                nccomp["example"] = {"body_text": [[]]}
                            inner_list = nccomp["example"]["body_text"][0]
                            var_count = len(re.findall(r"\{\{\d+\}\}", nccomp["text"]))
                            while len(inner_list) < var_count:
                                inner_list.append(f"sample_{len(inner_list)+1}")
                            nccomp["example"]["body_text"] = [inner_list[:var_count]]
                        
                        # Handle card media handles
                        if ccomp_type == "HEADER" and nccomp.get("format", "").upper() in ["IMAGE", "VIDEO"]:
                            if "format" in nccomp:
                                nccomp["format"] = nccomp["format"].upper()
                            if "example" in nccomp and "header_handle" in nccomp["example"]:
                                handles = nccomp["example"]["header_handle"]
                                if isinstance(handles, str):
                                    nccomp["example"]["header_handle"] = [handles]
                        
                        # Normalize buttons inside carousel cards
                        if ccomp_type == "BUTTONS" and "buttons" in nccomp:
                            nccomp["buttons"] = _normalize_buttons(nccomp["buttons"])
                        
                        card_comps.append(nccomp)
                    new_card["components"] = card_comps
                processed_cards.append(new_card)
            new_comp["cards"] = processed_cards

        processed_components.append(new_comp)

    payload = {
        "name": name,
        "category": category,
        "language": language,
        "components": processed_components
    }

    logger.info(f"META API REQUEST: {name} | Payload: {json.dumps(payload, ensure_ascii=False)}")

    try:
        res = session.post(url, headers=headers, json=payload, timeout=20)
        data = res.json()
        
        if res.status_code != 200:
            logger.error(f"META API FAILURE: {name} | Status: {res.status_code} | Trace: {data.get('error', {}).get('fbtrace_id')}")
            # Dump to error log for debugging
            with open("meta_debug_error.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- ERROR DUMP ---\n{json.dumps({'timestamp': time.time(), 'status_code': res.status_code, 'name': name, 'payload_sent': payload, 'meta_response': data}, indent=2, ensure_ascii=False)}\n")
            
            error_data = data.get("error", {})
            error_msg = error_data.get("error_user_msg") or error_data.get("message") or "Unknown Meta Error"
            return {
                "error": error_msg, 
                "code": error_data.get("code"), 
                "subcode": error_data.get("error_subcode"),
                "status": res.status_code
            }
            
        return data
    except Exception as e:
        logger.error(f"Exception in create_meta_template: {str(e)}")
        return {"error": str(e)}

def delete_meta_template(name: str, language: str = None, token: str = None, waba_id: str = None):
    """Delete a template from Meta."""
    use_token = token
    use_waba = waba_id
    if not use_token or not use_waba:
        raise ValueError("Meta Access Token and WABA ID are mandatory for template deletion")
    url = f"https://graph.facebook.com/{API_VERSION}/{use_waba}/message_templates"
    params = {"name": name}
    if language:
        params["language"] = language
        
    headers = {"Authorization": f"Bearer {use_token}"}
    
    try:
        res = session.delete(url, headers=headers, params=params, timeout=20)
        data = res.json()
        if res.status_code != 200:
            error_data = data.get("error", {})
            error_msg = error_data.get("error_user_msg") or error_data.get("message") or "Delete failed"
            return {
                "error": error_msg, 
                "code": error_data.get("code"), 
                "subcode": error_data.get("error_subcode"),
                "status": res.status_code
            }
        return data
    except Exception as e:
        return {"error": str(e)}

def get_meta_templates_status(token: str = None, waba_id: str = None):
    """Fetch all templates and their status from Meta."""
    use_token = token
    use_waba = waba_id
    if not use_token or not use_waba:
        raise ValueError("Meta Access Token and WABA ID are mandatory for template sync")
    url = f"https://graph.facebook.com/{API_VERSION}/{use_waba}/message_templates"
    headers = {"Authorization": f"Bearer {use_token}"}
    
    try:
        # Fetching basic fields + rejection_reason if available
        res = session.get(url, headers=headers, params={"fields": "name,status,category,language,components,id,rejection_reason"}, timeout=20)
        data = res.json()
        if res.status_code != 200:
            return {"error": data.get("error", {}).get("message", "Sync failed")}
        return data
    except Exception as e:
        return {"error": str(e)}

def create_resumable_upload_session(file_name: str, file_size: int, file_type: str, token: str = None, app_id: str = None):
    """Step 1: Create a session for media upload (used in template examples)."""
    if not token or not app_id:
        raise ValueError("Meta Access Token and App ID are mandatory for resumable upload")
    url = f"https://graph.facebook.com/{API_VERSION}/{app_id}/uploads"
    params = {
        "file_name": file_name,
        "file_length": file_size,
        "file_type": file_type,
        "access_token": token
    }
    
    try:
        res = session.post(url, params=params, timeout=20)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def upload_file_content(session_id: str, file_content: bytes, token: str = None):
    """Step 2: Upload the actual bytes to the session to get handle 'h'."""
    if not token:
        raise ValueError("Meta Access Token is mandatory for file upload")
    url = f"https://graph.facebook.com/{API_VERSION}/{session_id}"
    headers = {
        "Authorization": f"OAuth {token}",
        "file_offset": "0"
    }
    
    try:
        res = session.post(url, headers=headers, data=file_content, timeout=60)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def format_meta_error(res_data: dict) -> str:
    """
    Consistently format a Meta API error response for storage/display.
    Returns: "(Code:Subcode) Message [Trace: ID]"
    """
    if not isinstance(res_data, dict):
        return str(res_data)
        
    error_msg = res_data.get("error") or "Unknown Meta Error"
    code = res_data.get("code")
    subcode = res_data.get("subcode")
    trace_id = res_data.get("fbtrace_id")
    
    parts = []
    if code:
        if subcode:
            parts.append(f"{code}:{subcode}")
        else:
            parts.append(str(code))
    
    code_str = f"({', '.join(parts)}) " if parts else ""
    trace_str = f" [Trace: {trace_id}]" if trace_id else ""
    
    return f"{code_str}{error_msg}{trace_str}"

def send_template_message(to: str, template_name: str, components: list, language: str = "en_US", token: str = None, phone_id: str = None):
    """Send a template message via the Messages API."""
    use_token = token
    use_phone = phone_id
    if not use_token or not use_phone:
        raise ValueError("Meta Access Token and Phone ID are mandatory for template messages")
    url = f"https://graph.facebook.com/{API_VERSION}/{use_phone}/messages"
    headers = {
        "Authorization": f"Bearer {use_token}",
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
        logger.info(f"META_SEND_PAYLOAD: {json.dumps(payload, indent=2)}")
        res = session.post(url, headers=headers, json=payload, timeout=20)
        data = res.json()
        if res.status_code != 200:
            error_data = data.get("error", {})
            error_msg = error_data.get("message") or "Send failed"
            return {
                "error": error_msg, 
                "code": error_data.get("code"),
                "subcode": error_data.get("error_subcode"),
                "fbtrace_id": error_data.get("fbtrace_id"),
                "status": res.status_code
            }
        return data
    except Exception as e:
        logger.error(f"Exception in send_template_message: {str(e)}")
        return {"error": str(e), "code": 500}

def upload_media(file_path: str, media_type: str = "image", token: str = None, phone_id: str = None):
    """
    Step 1: Permanent upload to Meta Media API (for live chat messages).
    Returns the media 'id' needed for sending.
    """
    if not token or not phone_id:
        raise ValueError("Meta Access Token and Phone ID are mandatory for media upload")
    url = f"https://graph.facebook.com/{API_VERSION}/{phone_id}/media"
    headers = {"Authorization": f"Bearer {token}"}
    
    # BE-FIX: Dynamically determine MIME type from file extension
    # Meta is picky: claiming a PNG is a JPEG results in a 400 error.
    mime_type, _ = mimetypes.guess_type(file_path)
    
    # Fallbacks if guess_type fails or returns None
    if not mime_type:
        m_type = media_type.lower()
        if "video" in m_type:
            mime_type = "video/mp4"
        elif "audio" in m_type:
            mime_type = "audio/mpeg"
        elif "pdf" in m_type or "document" in m_type or "application" in m_type:
            mime_type = "application/pdf"
        else:
            mime_type = "image/jpeg"
    
    # Map high-level media_type to Meta's category
    meta_category = "image"
    if "video" in media_type.lower():
        meta_category = "video"
    elif "audio" in media_type.lower():
        meta_category = "audio"
    elif "document" in media_type.lower() or "pdf" in media_type.lower():
        meta_category = "document"
    
    try:
        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f, mime_type),
                "type": (None, meta_category),
                "messaging_product": (None, "whatsapp")
            }
            logger.info(f"Meta API: Uploading {meta_category} ({media_type}) to /media")
            res = session.post(url, headers=headers, files=files, timeout=60)
            return res.json()
    except Exception as e:
        return {"error": str(e)}

def send_whatsapp_message(to: str, text: str = None, media_id: str = None, media_type: str = "text", token: str = None, phone_id: str = None):
    """
    Flexible live-chat message sender supporting text, image, document, etc.
    """
    if not token or not phone_id:
        raise ValueError("Meta Access Token and Phone ID are mandatory for messages")
    url = f"https://graph.facebook.com/{API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
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
        res = session.post(url, headers=headers, json=payload, timeout=20)
        data = res.json()
        if res.status_code != 200:
            error_data = data.get("error", {})
            error_msg = error_data.get("message") or "Send failed"
            return {
                "error": error_msg, 
                "code": error_data.get("code"),
                "subcode": error_data.get("error_subcode"),
                "fbtrace_id": error_data.get("fbtrace_id"),
                "status": res.status_code
            }
        return data
    except Exception as e:
        logger.error(f"Exception in send_whatsapp_message: {str(e)}")
        return {"error": str(e), "code": 500}

def get_meta_media_url(media_id: str, token: str = None):
    """Fetch the temporary download URL for a media ID from Meta."""
    if not token:
        raise ValueError("Meta Access Token is mandatory for media lookup")
    url = f"https://graph.facebook.com/{API_VERSION}/{media_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = session.get(url, headers=headers, timeout=20)
        return res.json()
    except Exception as e:
        return {"error": str(e)}

def get_meta_media_content(download_url: str, token: str = None):
    """Fetch the actual binary content from a Meta media download URL."""
    if not token:
        raise ValueError("Meta Access Token is mandatory for media download")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = session.get(download_url, headers=headers, timeout=60)
        if res.status_code == 200:
            return res.content, res.headers.get("Content-Type", "image/jpeg")
        return None, None
    except Exception as e:
        logger.error(f"Error downloading Meta media: {str(e)}")
        return None, None

def check_phone_number_health(token: str, phone_id: str) -> dict:
    """
    Checks the status and quality rating of a phone number from Meta API.
    """
    if not token or not phone_id:
        raise ValueError("Meta Access Token and Phone ID are mandatory for status checks")
    url = f"https://graph.facebook.com/{API_VERSION}/{phone_id}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"fields": "status,quality_rating"}
    try:
        res = session.get(url, headers=headers, params=params, timeout=20)
        if res.status_code == 200:
            return res.json()
        return {"error": f"HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        logger.error(f"Error checking phone number health: {str(e)}")
        return {"error": str(e)}
