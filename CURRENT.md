# lifhop Current Status

## Current milestone

Step 2 — Authentication and Authorization

Status: Complete

Next milestone: Step 3 — Attachments and S3

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
- `User` ORM model and `users` table migration
- `entries.user_id` foreign key and User ↔ Entry ORM relationship
- Password hashing with Argon2 via `pwdlib`
- User registration via `POST /auth/register`
- User login via `POST /auth/login`
- JWT access tokens
- JWT refresh tokens via `POST /auth/refresh`
- `get_current_user` authentication dependency
- Authenticated Entry creation with ownership assigned from `current_user.id`
- Entry authorization rules restricting list/read/update/delete to the authenticated user's own Entries
- Cross-user access protection returning 404 for resources not owned by the current user

## Current architecture

```text
Client
  |
  v
FastAPI
  |
  +--> Authentication dependencies
  |      |
  |      v
  |    JWT validation
  |      |
  |      v
  |    Current User
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

Authentication flow:

```text
Register
  |
  v
Password hash stored in users

Login
  |
  v
Access token + refresh token

Authenticated request
  |
  v
Authorization: Bearer <access token>
  |
  v
get_current_user
  |
  v
User-scoped Entry access
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
- Entry and User currently use integer auto-increment primary keys.
- `entries.user_id` references `users.id` and is non-nullable.
- SQLAlchemy `relationship()` provides Python-side User ↔ Entry navigation; the foreign key provides the database-level constraint.
- `event_at` represents when the source event occurred.
- `created_at` represents when an Entry was stored in lifhop.
- Passwords are never stored directly; only password hashes are stored.
- Access and refresh JWTs include separate token types.
- Current refresh tokens are stateless JWTs; rotation, revocation, logout, and server-side refresh-token state are intentionally deferred.
- JSONB metadata is intentionally deferred for later learning/migration work.

## Current tests

20 tests pass with:

```bash
pytest -v
```

Coverage includes:

- Health endpoint
- Entry create/read/list/update/delete
- Missing Entry -> 404
- Invalid Entry type -> 422
- Invalid pagination -> 422
- User registration
- Duplicate email -> 409
- User login
- Incorrect password -> 401
- Unauthenticated Entry creation -> 401
- User-scoped Entry listing
- Cross-user single Entry access protection
- Cross-user update protection
- Cross-user delete protection
- Refresh token issuing and refresh flow
- Access token rejected when used as a refresh token

## Next milestone

Step 3 — Attachments and S3

Planned first work:

1. Define the `Attachment` data model
2. Associate Attachments with Entries and Users through ownership rules
3. Decide the initial local-development storage approach before introducing S3
4. Introduce S3 concepts and AWS credentials/IAM safely
5. Implement a presigned upload URL flow
6. Store attachment metadata in PostgreSQL
7. Add secure retrieval/access checks
8. Add integration tests for attachment ownership and upload metadata

Target flow from the roadmap:

```text
Client
  |
  v
API requests presigned URL
  |
  v
S3 presigned URL
  |
  v
Client uploads directly to S3
```

## Known issues / deferred decisions

- UUID vs integer IDs
- JSONB metadata structure
- Step 1 filters (`type`, event date range) are not yet implemented and may be revisited with search/filter work
- Production health/readiness endpoint design
- Test schema creation via Alembic vs `Base.metadata.create_all`
- Refresh token rotation/revocation and logout
- Password reset and email verification
- Production authentication provider choice, including whether to keep direct authentication or later adopt a managed service such as Cognito

## Last update

2026-08-24
