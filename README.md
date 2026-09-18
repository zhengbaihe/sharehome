# ShareHome

A shared household expense project. **Current status: Sprint 1 engineering
foundation, EQUAL domain splitting, and initial identity persistence.** User,
Household, and HouseholdMembership models exist; authentication, bills, allocations,
and balances are not implemented.
See [the scope decisions](docs/sprint-1-scope.md).

## Structure

- `backend/`: Python 3.13, FastAPI, SQLAlchemy 2.x, psycopg, Pydantic Settings,
  Alembic, pytest, and Ruff.
- `frontend/`: React, TypeScript, Vite, Vitest, and Testing Library.
- `docs/`: scope and engineering decisions.
- `.github/workflows/ci.yml`: backend, frontend, and Compose checks.

## Docker development

Prerequisites: Docker Engine/Desktop with Compose v2.

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell).
2. The example contains local placeholders only. Use matching database credentials
   in `DATABASE_URL` for host development. URL-encode credentials in URLs; use
   URL-safe credentials for Compose's interpolated development URL.
3. Run `docker compose up --build` from the repository root.

Frontend: http://localhost:5173. API: http://localhost:8000.
API docs: http://localhost:8000/docs. `GET /health` returns `{"status":"ok"}`.
The frontend dev proxy exposes the same endpoint at `/api/health`.

Compose waits for PostgreSQL and backend health checks. Database data persists in
a named volume. Source mounts enable reload. If frontend dependencies change,
run `docker compose run --rm frontend npm ci` to update its dependency volume.
Stop services with `docker compose down`; this preserves database data.
These Dockerfiles run development servers and are not a production deployment.

## Host development (PowerShell)

Prerequisites: Python 3.13 and Node.js 22.12+ (Node 22 recommended).
Copy the environment example as above. From the repository root:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -e "./backend[dev]"
docker compose up -d db
cd backend
.venv/Scripts/python -m uvicorn app.main:app --reload
```

In another terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

On Linux/macOS, replace `.venv/Scripts/python` with `.venv/bin/python`.
Run backend commands from `backend/` so settings locate the root `.env`.
Environment variables override the file. `DATABASE_URL` is required, but liveness
does not open a database connection. The Vite proxy avoids needing CORS for local
browser requests; no authentication settings are configured yet.

## Checks

From `backend/`:

```powershell
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m alembic upgrade head --sql
```

From `frontend/`:

```powershell
npm test
npm run typecheck
npm run build
```

From the repository root (no database or Docker daemon needed):

```powershell
docker compose --env-file .env.example config --quiet
```

Unit and health tests need no database. PostgreSQL integration tests skip unless
`TEST_DATABASE_URL` is set to a dedicated test database. For example, from `backend/`:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://test_user:test_placeholder@localhost:5432/sharehome_test'
.venv/Scripts/python -m pytest -q
```

Create that dedicated database and role beforehand. Tests need permission to create
schemas. They apply Alembic migrations in isolated temporary schemas and remove
only those schemas after each test. A configured but unavailable database fails the
tests. CI provides PostgreSQL and runs these integration tests.

## Migrations

Alembic imports all implemented models. Revision `0001_initial_identity` creates
`users`, `households`, and `household_memberships`, including foreign keys, unique
constraints, role/status checks, and a membership user index. It creates no future
business tables. Run from `backend/` with DATABASE_URL configured:

```powershell
.venv/Scripts/python -m alembic upgrade head
```

On a disposable database only, verify the reversible migration with
`alembic downgrade base` followed by `alembic upgrade head`. Downgrading drops the
three tables and their data. Never use `create_all()` as a migration strategy.

## Next task

Implement and test password hashing/verification helpers before adding registration
or login routes. Persistence currently accepts already-computed hashes only.
