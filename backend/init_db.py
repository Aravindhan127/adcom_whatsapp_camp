from app.core.database import Base, engine
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.whatsapp_conversation import WhatsAppConversation
from app.models.contact import Contact, ContactList
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun
from app.models.template import WhatsAppTemplate
from app.models.agent import Agent

def init_db():
    print("Creating Adcom Standalone Database Tables...")
    Base.metadata.create_all(bind=engine)
    print("Done! Your database is ready.")

if __name__ == "__main__":
    init_db()
