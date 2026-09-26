# ShareHome — Sprint 1 portfolio summary

## Project overview

ShareHome is a full-stack roommate expense application built with FastAPI,
SQLAlchemy/PostgreSQL and React/TypeScript. Sprint 1 provides authentication,
Households, EQUAL Bills, allocations and derived balances. It is a portfolio
project, not a claimed production deployment.

## Engineering challenges solved

- Preserving every minor unit through deterministic division and remainder allocation.
- Enforcing relational constraints and evolving PostgreSQL through reversible migrations.
- Combining JWT identity with ACTIVE Household membership authorization.
- Persisting a Bill and all allocations atomically, without partial financial records.
- Aggregating paid/allocated totals without join multiplication or stored balance drift.
- Connecting React forms to real APIs with safe money parsing, error handling and
  authentication restoration; making asynchronous component tests deterministic.

## Key engineering decisions

Integer minor units and pure `split_equal()` keep money logic exact and independently
testable. Request, service and domain responsibilities are separated without generic
repository frameworks. PostgreSQL integration tests validate actual database behavior;
SQLite is not a substitute. Alembic owns schema changes. Balances are derived, not
stored. Scope is deliberately limited to EQUAL splitting; no settlement, invitation
workflow or additional split methods are claimed.

## Testing strategy

294 backend tests include 192 PostgreSQL integration tests; 95 frontend tests cover
components and API clients. Coverage includes unit tests, migration round-trips,
constraints/access control and a full Sprint 1 backend acceptance test. Local real
headless Edge acceptance exercised React → FastAPI → PostgreSQL, including refresh
and logout. GitHub Actions checks backend/PostgreSQL, frontend and Compose config.
A full Docker image build remains unverified due to a Docker Hub timeout; successful
browser acceptance used Compose PostgreSQL with local FastAPI/Vite.

## Exact demo scenario

Alex pays ¥100.00 for Internet in a fresh CNY Household. Alex and Blair each receive
a ¥50.00 allocation. Alex's balance is +¥50.00; Blair's is -¥50.00; total is zero.
Both users register normally. Blair's ACTIVE MEMBER relationship is inserted only
as test/demo database preparation because Sprint 1 has no member-add/invite API.
Bill creation and financial displays use the frontend and real backend.

## Resume bullet candidates

- Built a Python/FastAPI expense backend with SQLAlchemy, PostgreSQL and Alembic,
  implementing JWT authentication, household authorization and atomic bill allocation.
- Developed React/TypeScript authentication, household, bill and balance flows with
  exact minor-unit parsing and backend-authoritative financial displays.
- Validated financial rules and access control with pytest/PostgreSQL integration
  tests, Vitest component tests, migration round-trips and GitHub Actions CI.
