import os
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Blood SOS"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./blood_sos.db")
    
    # JWT Authentication
    JWT_SECRET: str = os.getenv("JWT_SECRET", "blood_sos_super_secret_key_change_in_production_2026")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
    
    # Business Logic
    POINTS_PER_VERIFIED_DONATION: int = int(os.getenv("POINTS_PER_VERIFIED_DONATION", "100"))
    DONOR_SEARCH_RADIUS_KM: float = float(os.getenv("DONOR_SEARCH_RADIUS_KM", "25.0"))
    
    # Email SMTP (Optional)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST", None)
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "notifications@bloodsos.org")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "True").lower() in ("true", "1", "yes")
    
    # SMS (Optional)
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "none")  # none, twilio, fast2sms
    SMS_API_KEY: Optional[str] = os.getenv("SMS_API_KEY", None)
    TWILIO_ACCOUNT_SID: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID", None)
    TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN", None)
    TWILIO_FROM_PHONE: Optional[str] = os.getenv("TWILIO_FROM_PHONE", None)
    REQUIRE_PHONE_VERIFICATION: bool = os.getenv("REQUIRE_PHONE_VERIFICATION", "true").lower() in ("true", "1", "yes")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    PORT: int = int(os.getenv("PORT", "8000"))

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def get_normalized_database_url() -> str:
    url = settings.DATABASE_URL
    if not url:
        return "sqlite:///./blood_sos.db"
    # Convert postgres:// to postgresql:// for SQLAlchemy standard
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # If postgresql:// without driver specified, psycopg2 is used
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url
