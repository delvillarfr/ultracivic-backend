"""
Application Configuration Management

This module centralizes all configuration settings for the Ultra Civic backend.
It uses Pydantic Settings to automatically load environment variables from
.env files and validate their types, ensuring configuration consistency
across development, testing, and production environments.

The settings are cached using lru_cache to avoid repeated environment
variable parsing during application runtime.
"""

import sys
from enum import Enum
from functools import lru_cache

try:
    # Pydantic v2
    from pydantic import Field, SecretStr, field_validator  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - fallback for older Pydantic versions
    from pydantic import Field, SecretStr, validator as field_validator  # type: ignore
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Valid application environment values."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Valid logging level values."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings are validated for type correctness and business rules.
    Missing required variables will cause the application to fail fast
    with descriptive error messages.
    """
    
    # Database Configuration
    database_url: str = Field(
        ...,
        description="Primary database URL for async operations",
        min_length=1,
        pattern=r"^postgresql\+asyncpg://.*",
    )
    
    database_url_sync: str = Field(
        ...,
        description="Synchronous database URL for Alembic migrations",
        min_length=1,
        pattern=r"^postgresql://.*",
    )
    
    # Authentication & Security
    jwt_secret: SecretStr = Field(
        ...,
        description="JWT secret key for token signing and verification",
    )
    
    # Stripe Integration
    stripe_secret: SecretStr = Field(
        ...,
        description="Stripe secret API key for server-side operations",
    )
    
    stripe_webhook_secret: SecretStr = Field(
        ...,
        description="Stripe webhook signing secret for webhook verification",
    )
    
    # Optional Configuration
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment mode"
    )
    
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level for application"
    )
    
    # Email Configuration
    resend_api_key: SecretStr = Field(
        default="",
        description="Resend API key for sending emails"
    )
    
    from_email: str = Field(
        default="noreply@ultracivic.com",
        description="From email address for system emails"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: SecretStr) -> SecretStr:
        """Validate JWT secret meets security requirements."""
        secret_value = v.get_secret_value()
        
        if len(secret_value) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters long for security. "
                "Generate a secure secret with: openssl rand -hex 32"
            )
        
        if secret_value in ["changeme", "dev-secret", "your-secret-here"]:
            raise ValueError(
                "JWT_SECRET cannot use placeholder values. "
                "Generate a secure secret with: openssl rand -hex 32"
            )
        
        return v

    @field_validator("stripe_secret")
    @classmethod
    def validate_stripe_secret(cls, v: SecretStr) -> SecretStr:
        """Validate Stripe secret key format."""
        secret_value = v.get_secret_value()
        
        # Allow test values during testing
        if secret_value.startswith("sk_test_testing_"):
            return v
        
        if secret_value in ["your_stripe_secret_key_here", "sk_test_your_stripe_secret_key_here"]:
            raise ValueError(
                "STRIPE_SECRET cannot use placeholder values. "
                "Get your actual Stripe secret key from https://dashboard.stripe.com/apikeys"
            )
        
        return v

    @field_validator("stripe_webhook_secret")
    @classmethod
    def validate_stripe_webhook_secret(cls, v: SecretStr) -> SecretStr:
        """Validate Stripe webhook secret format."""
        secret_value = v.get_secret_value()
        
        # Allow test values during testing
        if secret_value.startswith("whsec_testing_"):
            return v
        
        if secret_value in ["your_webhook_secret_here", "whsec_your_webhook_secret_here"]:
            raise ValueError(
                "STRIPE_WEBHOOK_SECRET cannot use placeholder values. "
                "Get your actual webhook secret from https://dashboard.stripe.com/webhooks"
            )
        
        return v

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL format for async operations."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must start with 'postgresql+asyncpg://' for async operations. "
                "Example: postgresql+asyncpg://user:password@host:port/database"
            )
        return v

    @field_validator("database_url_sync")
    @classmethod
    def validate_database_url_sync(cls, v: str) -> str:
        """Validate synchronous database URL format."""
        if not v.startswith("postgresql://"):
            raise ValueError(
                "DATABASE_URL_SYNC must start with 'postgresql://' for Alembic migrations. "
                "Example: postgresql://user:password@host:port/database"
            )
        return v


def create_settings() -> Settings:
    """
    Create and validate settings instance with helpful error messages.
    
    This function provides better error handling than the raw Settings()
    constructor, giving users clear guidance on how to fix configuration issues.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as e:
        error_message = str(e)
        
        # Extract field name from Pydantic validation errors
        if "validation error" in error_message.lower():
            print("\n❌ Configuration Validation Error:", file=sys.stderr)
            print(f"{error_message}", file=sys.stderr)
        else:
            print(f"\n❌ Configuration Error: {error_message}", file=sys.stderr)
        
        print("\n💡 To fix this:", file=sys.stderr)
        print("1. Copy .env.example to .env", file=sys.stderr)
        print("2. Fill in all required values in .env", file=sys.stderr)
        print("3. Ensure all values meet the format requirements", file=sys.stderr)
        print("\nSee .env.example for detailed configuration instructions.", file=sys.stderr)
        sys.exit(1)


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return create_settings()

