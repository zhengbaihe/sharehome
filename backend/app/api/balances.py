from fastapi import APIRouter, HTTPException

from app.api.dependencies import ActiveHouseholdMembership, DatabaseSession
from app.schemas.balances import MembershipBalanceRead
from app.services.balances import BalanceReadError, MembershipBalance, get_household_balances

router = APIRouter(prefix="/households/{household_id}/balances", tags=["balances"])


@router.get("", response_model=list[MembershipBalanceRead])
def read_balances(
    membership: ActiveHouseholdMembership, session: DatabaseSession
) -> list[MembershipBalance]:
    try:
        return get_household_balances(session, household_id=membership.household_id)
    except BalanceReadError:
        raise HTTPException(status_code=500, detail="Unable to read household balances") from None
