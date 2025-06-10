"""
Magic Link Authentication Service

This module provides the core functionality for passwordless authentication
using secure, time-limited magic links sent via email. It handles token
generation, validation, and security binding.

Security features:
- Cryptographically secure random tokens (64 chars)
- 5-minute expiration window
- Single-use tokens with usage tracking  
- Optional IP address and User-Agent binding
- Automatic cleanup of expired tokens
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.magic_link import MagicLink


class MagicLinkService:
    """Service class for magic link authentication operations."""
    
    @staticmethod
    def generate_token() -> str:
        """Generate a cryptographically secure random token."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))
    
    @staticmethod
    async def create_magic_link(
        db: AsyncSession,
        user: User,
        request: Request,
        redirect_url: Optional[str] = None
    ) -> MagicLink:
        """
        Create a new magic link for the given user.
        
        Automatically expires any existing unused magic links for the user
        to prevent accumulation of valid tokens.
        """
        # Clean up any existing unused magic links for this user
        await MagicLinkService.cleanup_user_links(db, user.id)
        
        # Generate secure token
        token = MagicLinkService.generate_token()
        
        # Extract client information for security binding
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Create new magic link
        magic_link = MagicLink(
            token=token,
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            redirect_url=redirect_url,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        
        db.add(magic_link)
        await db.commit()
        await db.refresh(magic_link)
        
        return magic_link
    
    @staticmethod
    async def find_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Find a user by email address."""
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user_if_not_exists(db: AsyncSession, email: str) -> User:
        """
        Create a new user if one doesn't exist with the given email.
        
        For magic link auth, we create users on-demand during the first
        authentication attempt. No password is required.
        """
        user = await MagicLinkService.find_user_by_email(db, email)
        
        if not user:
            user = User(
                email=email,
                hashed_password="",  # No password needed for magic link auth
                is_active=True,
                is_verified=False  # Will be verified through magic link
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        return user
    
    @staticmethod
    async def validate_and_redeem_token(
        db: AsyncSession,
        token: str,
        request: Request,
        enforce_ip_binding: bool = True
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        Validate and redeem a magic link token.
        
        Returns:
            Tuple of (User, redirect_url) if valid, (None, None) if invalid
            
        Security checks:
        - Token exists and hasn't been used
        - Token hasn't expired  
        - Optional: IP address matches (if enforce_ip_binding=True)
        - Optional: User-Agent matches (if enforce_ip_binding=True)
        """
        # Find the magic link
        stmt = select(MagicLink).where(MagicLink.token == token)
        result = await db.execute(stmt)
        magic_link = result.scalar_one_or_none()
        
        if not magic_link:
            return None, None
        
        # Check if already used
        if magic_link.is_used:
            return None, None
        
        # Check if expired
        if magic_link.is_expired:
            # Clean up expired token
            await db.delete(magic_link)
            await db.commit()
            return None, None
        
        # Security binding checks (optional but recommended)
        if enforce_ip_binding and magic_link.ip_address:
            client_ip = request.client.host if request.client else None
            if client_ip != magic_link.ip_address:
                return None, None
        
        if enforce_ip_binding and magic_link.user_agent:
            user_agent = request.headers.get("user-agent")
            if user_agent != magic_link.user_agent:
                return None, None
        
        # Get the user
        user = await db.get(User, magic_link.user_id)
        if not user:
            return None, None
        
        # Mark the magic link as used
        magic_link.is_used = True
        magic_link.used_at = datetime.now(timezone.utc)
        
        # Mark user as verified (since they control the email)
        user.is_verified = True
        
        db.add(magic_link)
        db.add(user)
        await db.commit()
        
        return user, magic_link.redirect_url
    
    @staticmethod
    async def cleanup_expired_links(db: AsyncSession) -> int:
        """
        Clean up all expired magic links from the database.
        
        Returns the number of links deleted.
        """
        cutoff_time = datetime.now(timezone.utc)
        stmt = delete(MagicLink).where(MagicLink.expires_at < cutoff_time)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def cleanup_user_links(db: AsyncSession, user_id: UUID) -> int:
        """
        Clean up all unused magic links for a specific user.
        
        This prevents accumulation of valid tokens when users request
        multiple magic links before using any of them.
        """
        stmt = delete(MagicLink).where(
            MagicLink.user_id == user_id,
            MagicLink.is_used.is_(False)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    
    @staticmethod
    def build_magic_link_url(base_url: str, token: str) -> str:
        """Build the complete magic link URL for email delivery."""
        return f"{base_url}/magic-link/redeem?token={token}"


# Exception classes for better error handling
class MagicLinkError(HTTPException):
    """Base exception for magic link errors."""
    pass


class InvalidTokenError(MagicLinkError):
    """Raised when a magic link token is invalid or expired."""
    
    def __init__(self):
        super().__init__(
            status_code=400,
            detail={
                "error": "invalid_token",
                "message": "The magic link is invalid, expired, or has already been used",
                "action": "Request a new magic link"
            }
        )


class RateLimitError(MagicLinkError):
    """Raised when magic link requests are rate limited."""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": f"Too many magic link requests. Please wait {retry_after} seconds",
                "retry_after": retry_after
            }
        )