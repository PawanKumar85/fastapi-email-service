"""
Production-grade configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings with validation and sensible defaults."""

    # App
    app_name: str = Field(default="Email Microservice", alias="APP_NAME")
    debug: bool = Field(default=False, alias="DEBUG")
    api_key: str = Field(..., alias="API_KEY", min_length=16, description="Secret key for API authentication")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # SMTP
    smtp_host: str = Field(..., alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT", ge=1, le=65535)
    smtp_user: str = Field(..., alias="SMTP_USER")
    smtp_password: str = Field(..., alias="SMTP_PASSWORD")
    smtp_from_email: EmailStr = Field(..., alias="SMTP_FROM_EMAIL")
    smtp_from_name: str = Field(default="No Reply", alias="SMTP_FROM_NAME")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, alias="SMTP_USE_SSL")

    # Optional
    default_reply_to: Optional[EmailStr] = Field(default=None, alias="DEFAULT_REPLY_TO")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins into list."""
        if v == "*":
            return ["*"]
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @field_validator("smtp_use_tls", "smtp_use_ssl", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )


# Global settings instance (loaded once)
settings = Settings()

# Security note: Do not log sensitive fields
def get_public_settings() -> dict:
    """Return non-sensitive config for health/debug endpoints."""
    return {
        "app_name": settings.app_name,
        "debug": settings.debug,
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_from_email": settings.smtp_from_email,
        "smtp_use_tls": settings.smtp_use_tls,
        "log_level": settings.log_level,
    }