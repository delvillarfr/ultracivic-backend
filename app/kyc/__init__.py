from fastapi import APIRouter, Depends, HTTPException, Request
from uuid import UUID
import stripe

from app.core.config import get_settings
from app.auth import current_active_user
from app.models.user import User
from app.db import get_session

router = APIRouter()
settings = get_settings()
stripe.api_key = settings.stripe_secret     # 🔑

# ---------- 1. kick-off verification ----------------------------------
@router.post("/kyc/start")
async def start_kyc(user: User = Depends(current_active_user)):
    """
    Return a one-time redirect URL where the logged-in user
    completes Stripe’s ID flow.
    """
    session = stripe.identity.VerificationSession.create(
        type="document",
        client_reference_id=str(user.id),      # we’ll get this back in the webhook
        metadata={"email": user.email},
    )
    return {"url": session.url}

# ---------- 2. receive webhook when verification succeeds -------------
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig     = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="invalid signature")

    if event["type"] == "identity.verification_session.verified":
        session = event["data"]["object"]
        user_id = UUID(session["client_reference_id"])

        async with get_session() as db:
            user = await db.get(User, user_id)
            if user:
                user.kyc_status = "verified"
                db.add(user)
                await db.commit()

    return {"received": True}

