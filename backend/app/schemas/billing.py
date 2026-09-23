from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictInt

from app.models import SplitMethod


class BillCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    amount_minor: StrictInt
    payer_membership_id: UUID
    participant_membership_ids: list[UUID]
    paid_at: AwareDatetime


class AllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    membership_id: UUID
    amount_minor: int
    created_at: datetime


class BillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    payer_membership_id: UUID
    description: str
    amount_minor: int
    paid_at: datetime
    split_method: SplitMethod
    created_at: datetime
    updated_at: datetime
    allocations: list[AllocationRead]
