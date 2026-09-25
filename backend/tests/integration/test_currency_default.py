"""Verify currency defaults with actual Alembic migrations on PostgreSQL."""

from datetime import UTC, datetime
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from alembic import command
from app.db.base import Base
from app.models import Allocation, Bill, HouseholdMembership, User


def assert_server_default(connection, expected):
    # Raw SQL deliberately omits currency, bypassing SQLAlchemy's Python default.
    with connection.begin_nested() as savepoint:
        currency = connection.scalar(
            text(
                "INSERT INTO households (id, name) VALUES (:id, 'Default probe') RETURNING currency"
            ),
            {"id": uuid4()},
        )
        assert currency == expected
        savepoint.rollback()


def schema_without_currency_default(connection):
    inspector = inspect(connection)
    result = {}
    for table in inspector.get_table_names():
        if table == "alembic_version":
            continue
        columns = inspector.get_columns(table)
        for column in columns:
            column["type"] = str(column["type"])
            if table == "households" and column["name"] == "currency":
                column["default"] = "currency default intentionally ignored"
        result[table] = (
            columns,
            inspector.get_pk_constraint(table),
            inspector.get_foreign_keys(table),
            inspector.get_unique_constraints(table),
            inspector.get_check_constraints(table),
            inspector.get_indexes(table),
        )
    return result


def persisted_rows(connection):
    return {
        table: connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
        for table in ("users", "households", "household_memberships", "bills", "allocations")
    }


def test_0003_currency_default_round_trip_preserves_schema_and_data(empty_database):
    connection, config = empty_database
    command.upgrade(config, "0001_initial_identity")
    assert_server_default(connection, "MYR")
    legacy_id = uuid4()
    connection.execute(
        text("INSERT INTO households (id, name) VALUES (:id, 'Legacy MYR home')"),
        {"id": legacy_id},
    )
    connection.commit()
    command.upgrade(config, "0002_bills_allocations")
    with Session(connection) as session:
        member = HouseholdMembership(
            household_id=legacy_id,
            user=User(
                email="currency@example.com",
                password_hash="$argon2id$test-fixture-hash",
                display_name="Alex",
            ),
        )
        session.add(member)
        session.flush()
        bill = Bill(
            household_id=legacy_id,
            payer_membership_id=member.id,
            description="Legacy internet",
            amount_minor=10000,
            paid_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        session.add(Allocation(bill=bill, membership_id=member.id, amount_minor=10000))
        session.commit()
    expected_schema = schema_without_currency_default(connection)
    expected_rows = persisted_rows(connection)
    connection.commit()

    for direction, revision, currency in (
        (command.upgrade, "0003_household_currency_cny", "CNY"),
        (command.downgrade, "0002_bills_allocations", "MYR"),
        (command.upgrade, "0003_household_currency_cny", "CNY"),
    ):
        direction(config, revision)
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == revision
        assert_server_default(connection, currency)
        assert schema_without_currency_default(connection) == expected_schema
        assert persisted_rows(connection) == expected_rows
        assert (
            connection.scalar(
                text("SELECT currency FROM households WHERE id = :id"), {"id": legacy_id}
            )
            == "MYR"
        )
        connection.commit()

    assert (
        compare_metadata(
            MigrationContext.configure(connection, opts={"compare_server_default": True}),
            Base.metadata,
        )
        == []
    )
