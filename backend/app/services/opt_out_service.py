from sqlalchemy.orm import Session
from app.models.contact import Contact, ContactStatus

OPT_OUT_KEYWORDS = ["STOP", "UNSUBSCRIBE", "BLOCK", "CANCEL"]

def handle_opt_out(db: Session, wa_id: str, message: str) -> bool:
    """
    Check if the incoming message is an opt-out request.
    If yes, block the contact and return True.
    """
    if message.upper().strip() in OPT_OUT_KEYWORDS:
        contact = db.query(Contact).filter(Contact.phone_number == wa_id).first()
        if contact:
            contact.status = ContactStatus.BLOCKED.value
            db.commit()
            return True
    return False

def is_contact_blocked(db: Session, wa_id: str) -> bool:
    contact = db.query(Contact).filter(Contact.phone_number == wa_id).first()
    return contact is not None and contact.status == ContactStatus.BLOCKED.value
