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
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_active_user, current_verified_user
from app.core.config import get_settings
from app.db import get_session
from app.models.user import User, KYCStatus
from app.models.payment import Order, PaymentIntent, OrderStatus, PaymentStatus

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Stripe with the secret key
stripe.api_key = settings.stripe_secret.get_secret_value()


@router.post("/kyc/start")
async def start_kyc_verification(
    request: Request,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session)
) -> Dict[str, str]:
    """
    Create a Stripe Identity verification session for the authenticated user.
    
    Returns the URL that the frontend should open for the user to complete
    identity verification. Sets user status to PENDING during verification.
    """
    try:
        # Determine return URL based on request origin
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        
        if "ultracivic.com" in origin:
            return_url = "https://ultracivic.com/dashboard.html"
        elif "ultracivic.com" in referer:
            return_url = "https://ultracivic.com/dashboard.html"
        elif "localhost" in origin:
            return_url = "http://localhost:8080/dashboard.html"
        else:
            return_url = "https://ultracivic.com/dashboard.html"  # Default to production
        
        logger.info("Using return URL: %s for origin: %s", return_url, origin)
        
        # Create Stripe Identity verification session
        session = stripe.identity.VerificationSession.create(
            type="document",
            client_reference_id=str(user.id),
            metadata={
                "user_email": user.email,
                "user_id": str(user.id),
            },
            return_url=return_url,
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


async def capture_user_payments(db: AsyncSession, user: User) -> None:
    """
    Capture all authorized payments for a user after KYC verification.
    
    Finds all orders with PAYMENT_AUTHORIZED status and captures the
    associated PaymentIntents, then updates order status to PROCESSING.
    """
    try:
        # Find all orders with authorized payments
        stmt = select(Order).where(
            Order.user_id == user.id,
            Order.status == OrderStatus.PAYMENT_AUTHORIZED
        )
        result = await db.execute(stmt)
        orders = result.scalars().all()
        
        for order in orders:
            # Get associated PaymentIntent
            stmt = select(PaymentIntent).where(
                PaymentIntent.order_id == order.id,
                PaymentIntent.status == PaymentStatus.REQUIRES_CAPTURE
            )
            result = await db.execute(stmt)
            payment_intent = result.scalar_one_or_none()
            
            if payment_intent:
                # Capture the payment
                try:
                    stripe_intent = stripe.PaymentIntent.capture(
                        payment_intent.stripe_payment_intent_id
                    )
                    
                    # Update payment intent status
                    payment_intent.status = PaymentStatus(stripe_intent.status)
                    payment_intent.captured_at = datetime.now(timezone.utc)
                    payment_intent.captured_amount_cents = payment_intent.amount_cents
                    
                    # Update order status to processing
                    order.status = OrderStatus.PROCESSING
                    
                    db.add(payment_intent)
                    db.add(order)
                    
                    logger.info(
                        "Captured payment %s for order %s after KYC verification",
                        payment_intent.stripe_payment_intent_id,
                        str(order.id)
                    )
                    
                except stripe.StripeError as e:
                    logger.error(
                        "Failed to capture payment %s: %s", 
                        payment_intent.stripe_payment_intent_id,
                        str(e)
                    )
                    # Mark order as failed
                    order.status = OrderStatus.FAILED
                    db.add(order)
        
        await db.commit()
        
    except Exception as e:
        logger.error("Error capturing user payments after KYC: %s", str(e))
        await db.rollback()


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
    
    # Handle payment intent events
    if event.type.startswith("payment_intent."):
        return await handle_payment_intent_event(event, db)
    
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
        
        # Capture any authorized payments for this user
        await capture_user_payments(db, user)
        
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


async def handle_payment_intent_event(
    event: stripe.Event,
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Handle PaymentIntent webhook events to update order status.
    
    Updates order status based on payment authorization and capture events.
    """
    payment_intent_data = event.data.object
    payment_intent_id = payment_intent_data.id
    
    try:
        # Find PaymentIntent record
        stmt = select(PaymentIntent).where(
            PaymentIntent.stripe_payment_intent_id == payment_intent_id
        )
        result = await db.execute(stmt)
        payment_intent = result.scalar_one_or_none()
        
        if not payment_intent:
            logger.warning("PaymentIntent %s not found in database", payment_intent_id)
            return {"received": True, "error": "payment_intent_not_found"}
        
        # Update payment intent status
        old_status = payment_intent.status
        payment_intent.status = PaymentStatus(payment_intent_data.status)
        
        # Get associated order
        order = await db.get(Order, payment_intent.order_id)
        if not order:
            logger.warning("Order %s not found for PaymentIntent %s", payment_intent.order_id, payment_intent_id)
            return {"received": True, "error": "order_not_found"}
        
        # Update order status based on payment status
        if event.type == "payment_intent.requires_capture":
            # Payment authorized, waiting for capture
            order.status = OrderStatus.PAYMENT_AUTHORIZED
            logger.info("Payment authorized for order %s", str(order.id))
            
        elif event.type == "payment_intent.succeeded":
            # Payment captured successfully
            order.status = OrderStatus.PROCESSING
            payment_intent.captured_at = datetime.now(timezone.utc)
            logger.info("Payment captured for order %s", str(order.id))
            
        elif event.type == "payment_intent.canceled":
            # Payment canceled
            order.status = OrderStatus.CANCELED
            logger.info("Payment canceled for order %s", str(order.id))
            
        elif event.type == "payment_intent.payment_failed":
            # Payment failed
            order.status = OrderStatus.FAILED
            logger.info("Payment failed for order %s", str(order.id))
        
        # Save changes
        db.add(payment_intent)
        db.add(order)
        await db.commit()
        
        logger.info(
            "Updated PaymentIntent %s status: %s → %s, Order %s status: %s",
            payment_intent_id,
            old_status.value if old_status else "None",
            payment_intent.status.value,
            str(order.id),
            order.status.value
        )
        
        return {
            "received": True,
            "payment_intent_id": payment_intent_id,
            "order_id": str(order.id),
            "status": payment_intent.status.value
        }
        
    except Exception as e:
        logger.error("Error handling PaymentIntent event %s: %s", payment_intent_id, str(e))
        return {"received": True, "error": str(e)}


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