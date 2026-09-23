from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import MembershipRole, MembershipStatus


class MembershipBalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    user_id: UUID
    display_name: str
    role: MembershipRole
    status: MembershipStatus
    paid_minor: int
    allocated_minor: int
    balance_minor: int
