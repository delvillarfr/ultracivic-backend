"""
Payment Models for Stripe Integration

This module defines the database models for tracking payment intents,
orders, and the progressive payment flow where users authorize payment
before KYC and capture occurs after verification.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Integer, DECIMAL, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.user import Base


class PaymentStatus(str, Enum):
    """Payment status values matching Stripe PaymentIntent statuses."""
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    REQUIRES_CAPTURE = "requires_capture"
    CANCELED = "canceled"
    SUCCEEDED = "succeeded"


class OrderStatus(str, Enum):
    """Order processing status."""
    DRAFT = "draft"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_AUTHORIZED = "payment_authorized"
    KYC_PENDING = "kyc_pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class Order(Base):
    """
    Order tracking for CO2 allowance retirement purchases.
    
    Represents a complete order from payment through allowance retirement
    and token minting. Tracks the multi-step process and maintains state
    across the progressive KYC workflow.
    """
    __tablename__ = "orders"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    
    # Order details
    tonnes_co2: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_usd: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    fee_usd: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    total_usd: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    
    # Token delivery
    eth_address: Mapped[Optional[str]] = mapped_column(String(42), nullable=True)
    tokens_to_mint: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(18, 6), nullable=True)
    
    # Status tracking
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus, name="orderstatus", create_type=False),
        default=OrderStatus.DRAFT
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships (forward references for type checking)
    if False:  # Type checking only
        from app.models.user import User
        user: Mapped["User"] = relationship("User", back_populates="orders")
        payment_intent: Mapped[Optional["PaymentIntent"]] = relationship("PaymentIntent", back_populates="order", uselist=False)


class PaymentIntent(Base):
    """
    Stripe PaymentIntent tracking for manual capture flow.
    
    Stores PaymentIntent details and tracks the authorization → capture flow.
    Links orders to Stripe payment processing with proper status management.
    """
    __tablename__ = "payment_intent"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    
    # Stripe details
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    client_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Payment details
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="paymentstatus", create_type=False),
        nullable=False
    )
    
    # Capture details
    capture_method: Mapped[str] = mapped_column(String(20), default="manual")
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_amount_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(
        "metadata",
        Text,
        nullable=True,
        comment="JSON string stored as text",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="payment_intent")