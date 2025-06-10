"""
KYC Verification System using Stripe Identity

This module implements end-to-end KYC verification using Stripe Identity.
It provides endpoints for creating verification sessions and handles webhook
events to update user status based on verification results.

The system ensures idempotent webhook processing and maintains audit trails
through session ID tracking.
"""

import json
import logging
import hmac
import hashlib
from typing import Dict, Any
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_active_user, current_verified_user
from app.core.config import get_settings
from app.db import get_session
from app.models.user import User, KYCStatus

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Stripe with the secret key
stripe.api_key = settings.stripe_secret.get_secret_value()


@router.post("/kyc/start")
async def start_kyc_verification(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session)
) -> Dict[str, str]:
    """
    Create a Stripe Identity verification session for the authenticated user.
    
    Returns the URL that the frontend should open for the user to complete
    identity verification. Sets user status to PENDING during verification.
    """
    try:
        # Create Stripe Identity verification session
        session = stripe.identity.VerificationSession.create(
            type="document",
            client_reference_id=str(user.id),
            metadata={
                "user_email": user.email,
                "user_id": str(user.id),
            },
            # Configure for test mode to allow testing
            options={
                "document": {
                    "allowed_types": ["driving_license", "passport", "id_card"],
                    "require_live_capture": False,  # Allow uploads in test mode
                }
            }
        )
        
        # Update user with session ID and set status to PENDING
        user.stripe_verification_session_id = session.id
        user.kyc_status = KYCStatus.pending
        db.add(user)
        await db.commit()
        
        logger.info(
            "Created verification session %s for user %s", 
            session.id, 
            str(user.id)
        )
        
        return {"url": session.url}
        
    except stripe.StripeError as e:
        logger.error("Stripe error creating verification session: %s", str(e))
        raise HTTPException(
            status_code=500, 
            detail="Failed to create verification session"
        )
    except Exception as e:
        logger.error("Unexpected error creating verification session: %s", str(e))
        raise HTTPException(
            status_code=500, 
            detail="Internal server error"
        )


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Stripe webhook signature to ensure request authenticity.
    
    This prevents malicious actors from sending fake webhook events.
    """
    try:
        # Extract timestamp and signature from header
        elements = signature.split(",")
        timestamp = None
        signatures = []
        
        for element in elements:
            if "=" not in element:
                continue
            key, value = element.split("=", 1)
            if key == "t":
                timestamp = value
            elif key.startswith("v"):
                signatures.append(value)
        
        if not timestamp or not signatures:
            return False
        
        # Create expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Verify signature matches
        return any(
            hmac.compare_digest(expected_signature, sig) 
            for sig in signatures
        )
        
    except Exception as e:
        logger.error("Error verifying webhook signature: %s", str(e))
        return False


@router.post("/webhooks/stripe")
async def handle_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    Handle Stripe webhook events for identity verification.
    
    Processes verification session events and updates user KYC status.
    Ensures idempotent processing to handle duplicate events safely.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    
    # Verify webhook signature
    webhook_secret = settings.stripe_webhook_secret.get_secret_value()
    if not verify_webhook_signature(payload, signature, webhook_secret):
        logger.error("Invalid webhook signature received")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    try:
        # Parse the webhook event
        event = stripe.Event.construct_from(
            json.loads(payload.decode('utf-8')),
            stripe.api_key
        )
    except Exception as e:
        logger.error("Error parsing webhook payload: %s", str(e))
        raise HTTPException(status_code=400, detail="Invalid payload")
    
    logger.info("Processing webhook event: %s", event.type)
    
    # Handle verification session events
    if event.type.startswith("identity.verification_session."):
        return await handle_verification_session_event(event, db)
    
    # Return success for unhandled events
    return {"received": True}


async def handle_verification_session_event(
    event: stripe.Event,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Process verification session events and update user status.
    
    Handles verified, requires_input, and canceled events.
    Uses session ID for idempotent processing.
    """
    session_data = event.data.object
    session_id = session_data.id
    
    try:
        # Extract user ID from client_reference_id
        user_id = UUID(session_data.client_reference_id)
    except (ValueError, KeyError, TypeError) as e:
        logger.error("Invalid client_reference_id in webhook: %s", str(e))
        return {"received": True, "error": "invalid_client_reference_id"}
    
    # Find user by ID
    user = await db.get(User, user_id)
    if not user:
        logger.warning("User %s not found for verification session %s", user_id, session_id)
        return {"received": True, "error": "user_not_found"}
    
    # Check if this session was already processed (idempotency)
    if (user.stripe_verification_session_id == session_id and 
        event.type == "identity.verification_session.verified" and
        user.kyc_status == KYCStatus.verified):
        logger.info("Session %s already processed for user %s", session_id, user_id)
        return {"received": True, "status": "already_processed"}
    
    # Update user based on event type
    if event.type == "identity.verification_session.verified":
        logger.info("Verification successful for user %s, session %s", user_id, session_id)
        user.kyc_status = KYCStatus.verified
        user.stripe_verification_session_id = session_id
        status = "verified"
        
    elif event.type == "identity.verification_session.requires_input":
        logger.info("Verification requires input for user %s, session %s", user_id, session_id)
        user.kyc_status = KYCStatus.failed
        user.stripe_verification_session_id = session_id
        status = "requires_input"
        
    elif event.type == "identity.verification_session.canceled":
        logger.info("Verification canceled for user %s, session %s", user_id, session_id)
        user.kyc_status = KYCStatus.unverified
        user.stripe_verification_session_id = session_id
        status = "canceled"
        
    else:
        logger.info("Unhandled verification session event: %s", event.type)
        return {"received": True, "status": "unhandled"}
    
    # Save changes to database
    db.add(user)
    await db.commit()
    
    logger.info(
        "Updated user %s KYC status to %s for session %s", 
        user_id, 
        status,
        session_id
    )
    
    return {
        "received": True,
        "status": status,
        "user_id": str(user_id),
        "kyc_status": status
    }


@router.get("/kyc/verified-only")
async def verified_only_endpoint(user: User = Depends(current_verified_user)):
    """Test endpoint demonstrating KYC verification requirement."""
    return {
        "message": "Success! You are a verified user.",
        "user_id": str(user.id),
        "email": user.email,
        "kyc_status": user.kyc_status.value,
        "session_id": user.stripe_verification_session_id
    }