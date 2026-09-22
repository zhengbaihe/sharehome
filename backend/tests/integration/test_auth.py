from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token, decode_access_token, verify_password
from app.models import Household, HouseholdMembership, User

TEST_SECRET = "auth-api-test-secret-not-for-production-123456789"
PASSWORD = "correct-horse-battery-staple"
PUBLIC_FIELDS = {"id", "email", "display_name", "created_at", "updated_at"}


def register(client, email="alex@example.com"):
    return client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Alex",
        },
    )


@pytest.fixture
def registered_user(client):
    response = register(client)
    assert response.status_code == 201
    return response.json()


def test_registration_persists_normalized_hashed_user(client, db_session):
    response = register(client, " Alex@Example.COM ")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == PUBLIC_FIELDS
    assert body["email"] == "alex@example.com"
    assert body["display_name"] == "Alex"
    assert PASSWORD not in response.text
    user = db_session.get(User, UUID(body["id"]))
    assert user.email == "alex@example.com"
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash)
    assert user.password_hash not in response.text
    assert db_session.scalar(select(func.count()).select_from(Household)) == 0
    assert db_session.scalar(select(func.count()).select_from(HouseholdMembership)) == 0


@pytest.mark.parametrize("email", ["alex@example.com", " ALEX@Example.COM "])
def test_duplicate_email_returns_conflict_and_rolls_back(client, registered_user, email):
    response = register(client, email)
    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already registered"}
    assert register(client, "blair@example.com").status_code == 201


def test_login_returns_valid_token(client, registered_user):
    response = client.post(
        "/auth/login",
        json={
            "email": " ALEX@Example.COM ",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"
    assert decode_access_token(response.json()["access_token"])["sub"] == registered_user["id"]
    assert PASSWORD not in response.text


def test_login_failures_are_indistinguishable(client, registered_user):
    wrong_password = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": "wrong-password",
        },
    )
    missing_user = client.post(
        "/auth/login",
        json={
            "email": "nobody@example.com",
            "password": PASSWORD,
        },
    )
    assert wrong_password.status_code == missing_user.status_code == 401
    assert wrong_password.json() == missing_user.json() == {"detail": "Invalid email or password"}
    assert wrong_password.headers["www-authenticate"] == "Bearer"
    assert missing_user.headers["www-authenticate"] == "Bearer"


def test_register_login_me_flow(client, registered_user):
    assert register(client, "blair@example.com").status_code == 201
    token = client.post(
        "/auth/login",
        json={
            "email": "alex@example.com",
            "password": PASSWORD,
        },
    ).json()["access_token"]
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == registered_user
    assert set(response.json()) == PUBLIC_FIELDS
    assert PASSWORD not in response.text
    assert TEST_SECRET not in response.text


@pytest.mark.parametrize("authorization", [None, "Basic abc", "Bearer", "Bearer not-a-token"])
def test_missing_or_malformed_credentials_rejected(client, authorization):
    headers = {} if authorization is None else {"Authorization": authorization}
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("kind", ["expired", "wrong-secret", "missing-user", "invalid-sub"])
def test_invalid_bearer_tokens_rejected(client, registered_user, kind):
    subject = registered_user["id"]
    expiry = datetime.now(UTC) + timedelta(minutes=5)
    secret = TEST_SECRET
    if kind == "expired":
        expiry = datetime.now(UTC) - timedelta(seconds=1)
    elif kind == "wrong-secret":
        secret = "different-auth-test-secret-12345678901234567890"
    elif kind == "missing-user":
        subject = str(uuid4())
    else:
        subject = "not-a-uuid"
    token = jwt.encode({"sub": subject, "exp": expiry}, secret, algorithm="HS256")
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_user_removed_after_token_creation_is_rejected(client, db_session, registered_user):
    token = create_access_token(registered_user["id"])
    db_session.delete(db_session.get(User, UUID(registered_user["id"])))
    db_session.commit()
    assert client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"email": "alex@example.com", "password": PASSWORD},
        {"email": " ", "password": PASSWORD, "display_name": "Alex"},
        {"email": "alex@example.com", "password": "", "display_name": "Alex"},
        {"email": "alex@example.com", "password": PASSWORD, "display_name": " "},
        {"email": "alex@example.com", "password": PASSWORD, "display_name": "a" * 101},
    ],
)
def test_registration_validation_does_not_echo_password(client, body):
    response = client.post("/auth/register", json=body)
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])
