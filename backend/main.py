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



# Initialize Database & Run Migrations (Resiliently)
# Initialize Database
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Adcom DB: Metadata creation triggered.")
    
    # Initialize RBAC Roles and Permissions
    from app.core.rbac_init import init_rbac
    with SessionLocal() as db:
        init_rbac(db)
    logger.info("Adcom DB: RBAC initialization completed.")
    
except Exception as e:
    logger.error(f"Adcom DB Initialization Failed: {str(e)}")

# --- SSL Configuration ---
SSL_CERT_FILE = settings.SSL_CERT_FILE
SSL_KEY_FILE  = settings.SSL_KEY_FILE

# Detect if SSL is available
_ssl_available = bool(SSL_CERT_FILE and SSL_KEY_FILE and os.path.isfile(SSL_CERT_FILE) and os.path.isfile(SSL_KEY_FILE))

# Swagger / OpenAPI server URL
_base_url = "https://www.ttcitaloraa.shop" if _ssl_available else "http://localhost:3000"

app = FastAPI(
    title="Adcom WhatsApp Standalone (Latest Branch Sync)",
    description="FastAPI + Groq + Meta WhatsApp v21.0",
    version="2.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    servers=[
        {"url": _base_url, "description": "Production (HTTPS)" if _ssl_available else "Local Dev"},
        {"url": "http://localhost:3000", "description": "Local Dev (HTTP)"},
    ],
)

@app.on_event("startup")
async def startup_event():
    # Start the WebSocket Redis listener task
    asyncio.create_task(manager.listen_for_events())
    
    # Sync live exchange rate on startup
    # Initialize RBAC and permissions
    from app.core.rbac_init import init_rbac
    db = SessionLocal()
    try:
        init_rbac(db)
        from app.services.currency_service import update_system_exchange_rate
        update_system_exchange_rate(db)
        logger.info("Adcom API: Startup sync (RBAC + Exchange Rate) completed.")
    finally:
        db.close()
        
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

@app.get("/api/doc")
def redirect_api_doc():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.get("/api/docs")
def redirect_api_docs():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

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
    campaign_routes,
    system_routes,
    audit_routes,
    admin_routes,
    interactive_flow_routes
)

# Include Routers
# Include Routers
app.include_router(admin_routes.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api")
app.include_router(webhook_routes.router, prefix="/api")
app.include_router(template_routes.router, prefix="/api")
app.include_router(whatsapp_routes.router, prefix="/api")
app.include_router(contact_routes.router, prefix="/api")
app.include_router(analytics_routes.router, prefix="/api")
app.include_router(campaign_routes.router, prefix="/api")
app.include_router(system_routes.router, prefix="/api")
app.include_router(audit_routes.router, prefix="/api")
app.include_router(interactive_flow_routes.router, prefix="/api")

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
    import threading
    from fastapi import FastAPI as _FastAPI
    from fastapi.responses import RedirectResponse as _RedirectResponse

    if _ssl_available:
        # --- HTTP → HTTPS Redirect App (port 80) ---
        http_redirect_app = _FastAPI()

        @http_redirect_app.middleware("http")
        async def redirect_to_https(request: Request, call_next):
            https_url = str(request.url).replace("http://", "https://", 1)
            # Strip port 80 from URL if present
            https_url = https_url.replace(":80/", "/").replace(":80", "")
            return _RedirectResponse(url=https_url, status_code=301)

        def run_http_redirect():
            import uvicorn as _uvicorn
            logger.info("Starting HTTP → HTTPS redirect server on port 80")
            _uvicorn.run(http_redirect_app, host="0.0.0.0", port=80)

        # Start port 80 redirect in background thread
        redirect_thread = threading.Thread(target=run_http_redirect, daemon=True)
        redirect_thread.start()

        # Start main HTTPS app on port 443
        logger.info(f"Starting HTTPS server on port 443 | cert={SSL_CERT_FILE}")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=443,
            ssl_certfile=SSL_CERT_FILE,
            ssl_keyfile=SSL_KEY_FILE,
        )
    else:
        logger.warning(
            "SSL key file not found at C:\\ssl\\www_ttcitaloraa_shop.key — "
            "starting on port 8000 (HTTP only)."
        )
        uvicorn.run(app, host="0.0.0.0", port=8000)


