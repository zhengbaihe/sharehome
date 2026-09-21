from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.security import (
    TokenValidationError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

TEST_SECRET = "test-only-jwt-secret-not-for-production-123456789"
USER_ID = UUID("697521fc-1581-4fd5-8432-ae62137e0ef6")


@pytest.fixture
def auth_settings(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def password_hash():
    return hash_password("example-password")


def test_password_hash_is_encoded_and_fits_storage(password_hash):
    assert password_hash != "example-password"
    assert password_hash.startswith("$argon2id$")
    assert len(password_hash) <= 255


def test_correct_password_verifies(password_hash):
    assert verify_password("example-password", password_hash) is True


def test_incorrect_password_fails(password_hash):
    assert verify_password("wrong-password", password_hash) is False


def test_hashes_are_salted_and_both_verify(password_hash):
    second = hash_password("example-password")
    assert second != password_hash
    assert verify_password("example-password", password_hash)
    assert verify_password("example-password", second)


@pytest.mark.parametrize("malformed", ["", "plain-password", "$argon2id$invalid", "雪", None])
def test_malformed_hash_fails_safely(malformed):
    assert verify_password("example-password", malformed) is False


@pytest.mark.parametrize("user_id", [USER_ID, str(USER_ID)])
def test_token_round_trip_and_configured_expiration(auth_settings, user_id):
    before = int(datetime.now(UTC).timestamp())
    token = create_access_token(user_id)
    after = int(datetime.now(UTC).timestamp())
    assert isinstance(token, str)
    claims = decode_access_token(token)
    assert claims["sub"] == str(USER_ID)
    assert before + 900 <= claims["exp"] <= after + 900


def test_expired_token_is_rejected(auth_settings):
    token = jwt.encode(
        {"sub": str(USER_ID), "exp": datetime.now(UTC) - timedelta(seconds=1)},
        TEST_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenValidationError):
        decode_access_token(token)


@pytest.mark.parametrize("token", ["", "not-a-token", "a.b.c", None])
def test_malformed_token_is_rejected(auth_settings, token):
    with pytest.raises(TokenValidationError):
        decode_access_token(token)


def test_wrong_secret_is_rejected(auth_settings):
    token = jwt.encode(
        {"sub": str(USER_ID), "exp": datetime.now(UTC) + timedelta(minutes=1)},
        "different-secret-not-for-production-123456789",
        algorithm="HS256",
    )
    with pytest.raises(TokenValidationError):
        decode_access_token(token)


@pytest.mark.parametrize("algorithm", ["HS384", "none"])
def test_unapproved_algorithm_is_rejected(auth_settings, algorithm):
    token = jwt.encode(
        {"sub": str(USER_ID), "exp": datetime.now(UTC) + timedelta(minutes=1)},
        TEST_SECRET if algorithm != "none" else None,
        algorithm=algorithm,
    )
    with pytest.raises(TokenValidationError):
        decode_access_token(token)


@pytest.mark.parametrize("missing_claim", ["sub", "exp"])
def test_required_claims_are_enforced(auth_settings, missing_claim):
    claims = {"sub": str(USER_ID), "exp": int(datetime.now(UTC).timestamp()) + 60}
    del claims[missing_claim]
    with pytest.raises(TokenValidationError):
        decode_access_token(jwt.encode(claims, TEST_SECRET, algorithm="HS256"))


@pytest.mark.parametrize("subject", ["", "not-a-uuid", 123, None, [str(USER_ID)]])
def test_malformed_subject_is_rejected(auth_settings, subject):
    token = jwt.encode(
        {"sub": subject, "exp": datetime.now(UTC) + timedelta(minutes=1)},
        TEST_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(TokenValidationError):
        decode_access_token(token)


@pytest.mark.parametrize("user_id", ["", "not-a-uuid", 123, None])
def test_invalid_user_id_cannot_create_token(auth_settings, user_id):
    with pytest.raises(ValueError, match="user_id"):
        create_access_token(user_id)


@pytest.mark.parametrize("expiry", [True, "9999999999", 9999999999.5, None, "invalid"])
def test_malformed_expiration_is_rejected(auth_settings, expiry):
    token = jwt.encode({"sub": str(USER_ID), "exp": expiry}, TEST_SECRET, algorithm="HS256")
    with pytest.raises(TokenValidationError):
        decode_access_token(token)


def test_settings_load_from_environment(auth_settings):
    assert auth_settings.jwt_secret.get_secret_value() == TEST_SECRET
    assert auth_settings.jwt_algorithm == "HS256"
    assert auth_settings.jwt_access_token_expire_minutes == 15
    assert TEST_SECRET not in repr(auth_settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("jwt_secret", "short"),
        ("jwt_secret", ""),
        ("jwt_algorithm", "none"),
        ("jwt_access_token_expire_minutes", 0),
        ("jwt_access_token_expire_minutes", -1),
    ],
)
def test_invalid_auth_configuration_is_rejected(auth_settings, field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_token_operations_require_explicit_secret(monkeypatch, auth_settings):
    settings = Settings(_env_file=None, jwt_secret=None)
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    with pytest.raises(ValueError, match="JWT_SECRET must be configured"):
        create_access_token(USER_ID)
    with pytest.raises(ValueError, match="JWT_SECRET must be configured"):
        decode_access_token("anything")
