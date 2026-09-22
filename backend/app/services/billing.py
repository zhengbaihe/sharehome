from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.splitting import SplitValidationError, split_equal
from app.models import (
    Allocation,
    Bill,
    Household,
    HouseholdMembership,
    MembershipStatus,
    SplitMethod,
)


class BillValidationError(ValueError):
    """Bill input or household membership is not eligible for creation."""


class BillPersistenceError(RuntimeError):
    """The bill and its allocations could not be saved."""


def create_equal_bill(
    session: Session,
    *,
    household_id: UUID,
    payer_membership_id: UUID,
    amount_minor: int,
    participant_membership_ids: Sequence[UUID],
    description: str,
    paid_at: datetime,
) -> Bill:
    """Create one paid EQUAL bill, committing or rolling back this unit of work.

    Use a request-scoped session without unrelated pending writes. Existing read
    transactions are supported. Caller authorization belongs outside this service.
    Amount/participant split errors retain the domain's SplitValidationError.
    """
    try:
        try:
            household_id = UUID(str(household_id))
            payer_membership_id = UUID(str(payer_membership_id))
            participant_keys = [str(UUID(str(value))) for value in participant_membership_ids]
        except (ValueError, TypeError):
            raise BillValidationError("Household and membership IDs must be valid UUIDs") from None
        shares = split_equal(amount_minor, participant_keys)
        if amount_minor > 2**63 - 1:
            raise BillValidationError("amount_minor exceeds the database integer range")
        if not isinstance(description, str) or not description.strip() or len(description) > 255:
            raise BillValidationError("description must contain 1 to 255 characters")
        if not isinstance(paid_at, datetime) or paid_at.utcoffset() is None:
            raise BillValidationError("paid_at must be a timezone-aware datetime")
        participant_ids = [UUID(key) for key in shares]

        if session.scalar(select(Household.id).where(Household.id == household_id)) is None:
            raise BillValidationError("Household not found")
        eligible_ids = set(
            session.scalars(
                select(HouseholdMembership.id)
                .where(
                    HouseholdMembership.household_id == household_id,
                    HouseholdMembership.status == MembershipStatus.ACTIVE,
                    HouseholdMembership.id.in_([payer_membership_id, *participant_ids]),
                )
                .with_for_update()
            )
        )
        if payer_membership_id not in eligible_ids:
            raise BillValidationError("Payer is not eligible for this household")
        if any(member_id not in eligible_ids for member_id in participant_ids):
            raise BillValidationError(
                "One or more participants are not eligible for this household"
            )

        bill = Bill(
            household_id=household_id,
            payer_membership_id=payer_membership_id,
            amount_minor=amount_minor,
            description=description,
            paid_at=paid_at,
            split_method=SplitMethod.EQUAL,
            allocations=[
                Allocation(membership_id=UUID(member_id), amount_minor=share)
                for member_id, share in shares.items()
            ],
        )
        session.add(bill)
        session.commit()
    except (BillValidationError, SplitValidationError):
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise BillPersistenceError("Unable to save bill and allocations") from None

    session.refresh(bill)
    session.refresh(bill, attribute_names=["allocations"])
    return bill
