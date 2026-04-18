import requests
import logging
from sqlalchemy.orm import Session
from app.models.settings import SystemSettings

logger = logging.getLogger(__name__)

def fetch_live_exchange_rate():
    """
    Fetch the latest USD to INR exchange rate from Frankfurter API.
    Returns float or None if failed.
    """
    try:
        # Frankfurter API is free and doesn't require an API key
        url = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        rate = data.get("rates", {}).get("INR")
        if rate:
            logger.info(f"Successfully fetched live exchange rate: 1 USD = {rate} INR")
            return float(rate)
        
        return None
    except Exception as e:
        logger.error(f"Error fetching live exchange rate: {e}")
        return None

def update_system_exchange_rate(db: Session):
    """
    Fetch the live rate and update the SystemSettings in the database.
    """
    live_rate = fetch_live_exchange_rate()
    if live_rate:
        settings = SystemSettings.get_settings(db)
        settings.exchange_rate = live_rate
        db.add(settings)
        db.commit()
        db.refresh(settings)
        return live_rate
    return None
