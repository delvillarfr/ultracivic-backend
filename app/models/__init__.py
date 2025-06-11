from .user import User  # noqa: F401  → registers the table with SQLModel
from .magic_link import MagicLink  # noqa: F401
from .session import Session  # noqa: F401
from .payment import Order, PaymentIntent  # noqa: F401

# Configure relationships after all models are imported
from sqlalchemy.orm import relationship

User.magic_links = relationship(
    "MagicLink",
    back_populates="user",
    cascade="all, delete-orphan"
)

User.sessions = relationship(
    "Session",
    back_populates="user",
    cascade="all, delete-orphan"
)

# Payment relationships
User.orders = relationship(
    "Order",
    back_populates="user",
    cascade="all, delete-orphan",
)

Order.user = relationship(
    "User",
    back_populates="orders",
)

Order.payment_intent = relationship(
    "PaymentIntent",
    back_populates="order",
    uselist=False,
)
