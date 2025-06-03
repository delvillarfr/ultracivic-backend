# app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Async URL for FastAPI
    database_url: str

    # Sync URL for Alembic
    database_url_sync: str

    # Auth / JWT
    jwt_secret: str

    # Stripe
    stripe_secret: str
    stripe_webhook_secret: str

    # ↓ new way to declare .env support in Pydantic v2
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()

