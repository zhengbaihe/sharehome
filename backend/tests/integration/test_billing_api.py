from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select

from app.api import billing
from app.core.security import create_access_token, hash_password
from app.domain.splitting import split_equal
from app.models import Allocation, Bill, HouseholdMembership, MembershipStatus, User
from app.services.billing import create_equal_bill

BILL_FIELDS = {
    "id",
    "household_id",
    "payer_membership_id",
    "description",
    "amount_minor",
    "paid_at",
    "split_method",
    "created_at",
    "updated_at",
    "allocations",
}
ALLOCATION_FIELDS = {"id", "membership_id", "amount_minor", "created_at"}
PAID_AT = "2026-09-01T12:00:00Z"


@pytest.fixture(scope="module")
def password_hash():
    return hash_password("billing-api-test-password")


@pytest.fixture
def home(client, db_session, password_hash):
    users = [
        User(email=f"{name}@example.com", display_name=name, password_hash=password_hash)
        for name in ["alex", "blair", "casey", "outsider", "departed"]
    ]
    db_session.add_all(users)
    db_session.commit()
    headers = [{"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users]
    response = client.post("/households", headers=headers[0], json={"name": "Home"})
    assert response.status_code == 201
    household_id = UUID(response.json()["id"])
    alex = db_session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
            HouseholdMembership.user_id == users[0].id,
        )
    )
    members = [alex] + [
        HouseholdMembership(household_id=household_id, user_id=users[index].id)
        for index in [1, 2, 4]
    ]
    members[-1].status = MembershipStatus.DEPARTED
    members[-1].departed_at = datetime(2026, 9, 1, tzinfo=UTC)
    db_session.add_all(members[1:])
    db_session.commit()
    other = client.post("/households", headers=headers[3], json={"name": "Other"})
    assert other.status_code == 201
    other_id = UUID(other.json()["id"])
    other_member = db_session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == other_id,
        )
    )
    return SimpleNamespace(
        id=household_id,
        members=[member.id for member in members],
        headers=headers,
        path=f"/households/{household_id}/bills",
        other_path=f"/households/{other_id}/bills",
        other_member=other_member.id,
    )


def payload(home):
    return dict(
        description="Internet",
        amount_minor=10000,
        payer_membership_id=str(home.members[0]),
        participant_membership_ids=[str(member) for member in home.members[:2]],
        paid_at=PAID_AT,
    )


def post_bill(client, home, body=None, actor=0):
    return client.post(home.path, headers=home.headers[actor], json=body or payload(home))


def assert_public_bill(body):
    assert set(body) == BILL_FIELDS
    assert all(set(item) == ALLOCATION_FIELDS for item in body["allocations"])


def assert_no_records(session):
    assert session.scalar(select(func.count()).select_from(Bill)) == 0
    assert session.scalar(select(func.count()).select_from(Allocation)) == 0


@pytest.mark.parametrize("actor", [0, 1, 2])
def test_create_reuses_service_and_persists_alex_blair(
    client, db_session, home, monkeypatch, actor
):
    spy = Mock(wraps=create_equal_bill)
    monkeypatch.setattr(billing, "create_equal_bill", spy)
    response = post_bill(client, home, actor=actor)
    assert response.status_code == 201
    body = response.json()
    assert_public_bill(body)
    spy.assert_called_once()
    assert spy.call_args.args == (db_session,)
    assert spy.call_args.kwargs["household_id"] == home.id
    assert body["household_id"] == str(home.id)
    assert body["payer_membership_id"] == str(home.members[0])
    assert body["description"] == "Internet"
    assert body["amount_minor"] == 10000
    assert body["split_method"] == "EQUAL"
    assert datetime.fromisoformat(body["paid_at"]) == datetime.fromisoformat(PAID_AT)
    expected = {str(member): 5000 for member in home.members[:2]}
    assert {a["membership_id"]: a["amount_minor"] for a in body["allocations"]} == expected
    db_session.expunge_all()
    stored = db_session.get(Bill, UUID(body["id"]))
    for field in ["description", "amount_minor"]:
        assert getattr(stored, field) == body[field]
    for field in ["id", "household_id", "payer_membership_id"]:
        assert str(getattr(stored, field)) == body[field]
    for field in ["paid_at", "created_at", "updated_at"]:
        assert getattr(stored, field) == datetime.fromisoformat(body[field])
    assert {str(a.id) for a in stored.allocations} == {a["id"] for a in body["allocations"]}
    assert {str(a.membership_id): a.amount_minor for a in stored.allocations} == expected
    assert sum(a.amount_minor for a in stored.allocations) == stored.amount_minor


@pytest.mark.parametrize("amount", [10000, 1])
def test_remainders_are_persisted_independent_of_request_order(client, db_session, home, amount):
    ids = [str(member) for member in home.members[:3]]
    expected = split_equal(amount, ids)
    for order in [ids, list(reversed(ids))]:
        body = payload(home)
        body.update(amount_minor=amount, participant_membership_ids=order)
        response = post_bill(client, home, body)
        assert response.status_code == 201
        data = response.json()
        actual = {a["membership_id"]: a["amount_minor"] for a in data["allocations"]}
        assert actual == expected
        assert [actual[key] for key in sorted(ids)] == (
            [3334, 3333, 3333] if amount == 10000 else [1, 0, 0]
        )
        db_session.expunge_all()
        stored = db_session.get(Bill, UUID(data["id"]))
        assert {str(a.membership_id): a.amount_minor for a in stored.allocations} == expected


@pytest.mark.parametrize("operation", ["create", "list", "detail"])
@pytest.mark.parametrize("actor, expected", [(None, 401), (3, 404), (4, 404)])
def test_access_denied_on_every_endpoint(client, home, operation, actor, expected):
    bill = post_bill(client, home).json()
    path = home.path + (f"/{bill['id']}" if operation == "detail" else "")
    response = client.request(
        "POST" if operation == "create" else "GET",
        path,
        headers={} if actor is None else home.headers[actor],
        json=payload(home) if operation == "create" else None,
    )
    assert response.status_code == expected
    if expected == 404:
        assert response.json() == {"detail": "Household not found"}
    else:
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("operation", ["create", "list", "detail"])
def test_nonexistent_household_is_404(client, home, operation):
    path = f"/households/{uuid4()}/bills"
    if operation == "detail":
        path += f"/{uuid4()}"
    response = client.request(
        "POST" if operation == "create" else "GET",
        path,
        headers=home.headers[0],
        json=payload(home) if operation == "create" else None,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Household not found"}


@pytest.mark.parametrize("target", ["payer", "participant"])
@pytest.mark.parametrize("case", ["missing", "other", "departed"])
def test_invalid_membership_is_clean_422(client, db_session, home, target, case):
    member = {"missing": uuid4(), "other": home.other_member, "departed": home.members[-1]}[case]
    body = payload(home)
    if target == "payer":
        body["payer_membership_id"] = str(member)
    else:
        body["participant_membership_ids"] = [str(home.members[0]), str(member)]
    response = post_bill(client, home, body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid bill input"}
    assert_no_records(db_session)


@pytest.mark.parametrize("case", ["empty", "duplicate"])
def test_invalid_participant_list(client, db_session, home, case):
    body = payload(home)
    body["participant_membership_ids"] = [] if case == "empty" else [str(home.members[0])] * 2
    response = post_bill(client, home, body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid bill input"}
    assert_no_records(db_session)


@pytest.mark.parametrize("amount", [0, -1, 1.5, 10000.0, True, "10000", None, 2**63])
def test_invalid_amount_is_422(client, db_session, home, amount):
    body = payload(home)
    body["amount_minor"] = amount
    response = post_bill(client, home, body)
    assert response.status_code == 422
    assert_no_records(db_session)


@pytest.mark.parametrize(
    "field, value",
    [
        ("payer_membership_id", "invalid"),
        ("participant_membership_ids", ["invalid"]),
        ("participant_membership_ids", "invalid"),
        ("paid_at", "2026-09-01T12:00:00"),
        ("paid_at", None),
        ("description", ""),
        ("description", "x" * 256),
    ],
)
def test_bad_request_shape_or_fields(client, db_session, home, field, value):
    body = payload(home)
    body[field] = value
    assert post_bill(client, home, body).status_code == 422
    assert_no_records(db_session)


def test_required_fields(client, db_session, home):
    response = client.post(home.path, headers=home.headers[0], json={})
    assert response.status_code == 422
    assert_no_records(db_session)


def test_persistence_failure_is_sanitized_and_atomic(client, db_session, home):
    def break_allocation(mapper, connection, target):
        target.membership_id = uuid4()

    event.listen(Allocation, "before_insert", break_allocation)
    try:
        response = post_bill(client, home)
    finally:
        event.remove(Allocation, "before_insert", break_allocation)
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create bill"}
    assert_no_records(db_session)
    assert post_bill(client, home).status_code == 201


@pytest.mark.parametrize("actor", [0, 1])
def test_owner_and_member_list_and_detail_include_only_public_fields(client, home, actor):
    created = post_bill(client, home).json()
    listed = client.get(home.path, headers=home.headers[actor])
    detail = client.get(f"{home.path}/{created['id']}", headers=home.headers[actor])
    assert listed.status_code == detail.status_code == 200
    assert listed.json() == [created]
    assert detail.json() == created
    assert_public_bill(listed.json()[0])
    assert_public_bill(detail.json())


def test_empty_list(client, home):
    response = client.get(home.path, headers=home.headers[1])
    assert response.status_code == 200
    assert response.json() == []


def test_list_is_scoped_ordered_and_eager_loaded(client, db_session, home):
    own = [post_bill(client, home).json() for _ in range(4)]
    body = payload(home)
    body.update(
        payer_membership_id=str(home.other_member),
        participant_membership_ids=[str(home.other_member)],
    )
    foreign = client.post(home.other_path, headers=home.headers[3], json=body)
    assert foreign.status_code == 201
    rows = [db_session.get(Bill, UUID(item["id"])) for item in own]
    early = datetime(2026, 9, 1, tzinfo=UTC)
    late = datetime(2026, 9, 2, tzinfo=UTC)
    for row in rows:
        row.paid_at = early
        row.created_at = early
    rows[0].paid_at = late
    rows[1].created_at = late
    db_session.commit()
    expected = [own[0]["id"], own[1]["id"], *sorted([own[2]["id"], own[3]["id"]])]
    db_session.expunge_all()
    allocation_queries = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if "SELECT" in statement.upper() and "FROM allocations" in statement:
            allocation_queries.append(statement)

    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        response = client.get(home.path, headers=home.headers[1])
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == expected
    assert foreign.json()["id"] not in expected
    assert len(allocation_queries) == 1
    for item in response.json():
        assert_public_bill(item)
        assert len(item["allocations"]) == 2
    assert client.get(home.path, headers=home.headers[1]).json() == response.json()


def test_detail_missing_and_foreign_bill_are_indistinguishable(client, home):
    body = payload(home)
    body.update(
        payer_membership_id=str(home.other_member),
        participant_membership_ids=[str(home.other_member)],
    )
    foreign = client.post(home.other_path, headers=home.headers[3], json=body)
    assert foreign.status_code == 201
    for bill_id in [str(uuid4()), foreign.json()["id"]]:
        response = client.get(f"{home.path}/{bill_id}", headers=home.headers[0])
        assert response.status_code == 404
        assert response.json() == {"detail": "Bill not found"}


@pytest.mark.parametrize(
    "field, value",
    [
        ("allocations", []),
        ("split_method", "FIXED"),
        ("currency", "USD"),
    ],
)
def test_client_controlled_billing_fields_rejected(
    client, db_session, home, monkeypatch, field, value
):
    spy = Mock(wraps=create_equal_bill)
    monkeypatch.setattr(billing, "create_equal_bill", spy)
    body = payload(home)
    body[field] = value
    response = post_bill(client, home, body)
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "extra_forbidden",
                "loc": ["body", field],
                "msg": "Extra inputs are not permitted",
            }
        ]
    }
    spy.assert_not_called()
    assert_no_records(db_session)
