"""
Magic Link Authentication Models

This module defines the MagicLink model for passwordless authentication.
Magic links provide secure, time-limited authentication tokens sent via email
that expire after 5 minutes and can only be used once.

The model tracks creation, expiration, usage, and optional security binding
to IP address and User-Agent for enhanced security.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlmodel import SQLModel

from app.models.user import Base

if TYPE_CHECKING:
    from app.models.user import User


class MagicLink(Base):
    """Magic link token for passwordless authentication."""
    
    __tablename__ = "magic_link"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Token and user relationship
    token: Mapped[str] = mapped_column(
        String(64), 
        unique=True, 
        nullable=False,
        comment="Secure random token for authentication"
    )
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="User this magic link belongs to"
    )
    
    # Timing controls
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="When the magic link was created"
    )
    
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the magic link expires (5 minutes from creation)"
    )
    
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the magic link was redeemed"
    )
    
    # Security binding (optional)
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="IP address where magic link was requested"
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent where magic link was requested"
    )
    
    # Status tracking
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the magic link has been used"
    )
    
    # Redirect URL for after authentication
    redirect_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to redirect to after successful authentication"
    )
    
    # Relationship
    user: Mapped["User"] = relationship(back_populates="magic_links")

    def __init__(self, **kwargs):
        if "expires_at" not in kwargs:
            kwargs["expires_at"] = datetime.now(timezone.utc) + timedelta(minutes=5)
        super().__init__(**kwargs)
    
    @property
    def is_expired(self) -> bool:
        """Check if the magic link has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def is_valid(self) -> bool:
        """Check if the magic link is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired


class MagicLinkRequest(SQLModel):
    """Request schema for creating a magic link."""
    email: str
    redirect_url: Optional[str] = None


class MagicLinkResponse(SQLModel):
    """Response schema for magic link creation."""
    message: str
    expires_in_minutes: int = 5