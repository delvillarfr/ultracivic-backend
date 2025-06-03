"""
Authentication wiring for Ultra Civic
FastAPI-Users v14 + fastapi-users-db-sqlalchemy ≥1.3
"""

from datetime import timedelta
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Request
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
from fastapi_users.password import PasswordHelper
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from app.core.config import get_settings
from app.db import get_session
from app.models.user import User

# ─── Settings & helpers ─────────────────────────────────────────────────
settings = get_settings()
pwd_helper = PasswordHelper()

# ─── Database adapter ──────────────────────────────────────────────────
async def get_user_db(session=Depends(get_session)) -> AsyncGenerator:
    yield SQLAlchemyUserDatabase(session, User)

# ─── User manager ──────────────────────────────────────────────────────
class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    reset_password_token_secret = settings.jwt_secret
    verification_token_secret = settings.jwt_secret

    async def validate_password(
        self, password: str, user: User | None = None
    ) -> None:
        if len(password) < 5:
            raise InvalidPasswordException(reason="Password too short")

    # ← NEW: password-reset hook lives inside the manager
    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:  # noqa: D401
        # In production send email; for dev just print
        print(f"[DEV] reset-token for {user.email}: {token}")

async def get_user_manager(
    user_db=Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)

# ─── JWT backend ───────────────────────────────────────────────────────
bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.jwt_secret,
        lifetime_seconds=int(timedelta(days=1).total_seconds()),
    )

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# ─── FastAPI-Users instance ────────────────────────────────────────────
fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,      # ← user-manager factory
    [auth_backend],        # ← list of auth backends
)

# Convenience dependency for protected routes
current_active_user = fastapi_users.current_user(active=True)

# Optional: dev-only callback to print reset-tokens
async def on_after_forgot_password(user: User, token: str, request: Request | None = None):
    print(f"[DEV] Reset token for {user.email}: {token}")
