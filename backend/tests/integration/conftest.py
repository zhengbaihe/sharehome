import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.db.session import get_session
from app.main import create_app


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


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "auth-api-test-secret-not-for-production-123456789")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    get_settings.cache_clear()
    application = create_app()

    def override_session():
        yield db_session

    application.dependency_overrides[get_session] = override_session
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()
        get_settings.cache_clear()
