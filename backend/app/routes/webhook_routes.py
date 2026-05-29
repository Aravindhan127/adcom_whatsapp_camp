from fastapi import APIRouter, Header, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.organization import OrganizationConfig, Organization
from app.core.database import get_db, logger
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.whatsapp_conversation import WhatsAppConversation
from app.models.contact import Contact
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun
from app.services.meta_api import send_whatsapp_message as meta_send_msg, send_template_message, format_meta_error
from app.services.billing import ensure_conversation
from app.services.opt_out_service import handle_opt_out
from app.models.interactive_flow import InteractiveFlow
from app.models.template import WhatsAppTemplate
from app.services.ai_brain import chat_with_knowledge
from app.services.brochure_service import handle_brochure_request
from app.services.whatsapp_chat_service import finalize_billing_on_delivery
from app.services.audit_service import log_action
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import json
import logging

logger = logging.getLogger("adcom-api")

router = APIRouter(prefix="/webhook", tags=["webhook"])

def verify_webhook_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """Verify Meta webhook signature using HMAC-SHA256."""
    if not signature or not app_secret:
        return False
    expected = hmac.new(
        app_secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

@router.get("/")
@router.get("")
def verify_webhook(request: Request):
    # Meta webhook verification
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.MY_VERIFY_TOKEN:
        from fastapi.responses import Response
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/")
@router.post("")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256")
):
    # SECURITY: Read raw body first for signature verification
    body = await request.body()

    # Verify webhook signature if app secret is configured
    if hasattr(settings, 'META_APP_SECRET') and settings.META_APP_SECRET:
        if not verify_webhook_signature(body, x_hub_signature_256, settings.META_APP_SECRET):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
        logger.info(f"Webhook Received: {json.dumps(payload)[:500]}...") # Log start of payload
        
        # BE-FIX: Raw Trace Logger (Rule: Diagnostic Visibility)
        # This writes the FULL payload to a file for forensic analysis of delivery failures.
        try:
            with open("webhook_debug.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now().isoformat()} ---\n")
                f.write(json.dumps(payload, indent=2))
                f.write("\n")
        except Exception as log_err:
            logger.error(f"Failed to write webhook_debug.log: {log_err}")
            
    except json.JSONDecodeError:
        logger.error(f"Webhook JSON Error: {body[:200]}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if "entry" in payload:
        for entry in payload["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                
                # 1. Handle Messages (Rule 4)
                if "messages" in value:
                    for msg in value["messages"]:
                        wa_id = msg["from"]
                        meta_id = msg["id"]
                        msg_type = msg.get("type", "text")
                        
                        # ✅ IDEMPOTENCY CHECK: Skip if this exact message was already processed
                        # This prevents duplicate responses when Meta retries webhook delivery
                        already_processed = db.query(WhatsAppMessage).filter(
                            WhatsAppMessage.meta_message_id == meta_id
                        ).first()
                        if already_processed:
                            logger.info(f"Webhook: Skipping duplicate message (meta_id already processed): {meta_id[:40]}")
                            continue
                        
                        metadata = value.get("metadata", {})
                        recipient_phone_id = metadata.get("phone_number_id")
                        
                        # Find Organization by phone_number_id
                        org_config = db.query(OrganizationConfig).filter(OrganizationConfig.phone_number_id == recipient_phone_id).first()
                        org_id = org_config.organization_id if org_config else None
                        
                        # Find Organization Config for credentials
                        if org_config and org_config.access_token:
                            token = org_config.access_token
                            phone_id = org_config.phone_number_id
                        else:
                            from app.models.settings import SystemSettings
                            sys_settings = SystemSettings.get_settings(db)
                            token = sys_settings.whatsapp_token
                            phone_id = sys_settings.phone_number_id
                        
                        # Extract content based on type
                        text = ""
                        button_payload = None
                        is_button_click = False
                        
                        if msg_type == "text":
                            text = msg.get("text", {}).get("body", "")
                        elif msg_type == "interactive":
                            interactive = msg.get("interactive", {})
                            if interactive.get("type") == "button_reply":
                                button_reply = interactive.get("button_reply", {})
                                text = button_reply.get("title", "")
                                button_payload = button_reply.get("id")
                                is_button_click = True
                        elif msg_type == "button":
                            button = msg.get("button", {})
                            text = button.get("text", "")
                            button_payload = button.get("payload")
                            is_button_click = True
                            
                        meta_ts = int(msg.get("timestamp", datetime.now(timezone.utc).timestamp()))
                        started_at = datetime.fromtimestamp(meta_ts, tz=timezone.utc)
                        
                        # 1. Start/Update conversation (Scoped to Org)
                        conv_data = ensure_conversation(db, wa_id, "service", organization_id=org_id, meta_message_id=meta_id, started_at=started_at)
                        conv = conv_data["conversation"]
                        
                        
                        # 2. Check for opt-out (STOP/UNSUBSCRIBE)
                        if handle_opt_out(db, wa_id, text):
                            # Optional: Send a confirmation message "You have been unsubscribed."
                            if token and phone_id:
                                meta_send_msg(to=wa_id, text="You have been unsubscribed from our updates. Type START to subscribe again.", token=token, phone_id=phone_id)
                            logger.info(f"Contact {wa_id} opted out.")
                            continue # Process next message/status in SAME payload
                        
                        # 3. Check for opt-in (START)
                        if text.upper().strip() == "START":
                            contact_query = db.query(Contact).filter(Contact.phone_number == wa_id)
                            if org_id:
                                contact_query = contact_query.filter(Contact.organization_id == org_id)
                            contact = contact_query.first()
                            if contact:
                                contact.status = "valid"
                                db.commit()
                                if token and phone_id:
                                    meta_send_msg(to=wa_id, text="Welcome back! You have been re-subscribed.", token=token, phone_id=phone_id)
                                logger.info(f"Contact {wa_id} opted in.")
                                continue # Process next message/status in SAME payload
                            
                        # 4. Handle Automated Brochure Request (Rule: Enterprise Feature)
                        if handle_brochure_request(db, wa_id, text):
                            logger.info(f"Brochure request handled for {wa_id}")
                            # We don't continue here because we still want to save the message and notify UI
                            pass
 
                        # Flag as needs agent and activate customer-initiated 24h window
                        conv.needs_agent = True
                        conv.is_active = True
                        conv.billing_status = "charged"
                        conv.last_user_reply_at = started_at
                        conv.window_expires_at = started_at + timedelta(hours=24)
                        
                        # Save incoming message
                        new_msg = WhatsAppMessage(
                            wa_id=wa_id, direction="in", message=text,
                            meta_message_id=meta_id, conversation_id=conv.id
                        )
                        db.add(new_msg)
                        db.commit()
                        
                        # Look up contact name strictly from the Contact Table (Scoped to Org)
                        # Smart Match: Use last 10 digits to resolve country code mismatches
                        last_10 = wa_id[-10:] if len(wa_id) >= 10 else wa_id
                        contact_query = db.query(Contact).filter(Contact.phone_number.ilike(f"%{last_10}"))
                        if org_id:
                            contact_query = contact_query.filter(Contact.organization_id == org_id)
                        contact = contact_query.first()
                        contact_name = contact.name if (contact and contact.name) else None
 
                        from app.core.websocket_manager import manager
                        await manager.notify_new_message(wa_id, {
                            "id": str(new_msg.id),
                            "text": text,
                            "timestamp": new_msg.created_at.isoformat() if new_msg.created_at else datetime.now().isoformat(),
                            "sender": "user",
                            "contactName": contact_name,
                            "window_expires_at": conv.window_expires_at.isoformat() if conv.window_expires_at else None,
                            "is_active": True,
                            "is_button": is_button_click
                        })
 
                        # 5. Check for Interactive Flow matching
                        matched_flow = None
                        if org_id:
                            flow_query = db.query(InteractiveFlow).filter(
                                InteractiveFlow.organization_id == org_id,
                                InteractiveFlow.is_active == True
                            )
                            candidates = flow_query.all()
                            for flow in candidates:
                                flow_keyword = flow.trigger_keyword.strip().lower()
                                if button_payload and button_payload.strip().lower() == flow_keyword:
                                    matched_flow = flow
                                    break
                                if text and text.strip().lower() == flow_keyword:
                                    matched_flow = flow
                                    break

                        if matched_flow:
                            logger.info(f"Interactive Flow matched: '{matched_flow.name}' (Trigger: '{matched_flow.trigger_keyword}')")
                            flow_msg = None
                            
                            # Execute flow automated response
                            if matched_flow.response_type == "text":
                                response_text = matched_flow.response_text or ""
                                if contact:
                                    if "{{contact.name}}" in response_text.lower():
                                        response_text = response_text.replace("{{contact.name}}", contact.name or "")
                                    if "{{contact.phone}}" in response_text.lower():
                                        response_text = response_text.replace("{{contact.phone}}", contact.phone_number or "")
                                
                                response_data = None
                                if token and phone_id:
                                    response_data = meta_send_msg(to=wa_id, text=response_text, token=token, phone_id=phone_id)
                                
                                # Log response message in DB
                                flow_msg = WhatsAppMessage(
                                    wa_id=wa_id, direction="out", message=response_text,
                                    conversation_id=conv.id, message_type="text"
                                )
                                if response_data and "error" in response_data:
                                    flow_msg.delivery_status = "failed"
                                    flow_msg.status_error = format_meta_error(response_data)
                                    logger.error(f"Interactive Flow: Failed to send text response to {wa_id}: {response_data}")
                                    try:
                                        with open("meta_debug_error.log", "a", encoding="utf-8") as f:
                                            f.write(f"\n--- INTERACTIVE FLOW ERROR ---\n"
                                                    f"Timestamp: {datetime.now().isoformat()}\n"
                                                    f"To: {wa_id}\n"
                                                    f"Text: {response_text}\n"
                                                    f"Error: {json.dumps(response_data, indent=2)}\n")
                                    except Exception as log_err:
                                        logger.error(f"Failed to log meta send error: {log_err}")
                                db.add(flow_msg)
                                db.commit()
                            elif matched_flow.response_type == "template":
                                template_name = matched_flow.response_template
                                template = db.query(WhatsAppTemplate).filter(
                                    WhatsAppTemplate.name == template_name,
                                    WhatsAppTemplate.organization_id == org_id
                                ).first()
                                
                                template_lang = "en_US"
                                if template and template.language:
                                    template_lang = template.language

                                # Build template components
                                vars_dict = matched_flow.variable_values or {}
                                components = []
                                
                                # A. Header Media
                                header_val = vars_dict.get("header")
                                if header_val and isinstance(header_val, dict):
                                    media_type = header_val.get("type", "image").lower()
                                    media_url = header_val.get("url") or header_val.get("link")
                                    media_id = header_val.get("id")
                                    
                                    media_payload = {}
                                    if media_id:
                                        media_payload = {"id": media_id}
                                    elif media_url:
                                        if str(media_url).startswith(("http://", "https://")):
                                            media_payload = {"link": media_url}
                                        else:
                                            media_payload = {"id": media_url}
                                            
                                    if media_payload:
                                        components.append({
                                            "type": "header",
                                            "parameters": [{"type": media_type, media_type: media_payload}]
                                        })
                                        
                                # B. Body Parameters
                                body_params = vars_dict.get("body") or []
                                body_parameters = []
                                for param in body_params:
                                    val = str(param)
                                    if contact:
                                        if "{{contact.name}}" in val.lower():
                                            val = val.replace("{{contact.name}}", contact.name or "")
                                        elif "{{contact.phone}}" in val.lower():
                                            val = val.replace("{{contact.phone}}", contact.phone_number or "")
                                        elif val.lower().startswith("contact."):
                                            field = val.split(".", 1)[1]
                                            val = getattr(contact, field, "")
                                    
                                    # Fallback: if empty or only whitespace, use a single space " " to avoid Meta Graph API error #131008
                                    if not val or not val.strip():
                                        val = " "
                                        
                                    body_parameters.append({"type": "text", "text": val})
                                    
                                if body_parameters:
                                    components.append({
                                        "type": "body",
                                        "parameters": body_parameters
                                    })
                                    
                                # C. Buttons (Automatic phone injection for dynamic URL buttons)
                                buttons_config = vars_dict.get("buttons") or []
                                for btn in buttons_config:
                                    btn_idx = btn.get("index", 0)
                                    btn_type = btn.get("type", "url")
                                    btn_text = btn.get("text", wa_id)
                                    if contact and btn_text:
                                        if "{{contact.phone}}" in btn_text:
                                            btn_text = btn_text.replace("{{contact.phone}}", wa_id)
                                        elif "{{contact.name}}" in btn_text:
                                            btn_text = btn_text.replace("{{contact.name}}", contact.name or "")
                                            
                                    components.append({
                                        "type": "button",
                                        "sub_type": btn_type,
                                        "index": btn_idx,
                                        "parameters": [{"type": "text", "text": str(btn_text)}]
                                    })
                                    
                                # Auto-inject phone if template has dynamic URL button and not in config
                                if template:
                                    buttons_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "BUTTONS"), None)
                                    if buttons_comp:
                                        for btn_idx, btn in enumerate(buttons_comp.get("buttons", [])):
                                            if btn.get("type", "").upper() == "URL" and ("{?" in btn.get("url", "") or "{{" in btn.get("url", "")):
                                                has_existing = any(b.get("index") == btn_idx for b in buttons_config)
                                                if not has_existing:
                                                    components.append({
                                                        "type": "button",
                                                        "sub_type": "url",
                                                        "index": btn_idx,
                                                        "parameters": [{"type": "text", "text": str(wa_id)}]
                                                    })
                                            elif btn.get("type", "").upper() == "QUICK_REPLY" and btn.get("id"):
                                                has_existing = any(c.get("type") == "button" and c.get("index") == btn_idx for c in components)
                                                if not has_existing:
                                                    components.append({
                                                        "type": "button",
                                                        "sub_type": "quick_reply",
                                                        "index": btn_idx,
                                                        "parameters": [{"type": "payload", "payload": btn.get("id")}]
                                                    })
                                                    
                                response_data = None
                                if token and phone_id:
                                    response_data = send_template_message(
                                        to=wa_id,
                                        template_name=template_name,
                                        components=components,
                                        language=template_lang,
                                        token=token,
                                        phone_id=phone_id
                                    )
                                    
                                # Form message body fallback preview
                                msg_body = f"[Template: {template_name}]"
                                if template:
                                    body_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "BODY"), None)
                                    if body_comp:
                                        msg_body = body_comp.get("text", msg_body)
                                        for i, param in enumerate(body_params):
                                            val = str(param)
                                            if contact:
                                                if "{{contact.name}}" in val.lower():
                                                    val = val.replace("{{contact.name}}", contact.name or "")
                                                elif "{{contact.phone}}" in val.lower():
                                                    val = val.replace("{{contact.phone}}", contact.phone_number or "")
                                                elif val.lower().startswith("contact."):
                                                    field = val.split(".", 1)[1]
                                                    val = getattr(contact, field, "")
                                            
                                            if not val or not val.strip():
                                                val = " "
                                                
                                            msg_body = msg_body.replace(f"{{{{{i+1}}}}}", val)
                                            
                                flow_msg = WhatsAppMessage(
                                    wa_id=wa_id, direction="out", message=msg_body,
                                    conversation_id=conv.id, message_type="template",
                                    template_name=template_name
                                )
                                if response_data and "error" in response_data:
                                    flow_msg.delivery_status = "failed"
                                    flow_msg.status_error = format_meta_error(response_data)
                                    logger.error(f"Interactive Flow: Failed to send template {template_name} to {wa_id}: {response_data}")
                                    try:
                                        with open("meta_debug_error.log", "a", encoding="utf-8") as f:
                                            f.write(f"\n--- INTERACTIVE FLOW ERROR ---\n"
                                                    f"Timestamp: {datetime.now().isoformat()}\n"
                                                    f"To: {wa_id}\n"
                                                    f"Template: {template_name}\n"
                                                    f"Error: {json.dumps(response_data, indent=2)}\n")
                                    except Exception as log_err:
                                        logger.error(f"Failed to log meta send error: {log_err}")
                                db.add(flow_msg)
                                db.commit()
                                
                            # Notify UI of the automated response
                            if flow_msg:
                                await manager.broadcast({
                                    "type": "new_message",
                                    "wa_id": wa_id,
                                    "message": {
                                        "id": str(flow_msg.id),
                                        "text": flow_msg.message,
                                        "sender": "agent",
                                        "timestamp": flow_msg.created_at.isoformat() if flow_msg.created_at else datetime.now().isoformat()
                                    }
                                })
                            
                            # SKIP the general button/text AI acknowledgment
                            continue
 
                        # 6. LLM Acknowledgment (Rule: Only for button clicks as requested)
                        if is_button_click:
                            logger.info(f"Button click detected from {wa_id}: '{text}'. Generating AI acknowledgment.")
                            # Use the button text as query, context can be expanded later if needed
                            ai_res = chat_with_knowledge(
                                query=f"The user clicked a button with the title: '{text}'. Please provide a short, polite acknowledgment or response.",
                                context="You are an automated assistant. When a user clicks a button, acknowledge their choice politely."
                            )
                            ack_text = ai_res.get("response", "Thank you for your response!")
                            
                            # Send the AI response back to WhatsApp
                            if token and phone_id:
                                meta_send_msg(to=wa_id, text=ack_text, token=token, phone_id=phone_id)
                            
                            # Log the AI message in DB as well
                            ai_msg = WhatsAppMessage(
                                wa_id=wa_id, direction="out", message=ack_text,
                                conversation_id=conv.id
                            )
                            db.add(ai_msg)
                            db.commit()
                            
                            # Notify UI of AI response
                            await manager.broadcast({
                                "type": "new_message",
                                "wa_id": wa_id,
                                "message": {
                                    "id": str(ai_msg.id),
                                    "text": ack_text,
                                    "sender": "agent",
                                    "timestamp": ai_msg.created_at.isoformat()
                                }
                            })
                
                # 2. Handle Status Updates
                if "statuses" in value:
                    for status in value["statuses"]:
                        try:
                            meta_id = status["id"]
                            new_status = status["status"] # 'delivered', 'read', 'failed'
                            
                            msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_id).first()
                            if msg:
                                logger.info(f"Webhook Status Update: {meta_id} -> {new_status}")
                                
                                # Find organization context from conversation
                                target_org_id = None
                                if msg.conversation_id:
                                    conv = db.query(WhatsAppConversation).get(msg.conversation_id)
                                    if conv:
                                        target_org_id = conv.organization_id
                                
                                # SERVICE LOG: Delivery Update
                                log_action(
                                    db=db,
                                    action=f"WEBHOOK_STATUS_{new_status.upper()}",
                                    module="SERVICE",
                                    organization_id=target_org_id,
                                    details={"meta_id": meta_id, "wa_id": msg.wa_id, "status": new_status}
                                )
                                
                                # BE-FIX: Summary Analytics Sync
                                # When status changes from 'sent' to 'delivered' or 'read', 
                                # we update the Campaign and CampaignRun counters so the Dashboard stays accurate.
                                if msg.campaign_id:
                                    try:
                                        # 1. Update Campaign Stats
                                        # Use atomic increment to prevent race conditions during high-volume webhooks
                                        campaign = db.query(Campaign).get(msg.campaign_id)
                                        if campaign:
                                            if new_status == 'delivered' and msg.delivery_status == 'sent':
                                                campaign.delivered_count = (campaign.delivered_count or 0) + 1
                                            elif new_status == 'read':
                                                # If it moves to 'read', it also counts as 'delivered' if we haven't counted it yet
                                                if msg.delivery_status == 'sent': 
                                                    campaign.delivered_count = (campaign.delivered_count or 0) + 1
                                                if msg.delivery_status != 'read':
                                                    campaign.read_count = (campaign.read_count or 0) + 1
                                            elif new_status == 'failed' and msg.delivery_status != 'failed':
                                                campaign.failed_count = (campaign.failed_count or 0) + 1
                                        
                                        # 2. Update the most recent CampaignRun if applicable
                                        from sqlalchemy import desc
                                        run = db.query(CampaignRun).filter(CampaignRun.campaign_id == msg.campaign_id).order_by(desc(CampaignRun.created_at)).first()
                                        if run:
                                            # Ensure counters are not Null
                                            run.success_count = run.success_count or 0
                                            run.failed_count = run.failed_count or 0
                                            
                                            if new_status in ['delivered', 'read'] and msg.delivery_status == 'sent':
                                                run.success_count += 1
                                            elif new_status == 'failed' and msg.delivery_status != 'failed':
                                                run.failed_count += 1
                                    except Exception as sync_err:
                                        logger.error(f"Webhook: Failed to sync analytics for campaign {msg.campaign_id}: {sync_err}")
                                
                                # BE-FIX: Capture detailed error reason from Meta (Rule: Log visibility)
                                if new_status == "failed":
                                    errors = status.get("errors", [])
                                    is_cooldown = False
                                    if errors and isinstance(errors, list) and len(errors) > 0:
                                        err = errors[0]
                                        code = err.get("code")
                                        err_msg = err.get("message") or err.get("title") or ""
                                        is_cooldown = (code == 131049 or "131049" in str(err_msg))
                                        
                                        # Map webhook error fields to format_meta_error structure
                                        error_payload = {
                                            "code": code,
                                            "subcode": err.get("error_subcode"),
                                            "error": err_msg or "Meta delivery failed",
                                            "fbtrace_id": err.get("fbtrace_id")
                                        }
                                        msg.status_error = format_meta_error(error_payload)
                                    else:
                                        msg.status_error = "Meta delivery failed"
                                        
                                    if is_cooldown:
                                        new_status = "cooldown"
                                
                                # 3. Handle Billing Finalization (Rule: Legacy Compatibility)
                                # This updates conversation costs and billing status in the DB.
                                finalize_billing_on_delivery(db, meta_id, new_status)
                                
                                # Update the actual message status
                                msg.delivery_status = new_status
                                db.commit()

                                from app.core.websocket_manager import manager
                                await manager.broadcast({
                                    "type": "status_update",
                                    "meta_id": meta_id,
                                    "status": new_status,
                                    "wa_id": msg.wa_id,
                                    "campaign_id": str(msg.campaign_id) if msg.campaign_id else None
                                })
                        except Exception as status_err:
                            logger.error(f"Webhook: Error processing status update {status.get('id')}: {status_err}")
                            continue # Don't crash the WHOLE webhook if one status update fails
    
    return {"status": "success"}
