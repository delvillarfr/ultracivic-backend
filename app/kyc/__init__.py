"""
Know Your Customer (KYC) Verification System

This module implements identity verification using Stripe Identity, allowing
users to upload government-issued identification documents for verification.
The system handles the complete verification workflow from initiation through
webhook processing to status updates.

The implementation follows security best practices for webhook validation
and provides idempotent operations to handle duplicate webhook events gracefully.
"""

import logging
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth import current_active_user, current_verified_user
from app.core.config import get_settings
from app.db import get_session
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()
stripe.api_key = settings.stripe_secret.get_secret_value()


@router.post("/kyc/start")
async def start_kyc(user: User = Depends(current_active_user)):
    """Create Stripe Identity verification session for authenticated user."""
    session = stripe.identity.VerificationSession.create(
        type="document",
        client_reference_id=str(user.id),
        metadata={"email": user.email},
    )
    return {"url": session.url}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db=Depends(get_session)):
    """Process Stripe webhook events for identity verification completion."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
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

        user_id_str = str(user.id)

        if user.kyc_status == "verified":
            logger.info("User %s already verified, skipping update", user_id_str)
            return {"received": True, "status": "already_verified"}

        user.kyc_status = "verified"
        db.add(user)
        await db.commit()
        logger.info("User %s marked as verified", user_id_str)
        
        return {"received": True, "status": "updated"}

    return {"received": True}


@router.get("/kyc/verified-only")
async def verified_only_endpoint(user: User = Depends(current_verified_user)):
    """Test endpoint accessible only to KYC-verified users."""
    return {
        "message": "Success! You are a verified user.",
        "user_id": str(user.id),
        "email": user.email,
        "kyc_status": user.kyc_status
    }