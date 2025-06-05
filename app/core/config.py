"""
Application Configuration Management

This module centralizes all configuration settings for the Ultra Civic backend.
It uses Pydantic Settings to automatically load environment variables from
.env files and validate their types, ensuring configuration consistency
across development, testing, and production environments.

The settings are cached using lru_cache to avoid repeated environment
variable parsing during application runtime.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    database_url: str
    database_url_sync: str
    jwt_secret: str
    stripe_secret: str
    stripe_webhook_secret: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()  # type: ignore[call-arg]

