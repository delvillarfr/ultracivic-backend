"""
Session Management Models

This module defines the session model for server-side session storage.
Sessions are created after successful magic link redemption and provide
stateful authentication without requiring JWT tokens.

Sessions include security features like IP binding, expiration tracking,
and automatic cleanup of stale sessions.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlmodel import SQLModel

from app.models.user import Base

if TYPE_CHECKING:
    from app.models.user import User


class Session(Base):
    """User session for magic link authentication."""
    
    __tablename__ = "session"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Session identification
    session_token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="Secure session identifier"
    )
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="User this session belongs to"
    )
    
    # Timing controls
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When the session was created"
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the session expires"
    )
    
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When the session was last accessed"
    )
    
    # Security tracking
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="IP address where session was created"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent where session was created"
    )
    
    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the session is active"
    )
    
    # Optional session data
    session_data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON data for session (e.g., permissions, preferences)"
    )
    
    # Relationship
    user: Mapped["User"] = relationship(back_populates="sessions")

    def __init__(self, **kwargs):
        if "expires_at" not in kwargs:
            # Default session lifetime: 7 days
            kwargs["expires_at"] = datetime.now(timezone.utc) + timedelta(days=7)
        super().__init__(**kwargs)
    
    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if the session is valid (active and not expired)."""
        return self.is_active and not self.is_expired
    
    def touch(self) -> None:
        """Update the last_accessed_at timestamp."""
        self.last_accessed_at = datetime.now(timezone.utc)
    
    def extend_expiration(self, days: int = 7) -> None:
        """Extend the session expiration by the given number of days."""
        self.expires_at = datetime.now(timezone.utc) + timedelta(days=days)


class SessionCreate(SQLModel):
    """Schema for creating a new session."""
    user_id: UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    expires_in_days: int = 7


class SessionInfo(SQLModel):
    """Schema for session information in responses."""
    id: UUID
    session_token: str
    user_id: UUID
    created_at: datetime
    expires_at: datetime
    last_accessed_at: datetime
    is_active: bool