from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select

from app.core.security import hash_password
from app.domain.splitting import SplitValidationError, split_equal
from app.models import (
    Allocation,
    Bill,
    Household,
    HouseholdMembership,
    MembershipStatus,
    SplitMethod,
    User,
)
from app.services import billing
from app.services.billing import BillPersistenceError, BillValidationError, create_equal_bill

PAID_AT = datetime(2026, 9, 1, 12, tzinfo=UTC)
MEMBER_IDS = [UUID(int=1), UUID(int=2), UUID(int=3)]


@pytest.fixture(scope="module")
def stored_hash():
    return hash_password("service-test-password")


@pytest.fixture
def members(db_session, stored_hash):
    home = Household(name="Alex Home")
    result = [
        HouseholdMembership(
            id=member_id,
            household=home,
            user=User(
                email=f"{name.lower()}@example.com", display_name=name, password_hash=stored_hash
            ),
        )
        for member_id, name in zip(MEMBER_IDS, ["Alex", "Blair", "Casey"], strict=True)
    ]
    db_session.add_all(result)
    db_session.commit()
    return result


def inputs(members):
    return dict(
        household_id=members[0].household_id,
        payer_membership_id=members[0].id,
        amount_minor=10000,
        participant_membership_ids=[members[0].id, members[1].id],
        description="Internet",
        paid_at=PAID_AT,
    )


def assert_no_financial_records(session):
    assert session.scalar(select(func.count()).select_from(Bill)) == 0
    assert session.scalar(select(func.count()).select_from(Allocation)) == 0


def test_alex_blair_creation_reuses_domain_and_persists(db_session, members, monkeypatch):
    spy = Mock(wraps=split_equal)
    monkeypatch.setattr(billing, "split_equal", spy)
    result = create_equal_bill(db_session, **inputs(members))
    spy.assert_called_once_with(10000, [str(MEMBER_IDS[0]), str(MEMBER_IDS[1])])
    assert result.household_id == members[0].household_id
    assert result.payer_membership_id == members[0].id
    assert result.amount_minor == 10000
    assert result.description == "Internet"
    assert result.paid_at == PAID_AT
    assert result.split_method == SplitMethod.EQUAL
    expected = {str(MEMBER_IDS[0]): 5000, str(MEMBER_IDS[1]): 5000}
    assert {str(a.membership_id): a.amount_minor for a in result.allocations} == expected
    assert sum(a.amount_minor for a in result.allocations) == result.amount_minor
    bill_id = result.id
    db_session.expunge_all()
    stored = db_session.get(Bill, bill_id)
    assert {str(a.membership_id): a.amount_minor for a in stored.allocations} == expected
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 1
    assert db_session.scalar(select(func.count()).select_from(Allocation)) == 2


@pytest.mark.parametrize("amount", [10000, 1])
@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1)])
def test_remainders_match_domain_for_any_order(db_session, members, amount, order):
    values = inputs(members)
    participant_ids = [members[index].id for index in order]
    values.update(amount_minor=amount, participant_membership_ids=participant_ids)
    result = create_equal_bill(db_session, **values)
    expected = split_equal(amount, [str(member_id) for member_id in participant_ids])
    actual = {str(a.membership_id): a.amount_minor for a in result.allocations}
    assert actual == expected
    assert [actual[str(member_id)] for member_id in MEMBER_IDS] == (
        [3334, 3333, 3333] if amount == 10000 else [1, 0, 0]
    )
    assert sum(actual.values()) == amount
    assert participant_ids == [members[index].id for index in order]


def test_payer_is_not_automatically_a_participant(db_session, members):
    values = inputs(members)
    values["participant_membership_ids"] = [members[1].id]
    result = create_equal_bill(db_session, **values)
    assert len(result.allocations) == 1
    assert result.allocations[0].membership_id == members[1].id
    assert result.allocations[0].amount_minor == 10000


@pytest.mark.parametrize(
    "case",
    [
        "household-missing",
        "payer-missing",
        "payer-other-household",
        "payer-departed",
        "participant-missing",
        "participant-other-household",
        "participant-departed",
    ],
)
def test_ineligible_household_or_members_leave_no_records(db_session, members, case):
    values = inputs(members)
    target = members[0] if case.startswith("payer") else members[1]
    if case == "household-missing":
        values["household_id"] = uuid4()
    elif case == "payer-missing":
        values["payer_membership_id"] = uuid4()
    elif case == "participant-missing":
        values["participant_membership_ids"] = [members[0].id, uuid4()]
    elif case.endswith("other-household"):
        target.household = Household(name="Private unrelated home")
        db_session.commit()
        if case.startswith("payer"):
            values["participant_membership_ids"] = [members[1].id]
    else:
        target.status = MembershipStatus.DEPARTED
        target.departed_at = PAID_AT
        db_session.commit()
    with pytest.raises(BillValidationError) as error:
        create_equal_bill(db_session, **values)
    assert "Private unrelated home" not in str(error.value)
    assert_no_financial_records(db_session)


@pytest.mark.parametrize("participants", [[], [MEMBER_IDS[0], MEMBER_IDS[0]]])
def test_invalid_participants_reuse_split_exception(db_session, members, participants):
    values = inputs(members)
    values["participant_membership_ids"] = participants
    with pytest.raises(SplitValidationError):
        create_equal_bill(db_session, **values)
    assert_no_financial_records(db_session)


@pytest.mark.parametrize("amount", [0, -1, 1.5, True, "10000", None])
def test_invalid_amount_reuses_split_exception(db_session, members, amount):
    values = inputs(members)
    values["amount_minor"] = amount
    with pytest.raises(SplitValidationError):
        create_equal_bill(db_session, **values)
    assert_no_financial_records(db_session)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("amount_minor", 2**63),
        ("description", ""),
        ("description", " "),
        ("description", "x" * 256),
        ("description", None),
        ("paid_at", datetime(2026, 9, 1)),
        ("paid_at", None),
        ("household_id", "bad-id"),
        ("payer_membership_id", "bad-id"),
        ("participant_membership_ids", ["bad-id"]),
    ],
)
def test_invalid_bill_fields_rejected_before_persistence(db_session, members, field, value):
    values = inputs(members)
    values[field] = value
    with pytest.raises(BillValidationError):
        create_equal_bill(db_session, **values)
    assert_no_financial_records(db_session)


def test_equivalent_uuid_representations_are_duplicate_participants(db_session, members):
    values = inputs(members)
    values["participant_membership_ids"] = [members[0].id, members[0].id.hex]
    with pytest.raises(SplitValidationError, match="unique"):
        create_equal_bill(db_session, **values)
    assert_no_financial_records(db_session)


def test_allocation_failure_rolls_back_and_session_can_retry(db_session, members):
    values = inputs(members)
    seen_bills = []

    def break_allocation(mapper, connection, target):
        seen_bills.append(connection.scalar(select(func.count()).select_from(Bill)))
        target.membership_id = uuid4()

    event.listen(Allocation, "before_insert", break_allocation)
    try:
        with pytest.raises(BillPersistenceError, match="Unable to save bill and allocations"):
            create_equal_bill(db_session, **values)
    finally:
        event.remove(Allocation, "before_insert", break_allocation)
    assert seen_bills and all(count == 1 for count in seen_bills)
    assert_no_financial_records(db_session)
    result = create_equal_bill(db_session, **values)
    assert len(result.allocations) == 2
    assert db_session.scalar(select(func.count()).select_from(Bill)) == 1


def test_description_and_timezone_aware_paid_at_preserved(db_session, members):
    values = inputs(members)
    values["description"] = "  September Internet  "
    result = create_equal_bill(db_session, **values)
    assert result.description == values["description"]
    assert result.paid_at == values["paid_at"]
