# app/main.py
from fastapi import FastAPI, Depends
from app.core.config import get_settings
from app.auth import fastapi_users, auth_backend, current_active_user
from app.models.user import UserRead, UserCreate
from app.kyc import router as kyc_router

settings = get_settings()
app = FastAPI(title="Ultra Civic Backend")

# ─────────────────────────────────────────────────────────────
# Meta / health
# ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────
# Auth routers (FastAPI-Users v14)
# ─────────────────────────────────────────────────────────────
# 1) Register  → needs UserRead (response) and UserCreate (request)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

# 2) JWT login/logout → needs backend + response schema
app.include_router(
    fastapi_users.get_auth_router(auth_backend, UserRead),
    prefix="/auth/jwt",
    tags=["auth"],
)

# 3) Forgot-/reset-password → no schema args needed in v14
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

# Include KYC routes
app.include_router(kyc_router, tags=["kyc"])


# ─────────────────────────────────────────────────────────────
# Example protected endpoint
# ─────────────────────────────────────────────────────────────
@app.get("/me", response_model=UserRead, tags=["auth"])
async def read_me(user: UserRead = Depends(current_active_user)):
    return user
