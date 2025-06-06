"""
Ultra Civic Backend - Main Application Entry Point

This module serves as the central configuration point for the Ultra Civic API.
It assembles authentication, KYC verification, and health monitoring endpoints
into a cohesive FastAPI application using the dependency injection pattern.

The application follows a modular architecture where authentication is handled
by FastAPI-Users v14, KYC verification integrates with Stripe Identity, and
all database operations use async SQLAlchemy with PostgreSQL.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.auth import fastapi_users, auth_backend, current_active_user, current_verified_user, refresh_jwt_token
from app.models.user import User, UserRead, UserCreate
from app.kyc import router as kyc_router

settings = get_settings()
app = FastAPI(title="Ultra Civic Backend")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",  # Local development
        "https://ultracivic.com",  # Production
        "https://frontend-stub.ultracivic.pages.dev",  # Cloudflare Pages preview
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health_check():
    """Simple health check endpoint returning application status."""
    return {"status": "ok"}


app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

@app.post("/auth/jwt/refresh", tags=["auth"])
async def refresh_token(token_data: dict = Depends(refresh_jwt_token)):
    """Refresh JWT access token for authenticated user."""
    return token_data

app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(kyc_router, tags=["kyc"])


@app.get("/me", response_model=UserRead, tags=["auth"])
async def read_me(user: UserRead = Depends(current_active_user)):
    """Return the currently authenticated user's profile information."""
    return user


@app.get("/auth/test-verified", tags=["auth"])
async def test_verified_access(user: User = Depends(current_verified_user)):
    """Test endpoint that requires KYC verification - demonstrates the security gate."""
    return {
        "message": "Access granted - user is KYC verified",
        "user_id": str(user.id),
        "email": user.email,
        "kyc_status": user.kyc_status.value
    }
