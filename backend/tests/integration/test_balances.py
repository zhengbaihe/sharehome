from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from app.api import balances
from app.core.security import create_access_token, hash_password
from app.models import (
    Allocation,
    Bill,
    Household,
    HouseholdMembership,
    MembershipRole,
    MembershipStatus,
    User,
)
from app.services.balances import BalanceReadError, get_household_balances
from app.services.billing import create_equal_bill

FIELDS = {
    "membership_id",
    "user_id",
    "display_name",
    "role",
    "status",
    "paid_minor",
    "allocated_minor",
    "balance_minor",
}
NOW = datetime(2026, 9, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password("balance-test-password")


@pytest.fixture
def home(client, db_session, password_hash):
    users = [
        User(email=f"{name}@example.com", display_name=name, password_hash=password_hash)
        for name in ["Alex", "Blair", "Casey", "Outside"]
    ]
    household = Household(name="Home")
    members = [
        HouseholdMembership(
            id=UUID(int=index + 1),
            household=household,
            user=user,
            joined_at=NOW,
            role=MembershipRole.OWNER if index == 0 else MembershipRole.MEMBER,
        )
        for index, user in enumerate(users[:3])
    ]
    other = HouseholdMembership(household=Household(name="Other"), user=users[3])
    db_session.add_all([*members, other])
    db_session.commit()
    return SimpleNamespace(
        id=household.id,
        ids=[member.id for member in members],
        users=[user.id for user in users],
        other_id=other.household_id,
        other_member=other.id,
        headers=[{"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users],
        path=f"/households/{household.id}/balances",
    )


def bill(session, home, amount=10000, payer=0, participants=None):
    return create_equal_bill(
        session,
        household_id=home.id,
        payer_membership_id=home.ids[payer],
        participant_membership_ids=home.ids[:2] if participants is None else participants,
        description="Internet",
        amount_minor=amount,
        paid_at=NOW,
    )


def response_rows(client, home, actor=0):
    response = client.get(home.path, headers=home.headers[actor])
    assert response.status_code == 200
    rows = response.json()
    assert all(set(row) == FIELDS for row in rows)
    for row in rows:
        for field in ["paid_minor", "allocated_minor", "balance_minor"]:
            assert type(row[field]) is int
    return {row["membership_id"]: row for row in rows}


def totals(rows, membership_id):
    row = rows[str(membership_id)]
    return row["paid_minor"], row["allocated_minor"], row["balance_minor"]


@pytest.mark.parametrize("actor", [0, 1])
def test_alex_blair_api_and_zero_activity_member(client, db_session, home, actor):
    bill(db_session, home)
    rows = response_rows(client, home, actor)
    assert list(rows) == [str(member) for member in home.ids]
    assert totals(rows, home.ids[0]) == (10000, 5000, 5000)
    assert totals(rows, home.ids[1]) == (0, 5000, -5000)
    assert totals(rows, home.ids[2]) == (0, 0, 0)
    for index, name in enumerate(["Alex", "Blair", "Casey"]):
        row = rows[str(home.ids[index])]
        assert row["display_name"] == name
        assert row["user_id"] == str(home.users[index])
        assert row["role"] == ("OWNER" if index == 0 else "MEMBER")
        assert row["status"] == "ACTIVE"
    assert sum(row["balance_minor"] for row in rows.values()) == 0


def test_multiple_bills_and_changing_payer(client, db_session, home):
    bill(db_session, home)
    bill(db_session, home, amount=6000, payer=1)
    rows = response_rows(client, home)
    assert totals(rows, home.ids[0]) == (10000, 8000, 2000)
    assert totals(rows, home.ids[1]) == (6000, 8000, -2000)
    assert totals(rows, home.ids[2]) == (0, 0, 0)
    assert sum(row["balance_minor"] for row in rows.values()) == 0


def test_no_bills_returns_all_members_as_zero(client, home):
    rows = response_rows(client, home)
    assert len(rows) == 3
    assert all(totals(rows, member) == (0, 0, 0) for member in home.ids)


def test_departed_history_retained_but_requester_denied(client, db_session, home):
    bill(db_session, home)
    bill(db_session, home, amount=6000, payer=1)
    departed = db_session.get(HouseholdMembership, home.ids[1])
    departed.status = MembershipStatus.DEPARTED
    departed.departed_at = NOW
    db_session.commit()
    rows = response_rows(client, home)
    assert rows[str(home.ids[1])]["status"] == "DEPARTED"
    assert totals(rows, home.ids[1]) == (6000, 8000, -2000)
    assert sum(row["balance_minor"] for row in rows.values()) == 0
    response = client.get(home.path, headers=home.headers[1])
    assert response.status_code == 404
    assert response.json() == {"detail": "Household not found"}


@pytest.mark.parametrize(
    "case, expected", [("anonymous", 401), ("unrelated", 404), ("missing", 404)]
)
def test_access_control(client, home, case, expected):
    path = f"/households/{uuid4()}/balances" if case == "missing" else home.path
    headers = {} if case == "anonymous" else home.headers[3 if case == "unrelated" else 0]
    response = client.get(path, headers=headers)
    assert response.status_code == expected
    if expected == 404:
        assert response.json() == {"detail": "Household not found"}
    else:
        assert response.headers["www-authenticate"] == "Bearer"


def test_foreign_financial_records_cannot_affect_household(client, db_session, home):
    bill(db_session, home)
    before = response_rows(client, home)
    other = create_equal_bill(
        db_session,
        household_id=home.other_id,
        payer_membership_id=home.other_member,
        participant_membership_ids=[home.other_member],
        amount_minor=99999,
        description="Other home",
        paid_at=NOW,
    )
    assert response_rows(client, home) == before
    # Existing FKs permit cross-household IDs in directly inserted data. Even then,
    # bill household scoping must exclude both the payment and the allocation.
    other.payer_membership_id = home.ids[0]
    other.allocations[0].membership_id = home.ids[1]
    db_session.commit()
    assert response_rows(client, home) == before


def test_conservation_with_remainders_and_payer_outside_participants(client, db_session, home):
    bill(db_session, home, amount=1, participants=home.ids)
    bill(db_session, home, amount=10000, payer=1, participants=list(reversed(home.ids)))
    bill(db_session, home, amount=7, payer=2, participants=[home.ids[0]])
    rows = response_rows(client, home)
    assert sum(row["paid_minor"] for row in rows.values()) == 10008
    assert sum(row["allocated_minor"] for row in rows.values()) == 10008
    assert sum(row["balance_minor"] for row in rows.values()) == 0


def test_deterministic_joined_time_then_id_order(client, db_session, home):
    member = db_session.get(HouseholdMembership, home.ids[0])
    member.joined_at = datetime(2026, 9, 2, tzinfo=UTC)
    db_session.commit()
    expected = [str(home.ids[1]), str(home.ids[2]), str(home.ids[0])]
    assert list(response_rows(client, home)) == expected
    assert list(response_rows(client, home)) == expected


def test_service_is_one_read_query_and_does_not_commit_or_flush(db_session, home):
    bill(db_session, home)
    queries = []
    connection = db_session.connection()

    def capture(connection, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    pending = Household(name="Unrelated pending write")
    db_session.add(pending)
    event.listen(connection, "before_cursor_execute", capture)
    try:
        rows = get_household_balances(db_session, household_id=home.id)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert len(queries) == 1
    assert queries[0].lstrip().upper().startswith("SELECT")
    assert len(rows) == 3
    assert pending in db_session.new
    assert pending.id is None
    assert db_session.in_transaction()
    db_session.rollback()


def test_malformed_data_is_reported_without_automatic_correction(client, db_session, home):
    saved = bill(db_session, home)
    saved.allocations[0].amount_minor -= 1
    db_session.commit()
    before = list(db_session.execute(select(Allocation.id, Allocation.amount_minor)))
    rows = response_rows(client, home)
    assert sum(row["balance_minor"] for row in rows.values()) == 1
    assert list(db_session.execute(select(Allocation.id, Allocation.amount_minor))) == before
    assert db_session.get(Bill, saved.id).amount_minor == 10000


def test_large_integer_totals_remain_exact(client, db_session, home):
    amount = 2**63 - 1
    bill(db_session, home, amount=amount)
    bill(db_session, home, amount=amount)
    rows = response_rows(client, home)
    assert totals(rows, home.ids[0]) == (2 * amount, amount + 1, amount - 1)
    assert totals(rows, home.ids[1]) == (0, amount - 1, -(amount - 1))
    assert sum(row["balance_minor"] for row in rows.values()) == 0


def test_service_database_failure_is_sanitized(db_session, home, monkeypatch):
    monkeypatch.setattr(
        db_session, "execute", Mock(side_effect=SQLAlchemyError("private SQL text"))
    )
    with pytest.raises(BalanceReadError) as error:
        get_household_balances(db_session, household_id=home.id)
    assert str(error.value) == "Unable to read household balances"
    assert error.value.__suppress_context__


def test_api_read_failure_is_generic_500(client, home, monkeypatch):
    monkeypatch.setattr(
        balances, "get_household_balances", Mock(side_effect=BalanceReadError("private"))
    )
    response = client.get(home.path, headers=home.headers[0])
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to read household balances"}
