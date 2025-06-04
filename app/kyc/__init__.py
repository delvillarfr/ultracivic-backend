from fastapi import APIRouter, Depends, HTTPException, Request
from uuid import UUID
import logging
import stripe

from app.core.config import get_settings
from app.auth import current_active_user, current_verified_user
from app.models.user import User
from app.db import get_session

router = APIRouter()
logger = logging.getLogger(__name__)
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
async def stripe_webhook(request: Request, db = Depends(get_session)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid Stripe webhook signature")
        raise HTTPException(status_code=400, detail="invalid signature")
    except Exception as e:
        logger.error("Error parsing Stripe webhook: %s", str(e))
        raise HTTPException(status_code=400, detail="invalid payload")

    logger.info("Received Stripe webhook event: %s", event["type"])

    if event["type"] == "identity.verification_session.verified":
        session = event["data"]["object"]
        
        try:
            user_id = UUID(session["client_reference_id"])
        except (ValueError, KeyError, TypeError) as e:
            logger.error("Invalid client_reference_id in webhook: %s", str(e))
            return {"received": True, "error": "invalid client_reference_id"}

        user = await db.get(User, user_id)
        if not user:
            logger.warning("User not found for ID: %s", user_id)
            return {"received": True, "error": "user not found"}

        # Store user.id before any async operations to avoid lazy loading issues
        user_id_str = str(user.id)

        # Idempotency check - if already verified, don't update
        if user.kyc_status == "verified":
            logger.info("User %s already verified, skipping update", user_id_str)
            return {"received": True, "status": "already_verified"}

        user.kyc_status = "verified"
        db.add(user)
        await db.commit()
        logger.info("User %s marked as verified", user_id_str)
        
        return {"received": True, "status": "updated"}

    return {"received": True}

# ---------- 3. test endpoint for verified users only ---------------------
@router.get("/kyc/verified-only")
async def verified_only_endpoint(user: User = Depends(current_verified_user)):
    """
    Test endpoint that is only accessible to KYC-verified users.
    Returns 403 if user is not verified.
    """
    return {
        "message": "Success! You are a verified user.",
        "user_id": str(user.id),
        "email": user.email,
        "kyc_status": user.kyc_status
    }

