"""
Payment Processing System using Stripe PaymentIntents

This module implements the progressive payment flow where users authorize
payment first, then complete KYC verification, and payment is captured
only after successful verification.

Key Components:
- Order creation and management
- PaymentIntent creation with manual capture
- Payment status tracking and updates
- Integration with KYC verification flow
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_active_user
from app.core.config import get_settings
from app.db import get_session
from app.models.user import User
from app.models.payment import Order, PaymentIntent, OrderStatus, PaymentStatus

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Stripe
stripe.api_key = settings.stripe_secret.get_secret_value()


class OrderRequest(BaseModel):
    """Request schema for creating a new order."""
    tonnes_co2: int = Field(gt=0, le=1000, description="Number of CO2 tonnes to retire")
    eth_address: Optional[str] = Field(
        None,
        pattern=r"^0x[a-fA-F0-9]{40}$",
        description="Ethereum address for token delivery",
    )


class OrderResponse(BaseModel):
    """Response schema for order operations."""
    order_id: str
    status: OrderStatus
    tonnes_co2: int
    amount_usd: Decimal
    fee_usd: Decimal
    total_usd: Decimal
    eth_address: Optional[str] = None
    tokens_to_mint: Optional[Decimal] = None


class PaymentIntentResponse(BaseModel):
    """Response schema for PaymentIntent creation."""
    client_secret: str
    order_id: str
    amount_cents: int
    status: PaymentStatus


class PaymentService:
    """Service class for payment operations."""
    
    # Pricing configuration
    PRICE_PER_TONNE_USD = Decimal("20.00")  # $20 per tonne
    FEE_PER_ORDER_USD = Decimal("4.00")     # $4 flat fee
    TOKENS_PER_TONNE = Decimal("0.3")       # 0.3 tokens per tonne
    
    @staticmethod
    def calculate_order_amounts(tonnes_co2: int) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate order amounts: (amount, fee, total)."""
        amount = PaymentService.PRICE_PER_TONNE_USD * tonnes_co2
        fee = PaymentService.FEE_PER_ORDER_USD
        total = amount + fee
        return amount, fee, total
    
    @staticmethod
    def calculate_tokens_to_mint(tonnes_co2: int) -> Decimal:
        """Calculate number of tokens to mint for the order."""
        return PaymentService.TOKENS_PER_TONNE * tonnes_co2
    
    @staticmethod
    async def create_order(
        db: AsyncSession,
        user: User,
        tonnes_co2: int,
        eth_address: Optional[str] = None
    ) -> Order:
        """Create a new order for CO2 allowance retirement."""
        amount_usd, fee_usd, total_usd = PaymentService.calculate_order_amounts(tonnes_co2)
        tokens_to_mint = PaymentService.calculate_tokens_to_mint(tonnes_co2) if eth_address else None
        
        order = Order(
            user_id=user.id,
            tonnes_co2=tonnes_co2,
            amount_usd=amount_usd,
            fee_usd=fee_usd,
            total_usd=total_usd,
            eth_address=eth_address,
            tokens_to_mint=tokens_to_mint,
            status=OrderStatus.DRAFT
        )
        
        db.add(order)
        await db.commit()
        await db.refresh(order)
        
        logger.info(
            "Created order %s for user %s: %d tonnes, $%s total",
            str(order.id),
            str(user.id),
            tonnes_co2,
            total_usd
        )
        
        return order
    
    @staticmethod
    async def create_payment_intent(
        db: AsyncSession,
        order: Order,
        user: User
    ) -> PaymentIntent:
        """Create Stripe PaymentIntent with manual capture for the order."""
        amount_cents = int(order.total_usd * 100)
        
        try:
            # Create Stripe PaymentIntent
            stripe_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                capture_method="manual",  # Don't capture until after KYC
                confirmation_method="automatic",
                metadata={
                    "order_id": str(order.id),
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "tonnes_co2": str(order.tonnes_co2),
                },
                description=f"Ultra Civic: {order.tonnes_co2} tonnes CO2 retirement"
            )
            
            # Store PaymentIntent in database
            payment_intent = PaymentIntent(
                order_id=order.id,
                stripe_payment_intent_id=stripe_intent.id,
                client_secret=stripe_intent.client_secret,
                amount_cents=amount_cents,
                currency="usd",
                status=PaymentStatus(stripe_intent.status),
                capture_method="manual",
                description=stripe_intent.description,
                metadata_json=json.dumps(stripe_intent.metadata)
            )
            
            db.add(payment_intent)
            
            # Update order status
            order.status = OrderStatus.PAYMENT_PENDING
            db.add(order)
            
            await db.commit()
            await db.refresh(payment_intent)
            
            logger.info(
                "Created PaymentIntent %s for order %s, amount: $%s",
                stripe_intent.id,
                str(order.id),
                order.total_usd
            )
            
            return payment_intent
            
        except stripe.StripeError as e:
            logger.error("Stripe error creating PaymentIntent: %s", str(e))
            raise HTTPException(
                status_code=500,
                detail="Failed to create payment intent"
            )
    
    @staticmethod
    async def get_order_by_id(db: AsyncSession, order_id: UUID, user_id: UUID) -> Optional[Order]:
        """Get order by ID, ensuring it belongs to the user."""
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def capture_payment_intent(
        db: AsyncSession,
        payment_intent: PaymentIntent,
        amount_cents: Optional[int] = None
    ) -> bool:
        """Capture a previously authorized PaymentIntent."""
        try:
            # Capture payment in Stripe
            capture_amount = amount_cents or payment_intent.amount_cents
            stripe_intent = stripe.PaymentIntent.capture(
                payment_intent.stripe_payment_intent_id,
                amount_to_capture=capture_amount
            )
            
            # Update local record
            payment_intent.status = PaymentStatus(stripe_intent.status)
            payment_intent.captured_at = datetime.now(timezone.utc)
            payment_intent.captured_amount_cents = capture_amount
            
            db.add(payment_intent)
            await db.commit()
            
            logger.info(
                "Captured PaymentIntent %s for amount $%s",
                payment_intent.stripe_payment_intent_id,
                capture_amount / 100
            )
            
            return True
            
        except stripe.StripeError as e:
            logger.error("Stripe error capturing payment: %s", str(e))
            return False


@router.post("/orders", response_model=OrderResponse)
async def create_order(
    order_request: OrderRequest,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session)
) -> OrderResponse:
    """
    Create a new order for CO2 allowance retirement.
    
    Creates an order record and calculates pricing based on the number
    of tonnes requested. Does not create payment intent yet.
    """
    order = await PaymentService.create_order(
        db=db,
        user=user,
        tonnes_co2=order_request.tonnes_co2,
        eth_address=order_request.eth_address
    )
    
    return OrderResponse(
        order_id=str(order.id),
        status=order.status,
        tonnes_co2=order.tonnes_co2,
        amount_usd=order.amount_usd,
        fee_usd=order.fee_usd,
        total_usd=order.total_usd,
        eth_address=order.eth_address,
        tokens_to_mint=order.tokens_to_mint
    )


@router.post("/orders/{order_id}/payment-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    order_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session)
) -> PaymentIntentResponse:
    """
    Create Stripe PaymentIntent for an order with manual capture.
    
    This authorizes payment but does not capture funds until after
    KYC verification is completed.
    """
    # Get order
    order = await PaymentService.get_order_by_id(db, order_id, user.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Order status is {order.status.value}, expected draft"
        )
    
    # Create PaymentIntent
    payment_intent = await PaymentService.create_payment_intent(db, order, user)
    
    return PaymentIntentResponse(
        client_secret=payment_intent.client_secret,
        order_id=str(order.id),
        amount_cents=payment_intent.amount_cents,
        status=payment_intent.status
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session)
) -> OrderResponse:
    """Get order details by ID."""
    order = await PaymentService.get_order_by_id(db, order_id, user.id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return OrderResponse(
        order_id=str(order.id),
        status=order.status,
        tonnes_co2=order.tonnes_co2,
        amount_usd=order.amount_usd,
        fee_usd=order.fee_usd,
        total_usd=order.total_usd,
        eth_address=order.eth_address,
        tokens_to_mint=order.tokens_to_mint
    )


@router.get("/orders")
async def list_orders(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """List all orders for the authenticated user."""
    stmt = select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    result = await db.execute(stmt)
    orders = result.scalars().all()
    
    return {
        "orders": [
            OrderResponse(
                order_id=str(order.id),
                status=order.status,
                tonnes_co2=order.tonnes_co2,
                amount_usd=order.amount_usd,
                fee_usd=order.fee_usd,
                total_usd=order.total_usd,
                eth_address=order.eth_address,
                tokens_to_mint=order.tokens_to_mint
            )
            for order in orders
        ]
    }