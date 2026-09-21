from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DatabaseSession
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import TokenResponse, UserLogin, UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])
# Verify a hash even for an unknown email, avoiding the immediate no-user response.
_dummy_password_hash = hash_password("sharehome-unused-login-comparison")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, session: DatabaseSession) -> User:
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password.get_secret_value()),
        display_name=payload.display_name,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_users_email":
            raise HTTPException(status_code=409, detail="Email is already registered") from None
        raise HTTPException(status_code=500, detail="Unable to register user") from None
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, session: DatabaseSession) -> TokenResponse:
    user = session.scalar(select(User).where(User.email == payload.email))
    stored_hash = user.password_hash if user is not None else _dummy_password_hash
    valid_password = verify_password(payload.password.get_secret_value(), stored_hash)
    if user is None or not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id))
