# app/core/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # DB
    database_url: str  # Postgres DSN

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

