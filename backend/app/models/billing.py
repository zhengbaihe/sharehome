from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.identity import Household, HouseholdMembership, TimestampMixin


class SplitMethod(str, Enum):
    EQUAL = "EQUAL"


class Bill(TimestampMixin, Base):
    __tablename__ = "bills"
    __table_args__ = (CheckConstraint("amount_minor > 0", name="ck_bills_amount_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("households.id", name="fk_bills_household_id"), index=True
    )
    payer_membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_memberships.id", name="fk_bills_payer_membership_id"), index=True
    )
    description: Mapped[str] = mapped_column(String(255))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    split_method: Mapped[SplitMethod] = mapped_column(
        SqlEnum(
            SplitMethod,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="ck_bills_split_method",
        ),
        default=SplitMethod.EQUAL,
        server_default="EQUAL",
    )
    household: Mapped[Household] = relationship(back_populates="bills")
    payer_membership: Mapped[HouseholdMembership] = relationship(back_populates="paid_bills")
    allocations: Mapped[list[Allocation]] = relationship(
        back_populates="bill", passive_deletes="all"
    )


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="ck_allocations_amount_nonnegative"),
        UniqueConstraint("bill_id", "membership_id", name="uq_allocations_bill_membership"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    bill_id: Mapped[UUID] = mapped_column(ForeignKey("bills.id", name="fk_allocations_bill_id"))
    membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("household_memberships.id", name="fk_allocations_membership_id"), index=True
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    bill: Mapped[Bill] = relationship(back_populates="allocations")
    membership: Mapped[HouseholdMembership] = relationship(back_populates="allocations")
