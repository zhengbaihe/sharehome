from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import TokenValidationError, decode_access_token
from app.db.session import get_session
from app.models import HouseholdMembership, MembershipStatus, User

bearer = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials)
    except TokenValidationError:
        raise unauthorized from None
    user = session.get(User, UUID(claims["sub"]))
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_active_household_membership(
    household_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> HouseholdMembership:
    membership = session.scalar(
        select(HouseholdMembership)
        .options(joinedload(HouseholdMembership.household))
        .where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == user.id,
            HouseholdMembership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return membership


ActiveHouseholdMembership = Annotated[HouseholdMembership, Depends(get_active_household_membership)]
