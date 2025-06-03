"""
User table & Pydantic schemas for Ultra Civic
Compatible with FastAPI-Users ≥14 and fastapi-users-db-sqlalchemy ≥1.3
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi_users import schemas as fus
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String


# ────────────────────────────────────────────────────────────
# SQLAlchemy base class
# ────────────────────────────────────────────────────────────
class Base(DeclarativeBase):  # Alembic will target Base.metadata
    pass


# ────────────────────────────────────────────────────────────
# Database table
# ────────────────────────────────────────────────────────────
class User(SQLAlchemyBaseUserTableUUID, Base):  # inherits id/email/hashed_pw/flags
    __tablename__ = "user"

    kyc_status: Mapped[str] = mapped_column(
        String(20),
        default="unverified",
        server_default="unverified",
        comment="Stripe KYC status",
    )


# ────────────────────────────────────────────────────────────
# Pydantic schemas consumed by FastAPI-Users routers
# ────────────────────────────────────────────────────────────
class UserRead(fus.BaseUser[UUID]):
    kyc_status: str


class UserCreate(fus.BaseUserCreate):
    """Payload for /auth/register; nothing extra needed."""
    pass


class UserUpdate(fus.BaseUserUpdate):
    """Patchable fields for /me route (optional)."""
    kyc_status: Optional[str] = None
