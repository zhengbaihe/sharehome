from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.dependencies import ActiveHouseholdMembership, DatabaseSession
from app.domain.splitting import SplitValidationError
from app.models import Bill
from app.schemas.billing import BillCreate, BillRead
from app.services.billing import BillPersistenceError, BillValidationError, create_equal_bill

router = APIRouter(prefix="/households/{household_id}/bills", tags=["bills"])


@router.post("", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def create_bill(
    payload: BillCreate, membership: ActiveHouseholdMembership, session: DatabaseSession
) -> Bill:
    try:
        return create_equal_bill(
            session, household_id=membership.household_id, **payload.model_dump()
        )
    except (BillValidationError, SplitValidationError):
        raise HTTPException(status_code=422, detail="Invalid bill input") from None
    except BillPersistenceError:
        raise HTTPException(status_code=500, detail="Unable to create bill") from None


@router.get("", response_model=list[BillRead])
def list_bills(membership: ActiveHouseholdMembership, session: DatabaseSession) -> list[Bill]:
    """Return bills by paid_at DESC, created_at DESC, then id ASC."""
    statement = (
        select(Bill)
        .where(Bill.household_id == membership.household_id)
        .options(selectinload(Bill.allocations))
        .order_by(Bill.paid_at.desc(), Bill.created_at.desc(), Bill.id)
    )
    return list(session.scalars(statement))


@router.get("/{bill_id}", response_model=BillRead)
def read_bill(
    bill_id: UUID, membership: ActiveHouseholdMembership, session: DatabaseSession
) -> Bill:
    bill = session.scalar(
        select(Bill)
        .where(Bill.id == bill_id, Bill.household_id == membership.household_id)
        .options(selectinload(Bill.allocations))
    )
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill
