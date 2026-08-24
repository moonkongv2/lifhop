# lifhop Current Status

## Current milestone

Step 2 — Authentication and Authorization

Status: Starting

## Completed work

- FastAPI application bootstrap
- `GET /health`
- PostgreSQL 17 via Docker Compose
- SQLAlchemy 2.x and psycopg setup
- Environment configuration with Pydantic Settings
- Alembic migration setup
- `Entry` ORM model and `entries` table migration
- Entry CRUD API
  - `POST /entries`
  - `GET /entries`
  - `GET /entries/{entry_id}`
  - `PATCH /entries/{entry_id}`
  - `DELETE /entries/{entry_id}`
- Pagination with `limit` and `offset`
- Pydantic request/response schemas for Entry
- pytest-based API integration tests
- Separate `lifhop_test` PostgreSQL database
- FastAPI dependency override for test DB sessions
- Transaction rollback-based test isolation

## Current architecture

```text
Client
  |
  v
FastAPI
  |
  v
Pydantic validation
  |
  v
API router
  |
  v
SQLAlchemy Session
  |
  v
psycopg
  |
  v
PostgreSQL
```

Development database:

```text
postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop
```

Test database:

```text
postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test
```

## Important implementation notes

- PostgreSQL host port is `5433`; Docker maps host `5433` to container port `5432`.
- SQLAlchemy `Session` is injected through FastAPI `Depends(get_db)`.
- Tests replace `get_db` using `app.dependency_overrides`.
- Entry currently uses an integer auto-increment primary key.
- `event_at` represents when the source event occurred.
- `created_at` represents when an Entry was stored in lifhop.
- JSONB metadata is intentionally deferred for later learning/migration work.
- Authentication and authorization are not implemented yet.

## Current tests

Tests currently cover:

- Health endpoint
- Entry create
- Entry read
- Entry list
- Entry update
- Entry delete
- Missing Entry -> 404
- Invalid Entry type -> 422
- Invalid pagination -> 422

Run with:

```bash
pytest -v
```

## In progress

Step 2 — Authentication and Authorization

Immediate design work:

1. Define the `User` ORM model
2. Create the `users` table migration
3. Associate Entries with Users via `user_id`
4. Add registration and password hashing
5. Add login and token handling
6. Add `get_current_user` dependency
7. Restrict Entry CRUD to the authenticated user

## Known issues / deferred decisions

- UUID vs integer IDs
- JSONB metadata structure
- Production health/readiness endpoint design
- Test schema creation via Alembic vs `Base.metadata.create_all`
- Production authentication provider choice, including whether to keep direct authentication or later adopt a managed service such as Cognito

## Last update

2026-08-24
