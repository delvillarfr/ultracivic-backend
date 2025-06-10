from .user import User  # noqa: F401  → registers the table with SQLModel
from .magic_link import MagicLink  # noqa: F401
from .session import Session  # noqa: F401

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
