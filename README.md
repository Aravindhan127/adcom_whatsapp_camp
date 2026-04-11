# Adcom: WhatsApp Standalone AI Platform (v2 Latest)

A high-performance, standalone WhatsApp messaging platform perfectly synced with the latest development branches.

## 🚀 Latest Branch Features (Sync v2.0)

- **Brochure Automation**: Automatically delivers PDF brochures based on WhatsApp button interactions.
- **Enhanced v2 Dashboard**: Premium glassmorphism UI with tracking for message volume, read rates, costs (INR/USD), and brochure delivery.
- **Meta Billing Engine v2**: Strict implementation of the 9 Meta billing rules with 2024 pricing.
- **AI RAG Integration**: Powered by Groq LLM with latest system prompts and safety guardrails.
- **Latest Graph API**: Integrated with Meta Graph API v21.0.

## 🛠️ Project Structure

```text
Adcom_Standalone/
├── backend/            # FastAPI (Phase 1 Foundation)
│   ├── app/
│   │   ├── core/      # Database (PostgreSQL), Config & Security (JWT)
│   │   ├── models/    # DB Models (Contacts, Campaigns, Messages, Agents)
│   │   ├── routes/    # API Endpoints (Webhooks, Auth, Analytics)
│   │   └── services/  # Core Logic (Celery queues, WhatsApp Meta API)
│   └── main.py
└── frontend/           # React + Vite shell
    └── src/
        ├── components/ # Reusable UI components
        ├── pages/      # Dashboards, Login, Campaign view
        ├── services/   # Frontend API interactions
        └── App.tsx     # React Router setup
```

## 🚦 Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
# Set .env: WHATSAPP_TOKEN, PHONE_NUMBER_ID, GROQ_API_KEY, MY_VERIFY_TOKEN
python main.py
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---
**Adcom** — Synced with Latest Push. Built for Perfection.
