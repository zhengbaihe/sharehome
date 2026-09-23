from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Allocation, Bill, HouseholdMembership, MembershipRole, MembershipStatus, User


class BalanceReadError(RuntimeError):
    """Persisted household balances could not be read."""


@dataclass(frozen=True)
class MembershipBalance:
    membership_id: UUID
    user_id: UUID
    display_name: str
    role: MembershipRole
    status: MembershipStatus
    paid_minor: int
    allocated_minor: int
    balance_minor: int


def get_household_balances(session: Session, *, household_id: UUID) -> list[MembershipBalance]:
    """Read persisted balances, including departed members, without committing or writing.

    Caller authorization belongs outside this service. Order is joined_at ASC, id ASC.
    Aggregate payments and allocations separately to avoid multiplying either total.
    """
    paid = (
        select(
            Bill.payer_membership_id.label("membership_id"),
            func.sum(Bill.amount_minor).label("total"),
        )
        .where(Bill.household_id == household_id)
        .group_by(Bill.payer_membership_id)
        .subquery()
    )
    allocated = (
        select(Allocation.membership_id, func.sum(Allocation.amount_minor).label("total"))
        .join(Bill, Bill.id == Allocation.bill_id)
        .where(Bill.household_id == household_id)
        .group_by(Allocation.membership_id)
        .subquery()
    )
    statement = (
        select(
            HouseholdMembership.id.label("membership_id"),
            HouseholdMembership.user_id,
            User.display_name,
            HouseholdMembership.role,
            HouseholdMembership.status,
            func.coalesce(paid.c.total, 0).label("paid_minor"),
            func.coalesce(allocated.c.total, 0).label("allocated_minor"),
        )
        .join(User, User.id == HouseholdMembership.user_id)
        .outerjoin(paid, paid.c.membership_id == HouseholdMembership.id)
        .outerjoin(allocated, allocated.c.membership_id == HouseholdMembership.id)
        .where(HouseholdMembership.household_id == household_id)
        .order_by(HouseholdMembership.joined_at, HouseholdMembership.id)
        .execution_options(autoflush=False)
    )
    try:
        rows = session.execute(statement).mappings().all()
    except SQLAlchemyError:
        raise BalanceReadError("Unable to read household balances") from None
    results = []
    for row in rows:
        values = dict(row)
        # PostgreSQL SUM(bigint) is exact numeric; return Python integers, without a float step.
        values["paid_minor"] = int(values["paid_minor"])
        values["allocated_minor"] = int(values["allocated_minor"])
        results.append(
            MembershipBalance(
                **values, balance_minor=values["paid_minor"] - values["allocated_minor"]
            )
        )
    return results
