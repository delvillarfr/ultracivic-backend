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
from app.models.user import User

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
        """Enforce minimum password security requirements."""
        if len(password) < 5:
            raise InvalidPasswordException(reason="Password too short")

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
    """Configure JWT strategy with 24-hour token lifetime."""
    return JWTStrategy(
        secret=settings.jwt_secret,
        lifetime_seconds=int(timedelta(days=1).total_seconds()),
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
    """Dependency ensuring user is both active and KYC verified."""
    if user.kyc_status != "verified":
        raise HTTPException(status_code=403, detail="KYC verification required")
    return user
