"""
Authentication System Configuration

This module assembles the complete authentication system for Ultra Civic using
FastAPI-Users v14. It provides JWT-based authentication with user registration,
login, password reset, and email verification capabilities.

The system integrates with the User model and enforces KYC verification
requirements for accessing protected resources. All tokens and password
operations use secure industry-standard practices.
"""

from datetime import timedelta
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Request, HTTPException
from fastapi_users import (
    FastAPIUsers,
    BaseUserManager,
    InvalidPasswordException,
    UUIDIDMixin,
)
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.core.config import get_settings
from app.db import get_session
from app.models.user import User, KYCStatus

settings = get_settings()


async def get_user_db(session=Depends(get_session)) -> AsyncGenerator:
    """Provide database adapter for user operations."""
    yield SQLAlchemyUserDatabase(session, User)


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    """Manage user lifecycle events and password validation."""
    
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def validate_password(
        self, password: str, user
    ) -> None:
        """Enforce password security requirements: 8+ chars, 1+ digit."""
        if len(password) < 8:
            raise InvalidPasswordException(
                reason="Password must be at least 8 characters long"
            )
        
        if not any(char.isdigit() for char in password):
            raise InvalidPasswordException(
                reason="Password must contain at least one digit"
            )

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Handle password reset token generation (dev mode prints to console)."""
        print(f"[DEV] reset-token for {user.email}: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Handle verification token generation (dev mode prints to console)."""
        print(f"[DEV] Verification token for {user.email}: {token}")


async def get_user_manager(
    user_db=Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    """Provide user manager instance for dependency injection."""
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    """Configure JWT strategy with 1-hour access token lifetime."""
    return JWTStrategy(
        secret=settings.jwt_secret,
        lifetime_seconds=int(timedelta(hours=1).total_seconds()),
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)


async def current_verified_user(user: User = Depends(current_active_user)) -> User:
    """
    Dependency ensuring user is both active and KYC verified.
    
    Returns the user if KYC verified, otherwise raises 403 with clear guidance.
    This creates a security gate for sensitive operations.
    """
    if user.kyc_status != KYCStatus.VERIFIED:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "KYC verification required",
                "message": "This operation requires identity verification",
                "kyc_status": user.kyc_status.value,
                "action": "Complete KYC verification to access this resource"
            }
        )
    return user


async def refresh_jwt_token(user: User = Depends(current_active_user)) -> dict:
    """Generate a new JWT token for an authenticated user."""
    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)
    return {"access_token": token, "token_type": "bearer"}
