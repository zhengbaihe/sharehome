import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command


@pytest.fixture
def empty_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL integration test requires TEST_DATABASE_URL")
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    if engine.dialect.name != "postgresql":
        engine.dispose()
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL, not SQLite")
    schema = "sharehome_test_" + uuid4().hex
    try:
        with engine.connect() as connection:
            # Only this randomly named test schema is created and removed.
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.commit()
            try:
                connection.execute(text(f'SET search_path TO "{schema}"'))
                connection.commit()
                config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
                config.attributes["connection"] = connection
                yield connection, config
            finally:
                connection.rollback()
                connection.execute(text("SET search_path TO public"))
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
                connection.commit()
    finally:
        engine.dispose()


@pytest.fixture
def db_session(empty_database):
    connection, config = empty_database
    command.upgrade(config, "head")
    with Session(connection) as session:
        yield session
