import os

# Isolate tests from developer credentials. Health tests never connect to PostgreSQL.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://test_user:test_placeholder@localhost:5432/sharehome_test"
)
