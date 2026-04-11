import bcrypt
import os

# --- BCrypt/Passlib Compatibility Monkeypatch ---
# Native bcrypt starting from 4.1.0 removed __about__. 
# Passlib 1.7.4 depends on it. This fixes AttributeError.
if not hasattr(bcrypt, "__about__"):
    class About:
        __version__ = bcrypt.__version__
    bcrypt.__about__ = About()

from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine, get_db
from app.core.config import settings
from app.models.settings import SystemSettings
import time
import logging
import uvicorn
import redis
import os
import asyncio
from app.core.websocket_manager import manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("adcom-api")

def migrate_db():
    db = SessionLocal()
    try:
        # --- WhatsApp Templates Migration ---
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'whatsapp_templates'"))
        columns = [row[0] for row in result]
        if 'meta_template_id' not in columns:
            db.execute(text("ALTER TABLE whatsapp_templates ADD COLUMN meta_template_id VARCHAR(100)"))
        if 'rejection_reason' not in columns:
            db.execute(text("ALTER TABLE whatsapp_templates ADD COLUMN rejection_reason TEXT"))
        if 'last_synced_at' not in columns:
            db.execute(text("ALTER TABLE whatsapp_templates ADD COLUMN last_synced_at TIMESTAMP WITH TIME ZONE"))
        if 'variable_mappings' not in columns:
            db.execute(text("ALTER TABLE whatsapp_templates ADD COLUMN variable_mappings JSON"))
        if 'media_id' not in columns:
            db.execute(text("ALTER TABLE whatsapp_templates ADD COLUMN media_id VARCHAR(255)"))

        # --- Campaigns Migration ---
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'campaigns'"))
        camp_cols = [row[0] for row in result]
        updates = [
            ('name', "VARCHAR(255)"),
            ('template_name', "VARCHAR(255)"),
            ('status', "VARCHAR(20) DEFAULT 'draft'"),
            ('contact_list_id', "UUID"),
            ('total_contacts', "INTEGER DEFAULT 0"),
            ('sent_count', "INTEGER DEFAULT 0"),
            ('delivered_count', "INTEGER DEFAULT 0"),
            ('read_count', "INTEGER DEFAULT 0"),
            ('failed_count', "INTEGER DEFAULT 0"),
            ('on_hold_count', "INTEGER DEFAULT 0"),
            ('failure_reason', "VARCHAR(255)"),
            ('total_cost_inr', "DOUBLE PRECISION DEFAULT 0.0"),
            ('total_cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
            ('media_url', "TEXT"),
            ('scheduled_at', "TIMESTAMP WITH TIME ZONE"),
            ('completed_at', "TIMESTAMP WITH TIME ZONE")
        ]
        for col, col_type in updates:
            if col not in camp_cols:
                db.execute(text(f"ALTER TABLE campaigns ADD COLUMN {col} {col_type}"))

        # --- Campaign Runs Migration ---
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'campaign_runs'"))
        run_cols = [row[0] for row in result]
        run_updates = [
            ('on_hold_since', "TIMESTAMP WITH TIME ZONE"),
            ('failure_reason', "VARCHAR(255)"),
            ('on_hold_count', "INTEGER DEFAULT 0")
        ]
        for col, col_type in run_updates:
            if col not in run_cols:
                db.execute(text(f"ALTER TABLE campaign_runs ADD COLUMN {col} {col_type}"))


        # --- WhatsApp Messages Migration ---
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'whatsapp_messages'"))
        msg_cols = [row[0] for row in result]
        msg_updates = [
            ('campaign_id', "UUID"),
            ('whatsapp_cost', "DOUBLE PRECISION DEFAULT 0.0"),
            ('template_name', "VARCHAR(255)"),
            ('input_tokens', "INTEGER DEFAULT 0"),
            ('output_tokens', "INTEGER DEFAULT 0"),
            ('llm_cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
            ('llm_cost_inr', "DOUBLE PRECISION DEFAULT 0.0")
        ]
        for col, col_type in msg_updates:
            if col not in msg_cols:
                db.execute(text(f"ALTER TABLE whatsapp_messages ADD COLUMN {col} {col_type}"))

        # --- WhatsApp Conversations Migration ---
        result = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'whatsapp_conversations'"))
        conv_cols = [row[0] for row in result]
        conv_updates = [
            ('billing_status', "VARCHAR(20) DEFAULT 'pending'"),
            ('cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
            ('cost_inr', "DOUBLE PRECISION DEFAULT 0.0"),
            ('rate_usd', "DOUBLE PRECISION DEFAULT 0.0"),
            ('rate_inr', "DOUBLE PRECISION DEFAULT 0.0"),
            ('exchange_rate', "DOUBLE PRECISION DEFAULT 84.0"),
            ('conversation_count', "INTEGER DEFAULT 0"),
            ('cumulative_cost_usd', "DOUBLE PRECISION DEFAULT 0.0"),
            ('cumulative_cost_inr', "DOUBLE PRECISION DEFAULT 0.0"),
            ('last_user_reply_at', "TIMESTAMP WITH TIME ZONE"),
            ('window_expires_at', "TIMESTAMP WITH TIME ZONE"),
            ('needs_agent', "BOOLEAN DEFAULT FALSE"),
            ('meta_message_id', "VARCHAR(255)")
        ]
        for col, col_type in conv_updates:
            if col not in conv_cols:
                db.execute(text(f"ALTER TABLE whatsapp_conversations ADD COLUMN {col} {col_type}"))

        # --- System Settings Migration ---
        result_s = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_name = 'system_settings'"))
        if result_s.scalar() == 0:
            Base.metadata.tables['system_settings'].create(engine)
            db.commit()
            logger.info("Adcom DB: system_settings table created.")
        
        # Initialize default settings row if missing
        SystemSettings.get_settings(db)

        db.commit()
        logger.info("Adcom DB: Full schema migration sync completed successfully.")
    except Exception as e:
        logger.warning(f"Adcom DB Migration Warning: {str(e)}")
    finally:
        db.close()

# Initialize Database & Run Migrations (Resiliently)
try:
    migrate_db()
    Base.metadata.create_all(bind=engine)
    logger.info("Adcom DB: Metadata creation triggered.")
except Exception as e:
    logger.error(f"Adcom DB Initialization Failed: {str(e)}")

app = FastAPI(title="Adcom WhatsApp Standalone (Latest Branch Sync)", description="FastAPI + Groq + Meta WhatsApp v21.0")

@app.on_event("startup")
async def startup_event():
    # Start the WebSocket Redis listener task
    asyncio.create_task(manager.listen_for_events())
    logger.info("Adcom API: WebSocket Redis listener started.")

# Configure CORS - Parse origins from settings
import json
try:
    cors_origins = json.loads(settings.CORS_ORIGINS)
except json.JSONDecodeError:
    # If not valid JSON, treat as comma-separated string
    cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Total-Count"],
    max_age=600,
)

# Custom Middleware to Log Requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Log query params if present
        query_params = str(request.query_params)
        log_msg = f"API: {request.method} {request.url.path}"
        if query_params:
            log_msg += f" ?{query_params}"
            
        logger.info(f"{log_msg} -> Status: {response.status_code} [{duration:.4f}s]")
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"CRITICAL ERROR on {request.method} {request.url.path} after {duration:.4f}s: {str(e)}", exc_info=True)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server error logged", "error": str(e)}
        )

# --- Legacy Routing Middleware ---
# Some frontend components or external clients might miss the '/api' prefix.
# This middleware transparently redirects them to the correct prefixed route.
@app.middleware("http")
async def legacy_route_middleware(request: Request, call_next):
    path = request.url.path
    # List of known top-level routes that should have /api prefix
    legacy_bases = ["/analytics", "/whatsapp", "/contacts", "/templates", "/campaigns", "/auth"]
    
    if any(path.startswith(base) for base in legacy_bases) and not path.startswith("/api"):
        new_path = f"/api{path}"
        logger.info(f"ROUTING: Redirecting legacy path {path} -> {new_path}")
        # Note: We use a transparent internal redirect by modifying the scope 
        # or we can do a 307. Internal modification is cleaner for the client.
        request.scope["path"] = new_path
    
    response = await call_next(request)
    return response

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception: {request.method} {request.url.path} -> {str(exc)}", exc_info=True)
    return {
        "detail": "An internal server error occurred. The technical team has been notified.",
        "type": type(exc).__name__,
        "path": request.url.path
    }

@app.get("/")
def read_root():
    return {"message": "Adcom Standalone API (v2 Latest) is running", "status": "online"}

@app.get("/api/health/db")
async def health_check_db(db: Session = Depends(get_db)):
    """Check database connectivity and latency."""
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        latency = (time.time() - start_time) * 1000
        return {"status": "healthy", "database": "connected", "latency_ms": latency}
    except Exception as e:
        logger.error(f"HEALTH: Database connection failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api/health/redis")
async def health_redis():
    """Check Redis connectivity (used for Celery)."""
    try:
        from app.core.celery_app import celery_app
        start_time = time.time()
        conn = celery_app.backend.client
        conn.ping()
        latency = (time.time() - start_time) * 1000
        return {"status": "healthy", "redis": "connected", "latency_ms": latency}
    except Exception as e:
        logger.error(f"HEALTH: Redis connection failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api/health/summary")
async def health_summary(db: Session = Depends(get_db)):
    """Comprehensive health summary."""
    db_h = await health_check_db(db)
    redis_h = await health_redis()
    
    overall = "healthy" if db_h["status"] == "healthy" and redis_h["status"] == "healthy" else "degraded"
    
    return {
        "overall": overall,
        "db": db_h,
        "redis": redis_h,
        "timestamp": time.time()
    }

# Deferred Route Imports
from app.routes import (
    whatsapp_routes, 
    contact_routes, 
    auth_routes, 
    webhook_routes, 
    template_routes,
    analytics_routes,
    campaign_routes
)

# Include Routers
# Include Routers
app.include_router(auth_routes.router, prefix="/api")
app.include_router(webhook_routes.router, prefix="/api")
app.include_router(template_routes.router, prefix="/api")
app.include_router(whatsapp_routes.router, prefix="/api")
app.include_router(contact_routes.router, prefix="/api")
app.include_router(analytics_routes.router, prefix="/api")
app.include_router(campaign_routes.router, prefix="/api")

# --- WebSocket Endpoint ---
from app.core.websocket_manager import manager

@app.websocket("/api/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Just keep the connection alive and listen for any pings
            data = await websocket.receive_text()
            # If we need to handle incoming WS messages from the client:
            # await manager.broadcast(f"Client says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

