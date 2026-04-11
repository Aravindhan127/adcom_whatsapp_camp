from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.core.database import Base

class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    meta_balance_inr = Column(Float, default=1000.0) # Estimated Meta Balance
    meta_balance_usd = Column(Float, default=12.0)
    
    # Pricing overrides (Rule 1 & 12)
    marketing_rate_inr = Column(Float, default=0.82)
    utility_rate_inr = Column(Float, default=0.35)
    authentication_rate_inr = Column(Float, default=0.35)
    service_rate_inr = Column(Float, default=0.0)
    
    exchange_rate = Column(Float, default=84.0)
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    @classmethod
    def get_settings(cls, db):
        settings = db.query(cls).first()
        if not settings:
            settings = cls()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings
