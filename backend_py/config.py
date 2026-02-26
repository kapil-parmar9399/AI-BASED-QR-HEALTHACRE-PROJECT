"""
Configuration management for Swasthya Healthcare System
Loads settings from environment variables with defaults
"""
import os
from typing import Optional

class Config:
    """Base configuration"""
    
    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "swasthya_db")
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "3003"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    
    # Public URL for QR codes
    PUBLIC_URL: Optional[str] = os.getenv("PUBLIC_URL")
    
    # Email (SMTP)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "noreply@swasthya.health")
    SENDER_NAME: str = os.getenv("SENDER_NAME", "Swasthya Healthcare")
    SMTP_ENABLED: bool = bool(SMTP_USERNAME and SMTP_PASSWORD)
    
    # Twilio SMS
    TWILIO_ACCOUNT_SID: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER: Optional[str] = os.getenv("TWILIO_FROM_NUMBER")
    TWILIO_ENABLED: bool = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)
    
    # ngrok
    NGROK_AUTHTOKEN: Optional[str] = os.getenv("NGROK_AUTHTOKEN")
    
    # QR Token
    QR_TOKEN_EXPIRY_DAYS: int = int(os.getenv("QR_TOKEN_EXPIRY_DAYS", "7"))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Security (CORS)
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:3003",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3003",
    ]
    if not DEBUG:
        # Add production domains here
        CORS_ORIGINS.extend([
            # "https://yourdomain.com",
        ])
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = not DEBUG
    RATE_LIMIT_PER_MINUTE: int = 60
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if cls.ENVIRONMENT == "production":
            if cls.SECRET_KEY == "dev-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY must be changed in production! "
                    "Set via environment variable."
                )
            if not cls.PUBLIC_URL:
                raise ValueError(
                    "PUBLIC_URL must be set in production!"
                )
        return True

# Default instance
config = Config()
