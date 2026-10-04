from typing import List, Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings configured via environment variables.
    Clean, lean configuration tailored for Supabase PostgreSQL & Supabase Auth.
    """
    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Base Application Metadata
    PROJECT_NAME: str = "OpsMind AI Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Supabase Configuration & Auth Keys
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None

    # Fallback JWT Secret for local dev / testing if Supabase JWT secret is not set
    SECRET_KEY: str = "opsmind-local-dev-fallback-secret-key-32-chars-min"
    ALGORITHM: str = "HS256"

    # Database Configuration (Supabase PostgreSQL / SQLite fallback for tests)
    DATABASE_URL: Optional[str] = None
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        Constructs the asynchronous database connection URI.
        Normalizes postgres:// or postgresql:// to postgresql+asyncpg:// for Supabase.
        """
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return "sqlite+aiosqlite:///./opsmind_local.db"

    # CORS Settings
    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # AI Service Settings
    GEMINI_API_KEY: Optional[str] = None
    AI_CONFIDENCE_THRESHOLD: float = 0.75

    # Inbound Webhook Security
    WEBHOOK_SECRET: str = "opsmind_webhook_secret_key"

    # Outbound SMTP / Email Dispatch Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "orders@opsmind.io"
    SMTP_TLS: bool = True
    EMAIL_ENABLED: bool = False

    # Inbound IMAP Mailbox Poller Settings (Direct Gmail / IMAP Inbox Reader)
    IMAP_HOST: str = "imap.gmail.com"
    IMAP_PORT: int = 993
    IMAP_USER: Optional[str] = None
    IMAP_PASSWORD: Optional[str] = None
    IMAP_POLL_INTERVAL_SECONDS: int = 20
    IMAP_ENABLED: bool = True

    # Celery / Redis Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"


settings = Settings()
