from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select

from app.core.security import create_access_token, hash_password
from app.models import Household, HouseholdMembership, MembershipRole, MembershipStatus, User

PUBLIC_FIELDS = {"id", "name", "currency", "timezone", "created_at", "updated_at"}


@pytest.fixture
def actor(client, db_session):
    response = client.post(
        "/auth/register",
        json={
            "email": "alex@example.com",
            "password": "household-test-password",
            "display_name": "Alex",
        },
    )
    assert response.status_code == 201
    return db_session.get(User, UUID(response.json()["id"]))


@pytest.fixture
def headers(actor):
    return {"Authorization": f"Bearer {create_access_token(actor.id)}"}


@pytest.fixture
def other_user(db_session):
    user = User(
        email="blair@example.com",
        password_hash=hash_password("other-test-password"),
        display_name="Blair",
    )
    db_session.add(user)
    db_session.commit()
    return user


def add_membership(
    session, user, name="Home", role=MembershipRole.MEMBER, status=MembershipStatus.ACTIVE
):
    membership = HouseholdMembership(
        household=Household(name=name),
        user_id=user.id,
        role=role,
        status=status,
        departed_at=datetime.now(UTC) if status == MembershipStatus.DEPARTED else None,
    )
    session.add(membership)
    session.commit()
    return membership


def test_creation_persists_household_and_only_creator_membership(
    client, db_session, actor, headers, other_user
):
    response = client.post("/households", headers=headers, json={"name": " Alex Home "})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == PUBLIC_FIELDS
    assert body["name"] == "Alex Home"
    assert body["currency"] == "CNY"
    assert body["timezone"] == "Asia/Kuala_Lumpur"
    household = db_session.get(Household, UUID(body["id"]))
    assert household.name == "Alex Home"
    memberships = list(db_session.scalars(select(HouseholdMembership)))
    assert len(memberships) == 1
    membership = memberships[0]
    assert membership.household_id == household.id
    assert membership.user_id == actor.id
    assert membership.user_id != other_user.id
    assert membership.role == MembershipRole.OWNER
    assert membership.status == MembershipStatus.ACTIVE
    assert membership.joined_at.tzinfo is not None
    assert membership.departed_at is None
    assert client.get(f"/households/{household.id}", headers=headers).json() == body
    assert client.get("/households", headers=headers).json() == [body]


def test_membership_insert_failure_rolls_back_household(client, db_session, headers):
    seen_household_counts = []

    def break_membership(mapper, connection, target):
        # The household INSERT has occurred, but must not survive this real FK failure.
        seen_household_counts.append(connection.scalar(select(func.count()).select_from(Household)))
        target.user_id = uuid4()

    event.listen(HouseholdMembership, "before_insert", break_membership)
    try:
        response = client.post("/households", headers=headers, json={"name": "Rollback home"})
    finally:
        event.remove(HouseholdMembership, "before_insert", break_membership)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create household"}
    assert seen_household_counts == [1]
    assert db_session.scalar(select(func.count()).select_from(Household)) == 0
    assert db_session.scalar(select(func.count()).select_from(HouseholdMembership)) == 0
    assert (
        client.post("/households", headers=headers, json={"name": "Retry home"}).status_code == 201
    )


@pytest.mark.parametrize(
    "body", [{}, {"name": ""}, {"name": "   "}, {"name": "x" * 101}, {"name": None}, {"name": 123}]
)
def test_invalid_create_body_rejected(client, db_session, headers, body):
    response = client.post("/households", headers=headers, json=body)
    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Household)) == 0
    assert db_session.scalar(select(func.count()).select_from(HouseholdMembership)) == 0


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/households"),
        ("get", "/households"),
        ("get", "/households/697521fc-1581-4fd5-8432-ae62137e0ef6"),
    ],
)
def test_unauthenticated_requests_rejected(client, method, path):
    response = client.request(method, path, json={"name": "Home"} if method == "post" else None)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_list_without_memberships_is_empty(client, headers):
    assert client.get("/households", headers=headers).json() == []


def test_list_filters_current_active_memberships_and_orders_deterministically(
    client, db_session, actor, headers, other_user
):
    owned = add_membership(db_session, actor, "Owned", MembershipRole.OWNER)
    shared = add_membership(db_session, actor, "Shared", MembershipRole.MEMBER)
    departed = add_membership(db_session, actor, "Departed", status=MembershipStatus.DEPARTED)
    unrelated = add_membership(db_session, other_user, "Unrelated", MembershipRole.OWNER)
    db_session.add(HouseholdMembership(household_id=shared.household_id, user_id=other_user.id))
    # Force a creation-time tie so the ID tie-breaker is actually exercised.
    owned.household.created_at = shared.household.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.commit()
    expected = sorted([str(owned.household_id), str(shared.household_id)])
    response = client.get("/households", headers=headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == expected
    assert all(set(item) == PUBLIC_FIELDS for item in response.json())
    assert str(departed.household_id) not in expected
    assert str(unrelated.household_id) not in expected
    assert client.get("/households", headers=headers).json() == response.json()


@pytest.mark.parametrize("role", [MembershipRole.OWNER, MembershipRole.MEMBER])
def test_active_owner_and_member_can_read(client, db_session, actor, headers, role):
    membership = add_membership(db_session, actor, role=role)
    response = client.get(f"/households/{membership.household_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(membership.household_id)
    assert set(response.json()) == PUBLIC_FIELDS


def test_unrelated_household_and_nonexistent_household_have_same_404(
    client, db_session, headers, other_user
):
    membership = add_membership(db_session, other_user, role=MembershipRole.OWNER)
    inaccessible = client.get(f"/households/{membership.household_id}", headers=headers)
    missing = client.get(f"/households/{uuid4()}", headers=headers)
    assert inaccessible.status_code == missing.status_code == 404
    assert inaccessible.json() == missing.json() == {"detail": "Household not found"}


@pytest.mark.parametrize("role", [MembershipRole.OWNER, MembershipRole.MEMBER])
def test_departed_user_cannot_use_another_users_active_membership(
    client, db_session, actor, headers, other_user, role
):
    departed = add_membership(db_session, actor, role=role, status=MembershipStatus.DEPARTED)
    db_session.add(
        HouseholdMembership(
            household_id=departed.household_id,
            user_id=other_user.id,
            status=MembershipStatus.ACTIVE,
        )
    )
    db_session.commit()
    response = client.get(f"/households/{departed.household_id}", headers=headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Household not found"}
    assert client.get("/households", headers=headers).json() == []


def test_membership_status_is_rechecked_on_subsequent_requests(client, db_session, actor, headers):
    membership = add_membership(db_session, actor)
    path = f"/households/{membership.household_id}"
    assert client.get(path, headers=headers).status_code == 200
    membership.status = MembershipStatus.DEPARTED
    membership.departed_at = datetime.now(UTC)
    db_session.commit()
    assert client.get(path, headers=headers).status_code == 404


def test_invalid_household_id_returns_422(client, headers):
    assert client.get("/households/not-a-uuid", headers=headers).status_code == 422
