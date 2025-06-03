# app/models/user.py
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, String

class User(SQLModel, table=True):  # type: ignore[call-arg]
    id: UUID | None = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, sa_column_kwargs={"unique": True})
    hashed_password: str
    is_active: bool = True
    kyc_status: str = Field(
        default="unverified",
        sa_column=Column(String(20)),
    )
