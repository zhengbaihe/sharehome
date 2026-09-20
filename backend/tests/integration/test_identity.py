from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.db.base import Base
from app.models import Household, HouseholdMembership, MembershipRole, MembershipStatus, User

# Precomputed hash fixture only; no plaintext password is persisted.
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHQxMjM0NTY3OA$" + "A" * 43


def make_user(email="alex@example.com"):
    return User(email=email, password_hash=PASSWORD_HASH, display_name="Alex")


def make_membership(session, **values):
    membership = HouseholdMembership(user=make_user(), household=Household(name="Home"), **values)
    session.add(membership)
    session.commit()
    return membership


def test_user_persistence(db_session):
    user = make_user(" Alex@Example.COM ")
    db_session.add(user)
    db_session.commit()
    user_id = user.id
    db_session.expunge_all()
    stored = db_session.get(User, user_id)
    assert isinstance(stored.id, UUID)
    assert stored.email == "alex@example.com"
    assert stored.password_hash == PASSWORD_HASH
    assert stored.display_name == "Alex"
    assert stored.created_at.tzinfo is not None
    assert stored.updated_at.tzinfo is not None


def test_household_persistence(db_session):
    household = Household(name="Our home")
    db_session.add(household)
    db_session.commit()
    household_id = household.id
    db_session.expunge_all()
    stored = db_session.get(Household, household_id)
    assert isinstance(stored.id, UUID)
    assert stored.name == "Our home"
    assert stored.currency == "MYR"
    assert stored.timezone == "Asia/Kuala_Lumpur"
    assert stored.created_at.tzinfo is not None
    assert stored.updated_at.tzinfo is not None


def test_membership_links_and_defaults(db_session):
    membership_id = make_membership(db_session).id
    db_session.expunge_all()
    stored = db_session.get(HouseholdMembership, membership_id)
    assert stored in stored.user.memberships
    assert stored in stored.household.memberships
    assert stored.user_id == stored.user.id
    assert stored.household_id == stored.household.id
    assert stored.role == MembershipRole.MEMBER
    assert stored.status == MembershipStatus.ACTIVE
    assert stored.joined_at.tzinfo is not None
    assert stored.departed_at is None


def test_duplicate_membership_rejected(db_session):
    original = make_membership(db_session)
    db_session.add(
        HouseholdMembership(user_id=original.user_id, household_id=original.household_id)
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_normalized_email_rejected(db_session):
    db_session.add(make_user())
    db_session.commit()
    db_session.add(make_user(" ALEX@example.com "))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("role", [MembershipRole.OWNER, MembershipRole.MEMBER])
@pytest.mark.parametrize("status", [MembershipStatus.ACTIVE, MembershipStatus.DEPARTED])
def test_roles_and_statuses_persist(db_session, role, status):
    departed_at = datetime.now(UTC) if status == MembershipStatus.DEPARTED else None
    membership_id = make_membership(
        db_session, role=role, status=status, departed_at=departed_at
    ).id
    db_session.expunge_all()
    stored = db_session.get(HouseholdMembership, membership_id)
    assert stored.role == role
    assert stored.status == status
    assert stored.departed_at == departed_at


@pytest.mark.parametrize(("column", "invalid_value"), [("role", "GUEST"), ("status", "INVALID")])
def test_invalid_enum_rejected_by_database(db_session, column, invalid_value):
    membership = make_membership(db_session)
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(f"UPDATE household_memberships SET {column} = :invalid_value WHERE id = :id"),
            {"invalid_value": invalid_value, "id": membership.id},
        )
        db_session.commit()


@pytest.mark.parametrize("column", ["user_id", "household_id"])
def test_missing_foreign_key_rejected(db_session, column):
    membership = make_membership(db_session)
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(f"UPDATE household_memberships SET {column} = :missing WHERE id = :id"),
            {"missing": uuid4(), "id": membership.id},
        )
        db_session.commit()


@pytest.mark.parametrize("parent", ["user", "household"])
def test_parent_deletion_does_not_cascade(db_session, parent):
    membership = make_membership(db_session)
    db_session.delete(getattr(membership, parent))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_direct_unnormalized_email_rejected(db_session):
    db_session.add(make_user())
    db_session.commit()
    with pytest.raises(IntegrityError):
        db_session.execute(text("UPDATE users SET email = ' ALEX@EXAMPLE.COM '"))
        db_session.commit()


def test_updated_at_changes_on_orm_update(db_session):
    user = make_user()
    db_session.add(user)
    db_session.commit()
    old_timestamp = user.updated_at
    # End the transaction that loaded the old value before the update transaction.
    db_session.commit()
    user.display_name = "Alex Updated"
    db_session.commit()
    assert user.updated_at > old_timestamp


def test_migration_upgrade_downgrade_upgrade(empty_database):
    connection, config = empty_database
    assert inspect(connection).get_table_names() == []
    connection.commit()
    command.upgrade(config, "head")
    expected = {"users", "households", "household_memberships", "alembic_version"}
    assert set(inspect(connection).get_table_names()) == expected
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    assert (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        == "0001_initial_identity"
    )
    connection.commit()
    command.downgrade(config, "base")
    assert set(inspect(connection).get_table_names()) <= {"alembic_version"}
    connection.commit()
    command.upgrade(config, "head")
    assert set(inspect(connection).get_table_names()) == expected
    assert connection.scalar(select(User.id).limit(1)) is None
