from uuid import UUID

from sqlalchemy import select

from app.models import Allocation, Bill, HouseholdMembership, MembershipRole, MembershipStatus

PASSWORD = "sprint1-acceptance-test-password"


def test_sprint1_alex_blair_workflow(client, db_session):
    # Registration and authentication use public APIs and actual login tokens.
    alex_registration = client.post(
        "/auth/register",
        json={
            "email": " Alex@Example.COM ",
            "password": PASSWORD,
            "display_name": "Alex",
        },
    )
    blair_registration = client.post(
        "/auth/register",
        json={
            "email": "blair@example.com",
            "password": PASSWORD,
            "display_name": "Blair",
        },
    )
    assert alex_registration.status_code == blair_registration.status_code == 201
    alex_id = alex_registration.json()["id"]
    blair_id = blair_registration.json()["id"]
    assert alex_id != blair_id
    assert alex_registration.json()["email"] == "alex@example.com"
    assert blair_registration.json()["email"] == "blair@example.com"
    assert blair_registration.json()["display_name"] == "Blair"
    login = client.post("/auth/login", json={"email": "alex@example.com", "password": PASSWORD})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["access_token"]
    alex_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/users/me", headers=alex_headers)
    assert me.status_code == 200
    assert me.json()["id"] == alex_id
    assert me.json()["email"] == "alex@example.com"
    assert me.json()["display_name"] == "Alex"
    assert set(me.json()) == {"id", "email", "display_name", "created_at", "updated_at"}
    assert "password_hash" not in me.json()

    household_response = client.post(
        "/households", headers=alex_headers, json={"name": "Alex and Blair"}
    )
    assert household_response.status_code == 201
    household_id = UUID(household_response.json()["id"])
    assert household_response.json()["name"] == "Alex and Blair"
    owner = db_session.scalars(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == household_id,
        )
    ).one()
    assert owner.user_id == UUID(alex_id)
    assert owner.role == MembershipRole.OWNER
    assert owner.status == MembershipStatus.ACTIVE
    alex_membership_id = str(owner.id)

    # The only direct setup write: Sprint 1 intentionally has no invite/join API.
    blair_membership = HouseholdMembership(
        household_id=household_id,
        user_id=UUID(blair_id),
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
    )
    db_session.add(blair_membership)
    db_session.commit()
    db_session.refresh(blair_membership)
    assert blair_membership.user_id == UUID(blair_id)
    assert blair_membership.household_id == household_id
    assert blair_membership.role == MembershipRole.MEMBER
    assert blair_membership.status == MembershipStatus.ACTIVE
    blair_membership_id = str(blair_membership.id)

    bills_path = f"/households/{household_id}/bills"
    created = client.post(
        bills_path,
        headers=alex_headers,
        json={
            "description": "Internet",
            "amount_minor": 10000,
            "payer_membership_id": alex_membership_id,
            "participant_membership_ids": [alex_membership_id, blair_membership_id],
            "paid_at": "2026-09-01T12:00:00Z",
        },
    )
    assert created.status_code == 201
    bill_body = created.json()
    assert bill_body["description"] == "Internet"
    assert bill_body["household_id"] == str(household_id)
    assert bill_body["payer_membership_id"] == alex_membership_id
    assert bill_body["amount_minor"] == 10000
    assert bill_body["split_method"] == "EQUAL"
    expected_allocations = {alex_membership_id: 5000, blair_membership_id: 5000}
    assert len(bill_body["allocations"]) == 2
    assert {
        row["membership_id"]: row["amount_minor"] for row in bill_body["allocations"]
    } == expected_allocations

    # Clear the identity map so later requests read persisted data rather than cached objects.
    db_session.expunge_all()
    detail = client.get(f"{bills_path}/{bill_body['id']}", headers=alex_headers)
    listing = client.get(bills_path, headers=alex_headers)
    assert detail.status_code == listing.status_code == 200
    assert detail.json() == bill_body
    assert listing.json() == [bill_body]

    balances_path = f"/households/{household_id}/balances"
    balance_response = client.get(balances_path, headers=alex_headers)
    assert balance_response.status_code == 200
    rows = balance_response.json()
    assert len(rows) == 2
    assert {
        row["membership_id"]: (row["paid_minor"], row["allocated_minor"], row["balance_minor"])
        for row in rows
    } == {
        alex_membership_id: (10000, 5000, 5000),
        blair_membership_id: (0, 5000, -5000),
    }
    assert sum(row["balance_minor"] for row in rows) == 0

    # An ACTIVE MEMBER can use their own real login token for the same household.
    blair_login = client.post(
        "/auth/login", json={"email": "blair@example.com", "password": PASSWORD}
    )
    assert blair_login.status_code == 200
    assert blair_login.json()["token_type"] == "bearer"
    blair_headers = {"Authorization": f"Bearer {blair_login.json()['access_token']}"}
    blair_household = client.get(f"/households/{household_id}", headers=blair_headers)
    assert blair_household.status_code == 200
    assert blair_household.json() == household_response.json()
    blair_detail = client.get(f"{bills_path}/{bill_body['id']}", headers=blair_headers)
    blair_balances = client.get(balances_path, headers=blair_headers)
    assert blair_detail.status_code == blair_balances.status_code == 200
    assert blair_detail.json() == bill_body
    assert blair_balances.json() == rows

    # Small direct PostgreSQL assertions confirm the final financial records.
    stored_bill = db_session.scalars(select(Bill)).one()
    assert stored_bill.id == UUID(bill_body["id"])
    assert stored_bill.household_id == household_id
    assert stored_bill.description == "Internet"
    assert stored_bill.amount_minor == 10000
    allocations = list(db_session.scalars(select(Allocation)))
    assert len(allocations) == 2
    assert all(row.bill_id == stored_bill.id for row in allocations)
    assert {str(row.membership_id): row.amount_minor for row in allocations} == expected_allocations
    assert sum(row.amount_minor for row in allocations) == 10000
