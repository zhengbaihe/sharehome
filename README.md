# ShareHome

A full-stack shared-household expense splitting application for roommates.
**Sprint 1 supports EQUAL splitting only.** It records who paid, each member's
allocation, and derived household balances; it does not transfer money.

## Implemented features

- Registration/login with Argon2id password hashing and JWT Bearer access tokens.
- Household creation, list and detail; ACTIVE membership access control and a
  read-only ACTIVE Household member API.
- Bill creation, list and detail with explicit payer/participant selection,
  deterministic EQUAL splitting, and atomic Bill + Allocation persistence.
- Integer minor-unit money handling and CNY as the default Household currency.
- Derived Household balances, including DEPARTED members' historical activity.
- React authentication, Household, Bill and Balance UI; session restoration and
  local logout. Access tokens use sessionStorage; no refresh-token system.
- PostgreSQL integration tests, migration tests and GitHub Actions CI.

## Tech stack

| Backend | Frontend | Engineering |
| --- | --- | --- |
| Python, FastAPI, SQLAlchemy 2.x, PostgreSQL, Alembic, Pydantic Settings, pytest, Ruff | React, TypeScript, Vite, React Router, Vitest, React Testing Library | Docker, Docker Compose, GitHub Actions |

## Architecture and money design

```text
React → FastAPI → service/domain layer → SQLAlchemy → PostgreSQL
```

`split_equal()` is pure deterministic domain logic. It divides integer minor units
and assigns remainder units in sorted participant-ID order. Bill and Allocation
records are persisted atomically. Balances are calculated as paid minus allocated,
not stored, and the frontend displays the backend's allocations/balances.

Money has no floating-point storage: **10000 = ¥100.00**. The frontend converts
decimal text through string/BigInt parsing and rejects amounts outside JavaScript's
safe-integer range. Household currency defaults to `CNY`; the UI renders CNY using
`¥` and retains a readable code prefix for other currencies. Migration 0003 changes
only the default; existing MYR rows and historical amounts are not converted.

## Demo scenario

Alex pays **¥100.00 for Internet**, shared equally by Alex and Blair.

| Member | Paid | Allocation | Balance |
| --- | ---: | ---: | ---: |
| Alex | ¥100.00 | ¥50.00 | +¥50.00 |
| Blair | ¥0.00 | ¥50.00 | -¥50.00 |

Total balance is zero. Positive means owed to the member; negative means owed by
the member. This is not a who-owes-whom or settlement calculation.

Register both users, log in as Alex, and create a Household. Sprint 1 has no
member-add/invite API or UI: for the local demo only, insert Blair's
HouseholdMembership using SQLAlchemy with the new Household ID, Blair's User ID,
`role=MEMBER` and `status=ACTIVE`. This was the sole direct database setup step in
the browser acceptance. Use the frontend for Bill creation, detail and balances.
Do not treat this preparation as a production member-management workflow.

## Running locally

Requirements: Python 3.13 (used in CI), Node.js 22.12+ (Node 22 recommended),
PostgreSQL 17, and Docker Desktop/Engine with Compose v2 when using the supplied DB.
Commands below use PowerShell, starting at the repository root.

```powershell
Copy-Item .env.example .env
```

For a new checkout, replace placeholder database credentials and `JWT_SECRET` in
`.env`. Use a random JWT secret of at least 32 bytes. Keep `DATABASE_URL` consistent
with the database user/password/host port. URL-encode credentials in URLs; Compose's
interpolated development URL needs URL-safe credentials. Do not commit `.env`.

### PostgreSQL via Compose, backend and frontend locally

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -e "./backend[dev]"
docker compose up -d db
cd backend
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload
```

In another terminal, from the repository root:

```powershell
cd frontend
npm ci
npm run dev
```

Frontend: http://localhost:5173. API: http://localhost:8000.
API docs: http://localhost:8000/docs. Health: `GET /health`.
Vite proxies `/api` to `http://127.0.0.1:8000`; set `API_PROXY_TARGET` in the
frontend process environment if the backend uses another port.
Run backend commands from `backend/` so settings find the root `.env`;
environment variables override it. On Linux/macOS use `.venv/bin/python`.

### Full Docker Compose development setup

```powershell
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

Apply migrations before using the app: container startup does not apply them.
Compose configures the frontend proxy to the backend service and waits for DB/API
health checks. Named volumes preserve PostgreSQL data and frontend dependencies.
If dependencies change, run `docker compose run --rm frontend npm ci`.
`docker compose down` stops services without deleting the database volume.
These containers run development servers, not a production deployment.

**Verification boundary:** real browser acceptance passed with Compose PostgreSQL
plus local FastAPI and Vite/React. A full image build attempt was blocked by a
Docker Hub network timeout; successful full Compose image building has not been
verified. Compose configuration validation passed.

## Testing and validation

Latest local results: **294 backend tests passed**, including **192 PostgreSQL
integration tests**, with zero skips; **95 frontend tests passed**. Ruff,
TypeScript checking and frontend production build passed. The Bill loading test
was additionally repeated five times, and the full frontend suite three times.

From `backend/`, configure a dedicated PostgreSQL test database before running:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://test_user:test_placeholder@localhost:5432/sharehome_test'
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m ruff format --check .
.venv/Scripts/python -m pytest -q
```

The URL above is a placeholder: create that database and role first, with permission
to create schemas. Integration tests run Alembic in isolated temporary schemas and
remove those schemas afterward. Without `TEST_DATABASE_URL`, integration tests
skip; with an unavailable configured database, they fail. There is no SQLite fallback.

From `frontend/`:

```powershell
npm test
npm run typecheck
npm run build
```

From the repository root:

```powershell
git diff --check
docker compose --env-file .env.example config --quiet
```

Tests cover pure splitting, security primitives, PostgreSQL constraints and API
access control, atomic persistence, balance aggregation, frontend components/API
clients, and the full Sprint 1 backend acceptance flow. Real headless Edge browser
acceptance verified registration/login, CNY Household and Bill creation, allocations,
balances, refresh/auth restoration and logout protection against FastAPI/PostgreSQL.
This was a local acceptance exercise, not a committed browser E2E framework.

Alembic revisions are `0001_initial_identity`, `0002_bills_allocations` and
`0003_household_currency_cny`. PostgreSQL tests verify 0003 downgrade/re-upgrade
preserves existing tables/data and restores the correct currency default.
GitHub Actions runs backend tests with PostgreSQL, Ruff, a full migration
upgrade/downgrade/upgrade, frontend tests/typecheck/build, and Compose validation.
Run destructive downgrades only on disposable databases; never use `create_all()`
as the migration strategy.

## Future work — not implemented

Residence/occupancy periods, day-weighted splitting, PERCENTAGE and FIXED splitting,
invitation/member-management workflows, and settlement/repayment are future work.
No BillPayment, Bill update/delete, exchange rates or currency conversion is included.

See [scope decisions](docs/sprint-1-scope.md) and the
[portfolio summary](docs/portfolio-summary.md).
