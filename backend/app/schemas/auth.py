from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, SecretStr


def normalize_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


NormalizedEmail = Annotated[
    str, Field(min_length=1, max_length=320), BeforeValidator(normalize_email)
]
Password = Annotated[SecretStr, Field(min_length=1, max_length=1024)]


class UserRegister(BaseModel):
    email: NormalizedEmail
    password: Password
    display_name: Annotated[
        str,
        Field(min_length=1, max_length=100),
        BeforeValidator(lambda value: value.strip() if isinstance(value, str) else value),
    ]


class UserLogin(BaseModel):
    email: NormalizedEmail
    password: Password


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
