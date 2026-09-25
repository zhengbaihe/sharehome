from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event

from app.core.security import create_access_token, hash_password
from app.models import Household, HouseholdMembership, MembershipRole, MembershipStatus, User


@pytest.fixture(scope="module")
def password_hash():
    return hash_password("members-test-password")


@pytest.fixture
def home(client, db_session, password_hash):
    household = Household(name="Home")
    names = ["Alex", "Blair", "Casey", "Departed", "Outside"]
    users = [
        User(email=f"{name}@example.com", display_name=name, password_hash=password_hash)
        for name in names
    ]
    members = [
        HouseholdMembership(
            id=UUID(int=index + 1),
            user=user,
            household=household if index < 4 else Household(name="Other"),
            role=MembershipRole.OWNER if index == 0 else MembershipRole.MEMBER,
            status=MembershipStatus.DEPARTED if index == 3 else MembershipStatus.ACTIVE,
            joined_at=datetime(2026, 1, 1, tzinfo=UTC),
            departed_at=datetime(2026, 2, 1, tzinfo=UTC) if index == 3 else None,
        )
        for index, user in enumerate(users)
    ]
    db_session.add_all(members)
    db_session.commit()
    return SimpleNamespace(
        id=household.id,
        ids=[member.id for member in members],
        users=[user.id for user in users],
        headers=[{"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users],
        path=f"/households/{household.id}/members",
    )


@pytest.mark.parametrize("actor", [0, 1])
def test_active_owner_and_member_receive_only_public_active_members(client, home, actor):
    response = client.get(home.path, headers=home.headers[actor])
    assert response.status_code == 200
    assert response.json() == [
        dict(
            membership_id=str(home.ids[index]),
            user_id=str(home.users[index]),
            display_name=name,
            role="OWNER" if index == 0 else "MEMBER",
            status="ACTIVE",
        )
        for index, name in enumerate(["Alex", "Blair", "Casey"])
    ]


@pytest.mark.parametrize("actor, code", [(None, 401), (3, 404), (4, 404)])
def test_access_denied(client, home, actor, code):
    response = client.get(home.path, headers={} if actor is None else home.headers[actor])
    assert response.status_code == code
    if code == 404:
        assert response.json() == {"detail": "Household not found"}
    else:
        assert response.headers["www-authenticate"] == "Bearer"


def test_missing_household_is_404(client, home):
    response = client.get(f"/households/{uuid4()}/members", headers=home.headers[0])
    assert response.status_code == 404
    assert response.json() == {"detail": "Household not found"}


def test_order_by_joined_at_then_id(client, db_session, home):
    member = db_session.get(HouseholdMembership, home.ids[0])
    member.joined_at = datetime(2026, 1, 2, tzinfo=UTC)
    db_session.commit()
    response = client.get(home.path, headers=home.headers[0])
    assert response.status_code == 200
    assert [row["membership_id"] for row in response.json()] == [
        str(home.ids[i]) for i in [1, 2, 0]
    ]
    assert client.get(home.path, headers=home.headers[0]).json() == response.json()


def test_persisted_status_changes_leave_only_the_requester(client, db_session, home):
    for member_id in home.ids[1:3]:
        member = db_session.get(HouseholdMembership, member_id)
        member.status = MembershipStatus.DEPARTED
        member.departed_at = datetime(2026, 2, 1, tzinfo=UTC)
    db_session.commit()
    response = client.get(home.path, headers=home.headers[0])
    assert response.status_code == 200
    assert [row["membership_id"] for row in response.json()] == [str(home.ids[0])]
    # Historical members still belong in balances; membership discovery must not change that API.
    balances = client.get(f"/households/{home.id}/balances", headers=home.headers[0])
    assert balances.status_code == 200
    assert {row["membership_id"] for row in balances.json()} == {
        str(value) for value in home.ids[:4]
    }
    assert client.get(home.path, headers=home.headers[1]).status_code == 404


def test_query_count_is_constant_and_read_only(client, db_session, home):
    db_session.expunge_all()
    connection = db_session.connection()
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture)
    try:
        response = client.get(home.path, headers=home.headers[0])
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert len(response.json()) == 3
    # Current-user lookup, ACTIVE access check, and one joined member query.
    assert len(statements) == 3
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
