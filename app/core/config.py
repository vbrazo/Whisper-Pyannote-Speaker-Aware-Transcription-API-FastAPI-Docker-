import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings and configuration"""
    
    # Database
    DATABASE_URL: str = "sqlite:///./whisper_api.db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # OAuth Configuration
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    
    # HuggingFace Token for Pyannote
    HF_TOKEN: Optional[str] = None
    
    # Basic Auth (for API access)
    VALID_USERNAME: str = "admin"
    VALID_PASSWORD: str = "password123"
    
    # File Storage
    OUTPUT_DIR: str = "output"
    
    # Whisper Model
    WHISPER_MODEL: str = "base"  # tiny, base, small, medium, large
    
    # Pyannote Model
    PYANNOTE_MODEL: str = "pyannote/speaker-diarization@2.1"
    
    # Session Configuration
    SESSION_MAX_AGE: int = 3600  # 1 hour
    SESSION_SAME_SITE: str = "lax"
    
    # Webhook Configuration
    WEBHOOK_TIMEOUT: float = 30.0
    WEBHOOK_MAX_RETRIES: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings() 