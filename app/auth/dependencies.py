"""
Authentication Dependencies for Session-Based Auth

This module provides FastAPI dependencies for session-based authentication
to replace the JWT-based FastAPI-Users dependencies. It includes:

- current_user: Get current authenticated user
- current_active_user: Ensure user is active  
- current_verified_user: Ensure user is KYC verified
- optional_user: Get user if authenticated, None otherwise

All dependencies use session cookies instead of JWT Bearer tokens.
"""

from typing import Optional

from fastapi import Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import SessionService, SessionRequiredError, InvalidSessionError
from app.db import get_session
from app.models.user import User, KYCStatus


async def current_user(
    request: Request,
    db: AsyncSession = Depends(get_session)
) -> User:
    """
    Get the current authenticated user from session.
    
    Raises 401 if no valid session is found.
    """
    session_token = SessionService.get_session_token_from_request(request)
    
    if not session_token:
        raise SessionRequiredError()
    
    user = await SessionService.get_user_by_session_token(db, session_token)
    
    if not user:
        raise InvalidSessionError()
    
    return user


async def current_active_user(
    user: User = Depends(current_user)
) -> User:
    """
    Get the current authenticated user, ensuring they are active.
    
    Raises 401 if not authenticated, 403 if user is inactive.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "inactive_user",
                "message": "Your account has been deactivated",
                "action": "Contact support for assistance"
            }
        )
    
    return user


async def current_verified_user(
    user: User = Depends(current_active_user)
) -> User:
    """
    Get the current authenticated user, ensuring they are KYC verified.
    
    This creates a security gate for sensitive operations requiring identity verification.
    Raises 401 if not authenticated, 403 if user is inactive or not KYC verified.
    """
    if user.kyc_status != KYCStatus.verified:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "kyc_verification_required",
                "message": "This operation requires identity verification",
                "kyc_status": user.kyc_status.value,
                "action": "Complete KYC verification to access this resource"
            }
        )
    
    return user


async def optional_user(
    request: Request,
    db: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """
    Get the current user if authenticated, None otherwise.
    
    This dependency never raises authentication errors - it returns None
    for unauthenticated requests. Useful for endpoints that work with
    or without authentication.
    """
    try:
        session_token = SessionService.get_session_token_from_request(request)
        
        if not session_token:
            return None
        
        user = await SessionService.get_user_by_session_token(db, session_token)
        return user
    
    except Exception:
        # Any error getting user returns None
        return None


async def require_admin_user(
    user: User = Depends(current_active_user)
) -> User:
    """
    Get the current authenticated user, ensuring they are a superuser.
    
    Raises 401 if not authenticated, 403 if user is not an admin.
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "admin_required", 
                "message": "This operation requires administrator privileges",
                "action": "Contact an administrator for access"
            }
        )
    
    return user