from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.settings import SystemSettings
from app.services.currency_service import update_system_exchange_rate
import logging

router = APIRouter(prefix="/system", tags=["System"])
logger = logging.getLogger(__name__)

@router.get("/currency", response_model=dict)
def get_exchange_rate(db: Session = Depends(get_db)):
    """Get the current exchange rate stored in the system."""
    settings = SystemSettings.get_settings(db)
    return {
        "exchange_rate": settings.exchange_rate or 84.0,
        "last_updated": settings.updated_at.isoformat() if hasattr(settings, 'updated_at') and settings.updated_at else None
    }

@router.post("/currency/sync", response_model=dict)
def sync_exchange_rate(db: Session = Depends(get_db)):
    """Fetch live exchange rate from Frankfurter and update database."""
    rate = update_system_exchange_rate(db)
    if rate:
        return {"message": "Exchange rate updated successfully", "rate": rate}
    raise HTTPException(status_code=500, detail="Failed to fetch live exchange rate from provider.")
