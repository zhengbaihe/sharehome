# Foundation validation

Validated on Windows with Python 3.13 and Node.js 24.19.0. Docker and CI are
configured for Python 3.13 and Node.js 22; the hosted CI workflow has not run yet.

## Commands and results

- `python -m venv backend/.venv`: passed.
- `backend/.venv/Scripts/python -m pip install -e "./backend[dev]"`: passed.
- `npm.cmd install` (frontend): passed; generated package-lock.json.
- `npm.cmd install --save-dev vitest@^4.1.11`: patched the initial audit finding.
- `python -m ruff check --fix .` and `python -m ruff format .` (backend venv):
  corrected Alembic import ordering and formatting.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed, 10 files formatted.
- `python -m pytest -q`: passed, 2 tests; 2 upstream deprecation warnings.
- `python -m alembic upgrade head --sql`: passed with placeholder DATABASE_URL;
  no migration revisions or business schema exists.
- `python -m uvicorn app.main:app --host 127.0.0.1 --port 18000`: started.
- `Invoke-WebRequest http://127.0.0.1:18000/health`: HTTP 200, {"status":"ok"}.
  The smoke-test server was stopped afterward.
- `npm.cmd test`: passed, 1 test on Vitest 4.1.11.
- `npm.cmd run typecheck`: passed.
- `npm.cmd run build`: passed.
- `npm.cmd audit`: zero vulnerabilities reported.
- `docker compose --env-file .env.example config --quiet`: passed, exit 0.
- `docker version`: CLI available; Docker Desktop Linux engine unavailable.

## Limitations

Container image builds, Compose startup, and live PostgreSQL connectivity were
not verified because the Docker engine was not running. The health endpoint is
process liveness, not database readiness. CI execution is pending a future push;
no commit or push was performed.

Backend TestClient emits upstream deprecations concerning httpx and AnyIO's
BlockingPortal alias. They do not fail the tests. npm also emitted a transitive
whatwg-encoding deprecation and an esbuild install-script approval notice; the
frontend tests and production build completed successfully.

Local dependencies and generated outputs are ignored by Git. Environment values
used for validation were placeholders, supplied to the process, not real secrets.

## Smallest next task

Implement a pure EQUAL splitting function with integer minor units, stable
remainder allocation, and unit tests. No database changes are needed for that task.
