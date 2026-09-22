from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class HouseholdCreate(BaseModel):
    name: Annotated[
        str,
        Field(min_length=1, max_length=100),
        BeforeValidator(lambda value: value.strip() if isinstance(value, str) else value),
    ]


class HouseholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    currency: str
    timezone: str
    created_at: datetime
    updated_at: datetime
