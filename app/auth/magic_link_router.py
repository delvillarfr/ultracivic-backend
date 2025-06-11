"""
Magic Link Authentication Endpoints

This module provides the API endpoints for magic link authentication:
- POST /magic-link/request - Request a magic link via email
- GET /magic-link/redeem - Redeem a magic link token and create session

The endpoints handle the complete flow: email validation, token generation,
email delivery, token redemption, and session creation.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.magic_link import MagicLinkService, InvalidTokenError
from app.auth.session import SessionService
from app.core.config import get_settings
from app.core.email import send_magic_link_email
from app.db import get_session
from app.models.magic_link import MagicLinkRequest, MagicLinkResponse

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/magic-link/request", response_model=MagicLinkResponse)
async def request_magic_link(
    magic_link_request: MagicLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_session)
) -> MagicLinkResponse:
    """
    Request a magic link for passwordless authentication.
    
    Creates a user if one doesn't exist, generates a secure magic link,
    and sends it via email. The link expires after 5 minutes.
    """
    try:
        # Get or create user
        user = await MagicLinkService.create_user_if_not_exists(
            db, magic_link_request.email
        )
        
        # Create magic link
        magic_link = await MagicLinkService.create_magic_link(
            db=db,
            user=user,
            request=request,
            redirect_url=magic_link_request.redirect_url
        )
        
        # Build the complete magic link URL
        # Intelligently detect frontend URL based on environment and redirect_url
        if settings.environment.value == "production":
            base_url = "https://ultracivic.com"
        elif magic_link_request.redirect_url and magic_link_request.redirect_url.startswith("http"):
            # Extract base URL from redirect_url provided by frontend
            from urllib.parse import urlparse
            parsed = urlparse(magic_link_request.redirect_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
        elif magic_link_request.redirect_url and "ultracivic.com" in magic_link_request.redirect_url:
            # If redirect URL contains ultracivic.com, use production URL
            base_url = "https://ultracivic.com"
        else:
            # Default to localhost for development
            base_url = "http://localhost:8080"
        
        magic_link_url = MagicLinkService.build_magic_link_url(
            base_url, magic_link.token
        )
        
        # Send magic link email
        await send_magic_link_email(
            email=user.email,
            magic_link_url=magic_link_url,
            expires_in_minutes=5
        )
        
        logger.info(
            "Magic link sent to %s, token: %s", 
            user.email, 
            magic_link.token[:8] + "..."  # Log partial token for debugging
        )
        
        return MagicLinkResponse(
            message="Magic link sent to your email address",
            expires_in_minutes=5
        )
        
    except Exception as e:
        logger.error("Error sending magic link to %s: %s", magic_link_request.email, str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to send magic link. Please try again."
        )


@router.get("/magic-link/redeem")
async def redeem_magic_link(
    token: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Redeem a magic link token and create an authenticated session.
    
    Validates the token, creates a session, sets session cookie,
    and returns user information with optional redirect URL.
    """
    try:
        # Validate and redeem the magic link token
        user, redirect_url = await MagicLinkService.validate_and_redeem_token(
            db=db,
            token=token,
            request=request,
            enforce_ip_binding=False  # Disabled for development, enable in production
        )
        
        if not user:
            raise InvalidTokenError()
        
        # Create a new session
        session = await SessionService.create_session(
            db=db,
            user=user,
            request=request,
            expires_in_days=7  # Session lasts 7 days
        )
        
        # Set session cookie
        is_production = settings.environment.value == "production"
        # Also treat as production if request comes from ultracivic.com
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        is_ultracivic_com = "ultracivic.com" in origin or "ultracivic.com" in referer
        use_secure_cookies = is_production or is_ultracivic_com
        
        SessionService.set_session_cookie(
            response=response,
            session_token=session.session_token,
            secure=use_secure_cookies
        )
        
        logger.info(
            "Setting session cookie - production: %s, ultracivic.com: %s, secure: %s, token: %s",
            is_production,
            is_ultracivic_com,
            use_secure_cookies,
            session.session_token[:8] + "..."
        )
        
        logger.info(
            "Magic link redeemed successfully for user %s, session %s",
            str(user.id),
            session.session_token[:8] + "..."
        )
        
        # Return success response with user info
        response_data = {
            "message": "Authentication successful",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "is_verified": user.is_verified,
                "kyc_status": user.kyc_status.value
            },
            "session": {
                "id": str(session.id),
                "expires_at": session.expires_at.isoformat(),
                "created_at": session.created_at.isoformat()
            }
        }
        
        # Include redirect URL if provided
        if redirect_url:
            response_data["redirect_url"] = redirect_url
        
        return response_data
        
    except InvalidTokenError:
        raise
    except Exception as e:
        logger.error("Error redeeming magic link token %s: %s", token[:8] + "...", str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to redeem magic link. Please try again."
        )


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session)
) -> Dict[str, str]:
    """
    Log out the current user by revoking their session.
    
    Clears the session cookie and removes the session from the database.
    """
    # Get session token from cookie
    session_token = SessionService.get_session_token_from_request(request)
    
    if session_token:
        # Revoke the session in the database
        await SessionService.revoke_session(db, session_token)
        logger.info("Session %s revoked during logout", session_token[:8] + "...")
    
    # Clear session cookie
    is_production = settings.environment.value == "production"
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    is_ultracivic_com = "ultracivic.com" in origin or "ultracivic.com" in referer
    use_secure_cookies = is_production or is_ultracivic_com
    SessionService.clear_session_cookie(response, secure=use_secure_cookies)
    
    return {"message": "Logged out successfully"}


@router.get("/auth/session")
async def get_current_session(
    request: Request,
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Get information about the current session.
    
    Returns session and user details if authenticated, 401 if not.
    """
    session_token = SessionService.get_session_token_from_request(request)
    
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="No active session"
        )
    
    # Get session and user
    session = await SessionService.get_session_by_token(db, session_token)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )
    
    user = await db.get(type(session.user), session.user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )
    
    return {
        "session": {
            "id": str(session.id),
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "last_accessed_at": session.last_accessed_at.isoformat()
        },
        "user": {
            "id": str(user.id),
            "email": user.email,
            "is_verified": user.is_verified,
            "kyc_status": user.kyc_status.value
        }
    }