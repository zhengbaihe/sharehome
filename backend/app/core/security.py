from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings, get_settings


class TokenValidationError(ValueError):
    """An access token is invalid or expired."""


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return a randomly salted Argon2id hash for User.password_hash."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Mismatches and malformed stored hashes fail closed."""
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError, UnicodeError):
        return False


def _signing_secret(settings: Settings) -> str:
    if settings.jwt_secret is None:
        raise ValueError("JWT_SECRET must be configured before using access tokens")
    return settings.jwt_secret.get_secret_value()


def create_access_token(user_id: UUID | str) -> str:
    """Create an access token for a UUID user ID with the configured lifetime."""
    if not isinstance(user_id, (UUID, str)):
        raise ValueError("user_id must be a UUID or UUID string")
    try:
        subject = str(UUID(str(user_id)))
    except ValueError:
        raise ValueError("user_id must be a valid UUID") from None
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return jwt.encode(
        {"sub": subject, "exp": expires_at},
        _signing_secret(settings),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate signature, required claims, expiry, and UUID subject, or raise."""
    settings = get_settings()
    secret = _signing_secret(settings)
    if not isinstance(token, str) or not token:
        raise TokenValidationError("Invalid or expired access token")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp"]},
        )
        if not isinstance(claims["sub"], str) or type(claims["exp"]) is not int:
            raise ValueError("Invalid access-token claims")
        UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise TokenValidationError("Invalid or expired access token") from None
    return claims
