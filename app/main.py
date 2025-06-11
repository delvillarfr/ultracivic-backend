"""
Ultra Civic Backend - Main Application Entry Point

This module serves as the central configuration point for the Ultra Civic API.
It assembles magic-link authentication, KYC verification, and health monitoring 
endpoints into a cohesive FastAPI application using the dependency injection pattern.

The application follows a modular architecture where authentication is handled
by magic links with session-based state, KYC verification integrates with 
Stripe Identity, and all database operations use async SQLAlchemy with PostgreSQL.
"""

from datetime import datetime, timezone
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.auth.dependencies import current_active_user, current_verified_user
from app.auth.magic_link_router import router as magic_link_router
from app.models.user import User
from app.kyc import router as kyc_router
from app.payments import router as payments_router

settings = get_settings()
app = FastAPI(title="Ultra Civic Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",  # Local development (frontend-stub)
        "http://localhost:3000",  # Local development (main website)
        "https://ultracivic.com",  # Production website
        "https://frontend-stub.ultracivic.pages.dev",  # Cloudflare Pages preview
        "https://ultracivic-backend.onrender.com",  # Render backend (for API docs)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health_check():
    """Simple health check endpoint returning application status."""
    return {
        "status": "ok",
        "environment": settings.environment.value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Include magic-link authentication routes
app.include_router(magic_link_router, tags=["auth"])

app.include_router(kyc_router, tags=["kyc"])

app.include_router(payments_router, tags=["payments"])


@app.get("/me", tags=["auth"])
async def read_me(user: User = Depends(current_active_user)):
    """Return the currently authenticated user's profile information."""
    return {
        "id": str(user.id),
        "email": user.email,
        "is_verified": user.is_verified,
        "is_active": user.is_active,
        "kyc_status": user.kyc_status.value,
        "stripe_verification_session_id": user.stripe_verification_session_id
    }


@app.get("/auth/test-verified", tags=["auth"])
async def test_verified_access(user: User = Depends(current_verified_user)):
    """Test endpoint that requires KYC verification - demonstrates the security gate."""
    return {
        "message": "Access granted - user is KYC verified",
        "user_id": str(user.id),
        "email": user.email,
        "kyc_status": user.kyc_status.value
    }
