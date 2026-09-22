from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.core.security import hash_password
from app.db.base import Base
from app.models import Allocation, Bill, Household, HouseholdMembership, SplitMethod, User

PAID_AT = datetime(2026, 9, 1, 12, tzinfo=UTC)


@pytest.fixture(scope="module")
def stored_hash():
    return hash_password("billing-persistence-test-only")


@pytest.fixture
def payer(db_session, stored_hash):
    membership = HouseholdMembership(
        user=User(email="payer@example.com", password_hash=stored_hash, display_name="Payer"),
        household=Household(name="Home"),
    )
    db_session.add(membership)
    db_session.commit()
    return membership


def make_bill(payer, **values):
    fields = dict(
        household_id=payer.household_id,
        payer_membership_id=payer.id,
        description="Internet",
        amount_minor=10000,
        paid_at=PAID_AT,
    )
    fields.update(values)
    return Bill(**fields)


@pytest.fixture
def bill(db_session, payer):
    item = make_bill(payer)
    db_session.add(item)
    db_session.commit()
    return item


@pytest.mark.parametrize("amount", [1, 10000, 2**40])
def test_bill_persistence_and_relationships(db_session, payer, amount):
    item = make_bill(payer, amount_minor=amount)
    db_session.add(item)
    db_session.commit()
    bill_id = item.id
    db_session.expunge_all()
    stored = db_session.get(Bill, bill_id)
    assert isinstance(stored.id, UUID)
    assert stored.description == "Internet"
    assert stored.amount_minor == amount and type(stored.amount_minor) is int
    assert stored.paid_at == PAID_AT and stored.paid_at.tzinfo is not None
    assert stored.split_method == SplitMethod.EQUAL
    assert stored in stored.household.bills
    assert stored in stored.payer_membership.paid_bills
    assert stored.household_id == stored.payer_membership.household_id
    assert stored.created_at.tzinfo is not None
    assert stored.updated_at.tzinfo is not None


@pytest.mark.parametrize("amount", [0, -1])
def test_bill_nonpositive_amount_rejected(db_session, payer, amount):
    db_session.add(make_bill(payer, amount_minor=amount))
    with pytest.raises(IntegrityError) as error:
        db_session.commit()
    assert error.value.orig.diag.constraint_name == "ck_bills_amount_positive"


def test_invalid_split_method_rejected_by_check(db_session, bill):
    with pytest.raises(IntegrityError) as error:
        db_session.execute(
            text("UPDATE bills SET split_method = 'OTHER' WHERE id = :id"), {"id": bill.id}
        )
    assert error.value.orig.diag.constraint_name == "ck_bills_split_method"


@pytest.mark.parametrize("field", ["household_id", "payer_membership_id"])
def test_bill_invalid_foreign_key_rejected(db_session, payer, field):
    db_session.add(make_bill(payer, **{field: uuid4()}))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("field", ["description", "paid_at"])
def test_bill_required_fields_rejected(db_session, payer, field):
    db_session.add(make_bill(payer, **{field: None}))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_bill_updated_at_on_orm_update(db_session, bill):
    previous = bill.updated_at
    db_session.commit()
    bill.description = "Updated internet bill"
    db_session.commit()
    assert bill.updated_at > previous


@pytest.mark.parametrize("amount", [0, 5000, 2**40])
def test_allocation_persistence_and_relationships(db_session, bill, amount):
    allocation = Allocation(bill=bill, membership=bill.payer_membership, amount_minor=amount)
    db_session.add(allocation)
    db_session.commit()
    allocation_id = allocation.id
    db_session.expunge_all()
    stored = db_session.get(Allocation, allocation_id)
    assert isinstance(stored.id, UUID)
    assert stored.amount_minor == amount and type(stored.amount_minor) is int
    assert stored.created_at.tzinfo is not None
    assert stored in stored.bill.allocations
    assert stored in stored.membership.allocations
    assert stored.bill_id == stored.bill.id
    assert stored.membership_id == stored.membership.id


def test_negative_allocation_rejected(db_session, bill):
    db_session.add(Allocation(bill=bill, membership=bill.payer_membership, amount_minor=-1))
    with pytest.raises(IntegrityError) as error:
        db_session.commit()
    assert error.value.orig.diag.constraint_name == "ck_allocations_amount_nonnegative"


def test_duplicate_allocation_rejected(db_session, bill):
    fields = dict(bill_id=bill.id, membership_id=bill.payer_membership_id, amount_minor=1)
    db_session.add(Allocation(**fields))
    db_session.commit()
    db_session.add(Allocation(**fields))
    with pytest.raises(IntegrityError) as error:
        db_session.commit()
    assert error.value.orig.diag.constraint_name == "uq_allocations_bill_membership"


@pytest.mark.parametrize("field", ["bill_id", "membership_id"])
def test_allocation_invalid_foreign_key_rejected(db_session, bill, field):
    fields = dict(bill_id=bill.id, membership_id=bill.payer_membership_id, amount_minor=1)
    fields[field] = uuid4()
    db_session.add(Allocation(**fields))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("parent", ["bill", "household", "membership"])
def test_financial_records_are_not_cascade_deleted(db_session, bill, parent):
    allocation = Allocation(bill=bill, membership=bill.payer_membership, amount_minor=10000)
    db_session.add(allocation)
    db_session.commit()
    target = {"bill": bill, "household": bill.household, "membership": bill.payer_membership}[
        parent
    ]
    db_session.delete(target)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.scalar(select(Allocation.id)) is not None
    assert db_session.scalar(select(Bill.id)) is not None


def test_bill_exposes_multiple_allocations(db_session, bill, stored_hash):
    other = HouseholdMembership(
        household=bill.household,
        user=User(email="other@example.com", password_hash=stored_hash, display_name="Other"),
    )
    db_session.add(other)
    db_session.add_all(
        [
            Allocation(bill=bill, membership=bill.payer_membership, amount_minor=1),
            Allocation(bill=bill, membership=other, amount_minor=0),
        ]
    )
    db_session.commit()
    bill_id = bill.id
    db_session.expunge_all()
    assert sorted(item.amount_minor for item in db_session.get(Bill, bill_id).allocations) == [0, 1]


def test_0002_round_trip_preserves_identity(empty_database, stored_hash):
    connection, config = empty_database
    command.upgrade(config, "0001_initial_identity")
    with Session(connection) as session:
        member = HouseholdMembership(
            user=User(
                email="preserved@example.com", password_hash=stored_hash, display_name="Preserved"
            ),
            household=Household(name="Preserved home"),
        )
        session.add(member)
        session.commit()
        ids = member.id, member.user_id, member.household_id
        session.commit()
    command.upgrade(config, "0002_bills_allocations")
    with Session(connection) as session:
        bill = Bill(
            household_id=ids[2],
            payer_membership_id=ids[0],
            description="Internet",
            amount_minor=10000,
            paid_at=PAID_AT,
        )
        session.add(Allocation(bill=bill, membership_id=ids[0], amount_minor=10000))
        session.commit()
    identity = {"users", "households", "household_memberships", "alembic_version"}
    assert set(inspect(connection).get_table_names()) == identity | {"bills", "allocations"}
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    connection.commit()
    command.downgrade(config, "0001_initial_identity")
    assert set(inspect(connection).get_table_names()) == identity
    assert connection.scalar(text("SELECT id FROM household_memberships")) == ids[0]
    assert connection.scalar(text("SELECT id FROM users")) == ids[1]
    assert connection.scalar(text("SELECT id FROM households")) == ids[2]
    assert (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        == "0001_initial_identity"
    )
    connection.commit()
    command.upgrade(config, "0002_bills_allocations")
    assert set(inspect(connection).get_table_names()) == identity | {"bills", "allocations"}
    assert connection.scalar(text("SELECT count(*) FROM bills")) == 0
    assert connection.scalar(text("SELECT count(*) FROM allocations")) == 0
    assert connection.scalar(text("SELECT id FROM users")) == ids[1]
    assert (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        == "0002_bills_allocations"
    )
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
