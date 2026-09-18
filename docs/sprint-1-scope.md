# Sprint 1 scope and decisions

## Current task: foundation only

FastAPI liveness endpoint, settings, empty SQLAlchemy metadata, Alembic scaffolding,
React shell, tests, Compose development services, and CI. No business tables or
migration revisions exist yet. Health means the HTTP process responds; it is not
a database-readiness check. No authentication or financial features exist yet.

## Subsequent Sprint 1 constraints (not implemented)

- Authentication: JWT access token in the Authorization Bearer header. No refresh tokens.
- Money: integer minor units only.
- Splitting: EQUAL only, with deterministic remainder allocation.
- Bill fields include payer_membership_id, amount_minor, and paid_at.
- No separate BillPayment table.
- No invitations, occupancy periods, settlements, percentage/fixed/weighted splitting.
- No AI, OCR, payment gateways, messaging, Redis, microservices, or Kubernetes.

Acceptance example for later work: Alex funds an Internet bill of 10000 minor
units. Alex and Blair receive allocations of 5000 each. Their balances become
+5000 and -5000 respectively. This is not supported by the current foundation.

## Smallest next task

Implement and unit-test a pure equal-split function using integer minor units and
stable participant identifiers. Verify exact totals, deterministic remainder
handling, and invalid input rejection before adding persistence or endpoints.
