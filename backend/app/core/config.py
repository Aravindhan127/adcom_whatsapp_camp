from pydantic_settings import BaseSettings
import os
from typing import Optional
from dotenv import load_dotenv

# Explicitly load .env from the backend directory using absolute path
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(dotenv_path=env_path, override=True)

class Settings(BaseSettings):
    # Database (Standardized on 127.0.0.1 for Windows compatibility)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:root@127.0.0.1:5432/adcom_standalone")

    # Security - MUST be set in environment
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 week

    # Meta/WhatsApp Config - MUST be set in environment
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN")
    PHONE_NUMBER_ID: str = os.getenv("PHONE_NUMBER_ID")
    WABA_ID: str = os.getenv("WABA_ID")
    META_APP_ID: str = os.getenv("META_APP_ID")
    MY_VERIFY_TOKEN: str = os.getenv("MY_VERIFY_TOKEN")

    # API Keys
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")

    # Redis
    # Redis (Forced to 127.0.0.1 for maximum Windows/Docker compatibility)
    REDIS_URL: str = os.getenv("REDIS_URL") or "redis://127.0.0.1:6379/0"

    # CORS Origins (comma-separated)
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")

    class Config:
        env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
        extra = "allow"

settings = Settings()

# Validate critical settings on startup
if not settings.JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is required")
if not settings.WHATSAPP_TOKEN:
    raise ValueError("WHATSAPP_TOKEN environment variable is required")
if not settings.PHONE_NUMBER_ID:
    raise ValueError("PHONE_NUMBER_ID environment variable is required")
if not settings.WABA_ID:
    raise ValueError("WABA_ID environment variable is required")
    