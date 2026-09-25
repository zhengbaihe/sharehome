from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import ActiveHouseholdMembership, CurrentUser, DatabaseSession
from app.models import Household, HouseholdMembership, MembershipRole, MembershipStatus, User
from app.schemas.household import HouseholdCreate, HouseholdMemberRead, HouseholdRead

router = APIRouter(prefix="/households", tags=["households"])


@router.post("", response_model=HouseholdRead, status_code=status.HTTP_201_CREATED)
def create_household(
    payload: HouseholdCreate, user: CurrentUser, session: DatabaseSession
) -> Household:
    household = Household(name=payload.name)
    session.add(
        HouseholdMembership(
            household=household,
            user_id=user.id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    try:
        # The relationship inserts both rows in the same transaction.
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(status_code=500, detail="Unable to create household") from None
    session.refresh(household)
    return household


@router.get("", response_model=list[HouseholdRead])
def list_households(user: CurrentUser, session: DatabaseSession) -> list[Household]:
    statement = (
        select(Household)
        .join(HouseholdMembership)
        .where(
            HouseholdMembership.user_id == user.id,
            HouseholdMembership.status == MembershipStatus.ACTIVE,
        )
        .order_by(Household.created_at, Household.id)
    )
    return list(session.scalars(statement))


@router.get("/{household_id}", response_model=HouseholdRead)
def read_household(membership: ActiveHouseholdMembership) -> Household:
    return membership.household


@router.get("/{household_id}/members", response_model=list[HouseholdMemberRead])
def list_household_members(
    membership: ActiveHouseholdMembership, session: DatabaseSession
) -> list[HouseholdMemberRead]:
    """List eligible ACTIVE members by joined_at ASC, then membership ID ASC."""
    statement = (
        select(
            HouseholdMembership.id.label("membership_id"),
            HouseholdMembership.user_id,
            User.display_name,
            HouseholdMembership.role,
            HouseholdMembership.status,
        )
        .join(User, User.id == HouseholdMembership.user_id)
        .where(
            HouseholdMembership.household_id == membership.household_id,
            HouseholdMembership.status == MembershipStatus.ACTIVE,
        )
        .order_by(HouseholdMembership.joined_at, HouseholdMembership.id)
    )
    return [
        HouseholdMemberRead.model_validate(row) for row in session.execute(statement).mappings()
    ]
