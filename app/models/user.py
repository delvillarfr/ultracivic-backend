"""
User Data Models and Database Schema

This module defines the complete user data model for Ultra Civic, including
the SQLAlchemy table definition and Pydantic schemas for API serialization.
It integrates with FastAPI-Users for authentication while extending the base
user model with KYC verification status tracking.

The design separates database concerns (User table) from API concerns
(UserRead, UserCreate, UserUpdate schemas) following clean architecture principles.
"""

from __future__ import annotations
import enum
from typing import Optional
from uuid import UUID

from fastapi_users import schemas as fus
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class KYCStatus(str, enum.Enum):
    """Valid KYC verification status values for Stripe Identity."""
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all database models."""
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    """User table extending FastAPI-Users base with KYC verification status."""
    
    __tablename__ = "user"

    kyc_status: Mapped[KYCStatus] = mapped_column(
        Enum(KYCStatus, name="kyc_status_enum"),
        default=KYCStatus.UNVERIFIED,
        server_default="unverified",
        nullable=False,
        comment="Stripe KYC verification status",
    )
    
    stripe_verification_session_id: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        comment="Stripe Identity verification session ID for audit trail",
    )


class UserRead(fus.BaseUser[UUID]):
    """User data schema for API responses."""
    kyc_status: KYCStatus
    stripe_verification_session_id: Optional[str] = None


class UserCreate(fus.BaseUserCreate):
    """User registration schema for API requests."""
    pass


class UserUpdate(fus.BaseUserUpdate):
    """User update schema for PATCH operations."""
    kyc_status: Optional[KYCStatus] = None
    stripe_verification_session_id: Optional[str] = None
