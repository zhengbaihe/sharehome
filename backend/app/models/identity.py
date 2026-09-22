from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.billing import Allocation, Bill


class MembershipRole(str, Enum):
    OWNER = "OWNER"
    MEMBER = "MEMBER"


class MembershipStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPARTED = "DEPARTED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "email = lower(btrim(email)) AND email <> ''", name="ck_users_email_normalized"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320))
    # Callers must supply an already-computed password hash, never a plaintext password.
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    memberships: Mapped[list[HouseholdMembership]] = relationship(
        back_populates="user", passive_deletes="all"
    )

    @validates("email")
    def normalize_email(self, key: str, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email cannot be empty")
        return normalized


class Household(TimestampMixin, Base):
    __tablename__ = "households"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="MYR", server_default="MYR")
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Kuala_Lumpur", server_default="Asia/Kuala_Lumpur"
    )
    memberships: Mapped[list[HouseholdMembership]] = relationship(
        back_populates="household", passive_deletes="all"
    )

    bills: Mapped[list[Bill]] = relationship(back_populates="household", passive_deletes="all")


class HouseholdMembership(TimestampMixin, Base):
    __tablename__ = "household_memberships"
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_memberships_household_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households.id", name="fk_household_memberships_household_id")
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", name="fk_household_memberships_user_id"), index=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        SqlEnum(
            MembershipRole,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="ck_membership_role",
        ),
        default=MembershipRole.MEMBER,
        server_default="MEMBER",
    )
    status: Mapped[MembershipStatus] = mapped_column(
        SqlEnum(
            MembershipStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="ck_membership_status",
        ),
        default=MembershipStatus.ACTIVE,
        server_default="ACTIVE",
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship(back_populates="memberships")
    household: Mapped[Household] = relationship(back_populates="memberships")
    paid_bills: Mapped[list[Bill]] = relationship(
        back_populates="payer_membership", passive_deletes="all"
    )
    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="membership", passive_deletes="all"
    )
