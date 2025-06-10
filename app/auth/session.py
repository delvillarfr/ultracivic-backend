"""
Session Management Service

This module provides session-based authentication to replace JWT tokens.
Sessions are server-side stored and provide better security control,
immediate revocation, and detailed access tracking.

Features:
- Secure session token generation
- Automatic session expiration and cleanup
- IP address and User-Agent tracking
- Session extension and revocation
- Database-backed session storage
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import Request, Response, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.session import Session


class SessionService:
    """Service class for session management operations."""
    
    SESSION_COOKIE_NAME = "ultracivic_session"
    SESSION_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate a cryptographically secure session token."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))
    
    @staticmethod
    async def create_session(
        db: AsyncSession,
        user: User,
        request: Request,
        expires_in_days: int = 7
    ) -> Session:
        """
        Create a new session for the given user.
        
        Automatically cleans up any expired sessions for the user
        to prevent accumulation of stale sessions.
        """
        # Clean up expired sessions for this user
        await SessionService.cleanup_user_sessions(db, user.id)
        
        # Generate secure session token
        session_token = SessionService.generate_session_token()
        
        # Extract client information
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Create new session
        session = Session(
            session_token=session_token,
            user_id=user.id,
            ip_address=client_ip,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        return session
    
    @staticmethod
    async def get_session_by_token(
        db: AsyncSession,
        session_token: str,
        touch: bool = True
    ) -> Optional[Session]:
        """
        Get session by token and optionally update last_accessed_at.
        
        Returns None if session doesn't exist, is expired, or inactive.
        """
        stmt = select(Session).where(Session.session_token == session_token)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        # Check if session is valid
        if not session.is_valid:
            # Clean up invalid session
            await db.delete(session)
            await db.commit()
            return None
        
        # Update last accessed time
        if touch:
            session.touch()
            db.add(session)
            await db.commit()
        
        return session
    
    @staticmethod
    async def get_user_by_session_token(
        db: AsyncSession,
        session_token: str
    ) -> Optional[User]:
        """Get user associated with a session token."""
        session = await SessionService.get_session_by_token(db, session_token)
        if not session:
            return None
        
        return await db.get(User, session.user_id)
    
    @staticmethod
    def set_session_cookie(
        response: Response,
        session_token: str,
        secure: bool = True
    ) -> None:
        """Set session cookie in the response."""
        response.set_cookie(
            key=SessionService.SESSION_COOKIE_NAME,
            value=session_token,
            max_age=SessionService.SESSION_COOKIE_MAX_AGE,
            httponly=True,  # Prevent XSS
            secure=secure,  # HTTPS only in production
            samesite="lax"  # CSRF protection
        )
    
    @staticmethod
    def get_session_token_from_request(request: Request) -> Optional[str]:
        """Extract session token from request cookie."""
        return request.cookies.get(SessionService.SESSION_COOKIE_NAME)
    
    @staticmethod
    def clear_session_cookie(response: Response) -> None:
        """Clear session cookie from the response."""
        response.delete_cookie(
            key=SessionService.SESSION_COOKIE_NAME,
            httponly=True,
            secure=True,
            samesite="lax"
        )
    
    @staticmethod
    async def revoke_session(
        db: AsyncSession,
        session_token: str
    ) -> bool:
        """
        Revoke (delete) a specific session.
        
        Returns True if session was found and revoked, False otherwise.
        """
        stmt = select(Session).where(Session.session_token == session_token)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            await db.delete(session)
            await db.commit()
            return True
        
        return False
    
    @staticmethod
    async def revoke_all_user_sessions(
        db: AsyncSession,
        user_id: UUID
    ) -> int:
        """
        Revoke all sessions for a user.
        
        Returns the number of sessions revoked.
        """
        stmt = delete(Session).where(Session.user_id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """
        Clean up all expired sessions from the database.
        
        Returns the number of sessions deleted.
        """
        cutoff_time = datetime.now(timezone.utc)
        stmt = delete(Session).where(Session.expires_at < cutoff_time)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def cleanup_user_sessions(
        db: AsyncSession,
        user_id: UUID,
        keep_active: bool = True
    ) -> int:
        """
        Clean up sessions for a specific user.
        
        If keep_active=True, only removes expired/inactive sessions.
        If keep_active=False, removes all sessions for the user.
        """
        if keep_active:
            # Only remove expired or inactive sessions
            cutoff_time = datetime.now(timezone.utc)
            stmt = delete(Session).where(
                Session.user_id == user_id,
                (Session.expires_at < cutoff_time) | (Session.is_active.is_(False))
            )
        else:
            # Remove all sessions
            stmt = delete(Session).where(Session.user_id == user_id)
        
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def extend_session(
        db: AsyncSession,
        session_token: str,
        days: int = 7
    ) -> bool:
        """
        Extend session expiration by the given number of days.
        
        Returns True if session was found and extended, False otherwise.
        """
        session = await SessionService.get_session_by_token(db, session_token, touch=False)
        if not session:
            return False
        
        session.extend_expiration(days)
        db.add(session)
        await db.commit()
        return True


# Exception classes for session errors
class SessionError(HTTPException):
    """Base exception for session errors."""
    pass


class InvalidSessionError(SessionError):
    """Raised when a session is invalid or expired."""
    
    def __init__(self):
        super().__init__(
            status_code=401,
            detail={
                "error": "invalid_session",
                "message": "Your session is invalid or has expired",
                "action": "Please log in again"
            }
        )


class SessionRequiredError(SessionError):
    """Raised when authentication is required but no session is present."""
    
    def __init__(self):
        super().__init__(
            status_code=401,
            detail={
                "error": "authentication_required",
                "message": "Authentication is required to access this resource",
                "action": "Please log in"
            }
        )