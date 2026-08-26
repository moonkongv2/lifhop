# lifhop Current Status

## Current milestone

Step 3 — Attachments and S3

Status: In Progress

Previous milestone: Step 2 — Authentication and Authorization — Complete

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
- Initial `Attachment` ORM model
  - Attachment belongs to an Entry through `entry_id`
  - Entry ↔ Attachment ORM relationship
  - S3 object key metadata via `s3_key`
  - filename, MIME type, and optional size metadata
  - upload status using `PENDING` and `UPLOADED`
- Alembic migration for the `attachments` table
  - revision `72ee7e9fc709`
- Attachment Pydantic schemas
  - `AttachmentCreate`
  - `AttachmentResponse`
  - `AttachmentUploadResponse`
- Initial Attachment creation API
  - `POST /entries/{entry_id}/attachments`
  - authenticated Entry ownership check
  - server-generated unique `s3_key`
  - creates Attachment with `PENDING` status
  - returns Attachment metadata only for now
- Initial Attachment API test
  - creates an Entry
  - creates `report.pdf` metadata for that Entry
  - verifies HTTP 201 and returned metadata

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

Current data ownership model:

```text
User
  |
  +-- Entry
       |
       +-- Attachment
```

Attachment ownership is derived through the parent Entry:

```text
Attachment
  |
  v
Entry
  |
  v
User
```

Target attachment upload flow:

```text
Client
  |
  | 1. request attachment upload metadata
  v
lifhop API
  |
  | 2. verify Entry ownership
  | 3. create Attachment(status=PENDING)
  | 4. generate presigned upload URL
  v
Client
  |
  | 5. upload file directly
  v
S3
```

The current implementation stops after step 3. Presigned S3 upload URL generation has not yet been implemented.

## Important implementation notes

- PostgreSQL host port is `5433`; Docker maps host `5433` to container port `5432`.
- SQLAlchemy `Session` is injected through FastAPI `Depends(get_db)`.
- Tests replace `get_db` using `app.dependency_overrides`.
- Entry, User, and Attachment currently use integer auto-increment primary keys.
- `entries.user_id` references `users.id` and is non-nullable.
- `attachments.entry_id` references `entries.id` and is non-nullable.
- Attachment does not contain a separate `user_id`; ownership is derived from its Entry.
- SQLAlchemy `relationship()` provides Python-side object navigation, while database foreign keys enforce persistent relational constraints.
- Actual attachment file contents are not stored in PostgreSQL.
- PostgreSQL stores attachment metadata; S3 will store the actual file contents.
- `Attachment.status` currently supports `PENDING` and `UPLOADED`.
- `Attachment.size` is nullable and validated as non-negative when provided by the client.
- `s3_key` is generated server-side and uniquely identifies the intended S3 object.
- `s3_key` is not exposed in the current public Attachment response schema.
- `upload_url` is modeled in `AttachmentUploadResponse` but is not yet produced by the API.
- Presigned upload URLs should be temporary values and should not be stored as Attachment database columns.
- Current `s3_key` format includes user id, entry id, a random UUID, and the original filename to avoid object-key collisions.
- `event_at` represents when the source event occurred.
- `created_at` represents when an Entry was stored in lifhop.
- Passwords are never stored directly; only password hashes are stored.
- Access and refresh JWTs include separate token types.
- Current refresh tokens are stateless JWTs; rotation, revocation, logout, and server-side refresh-token state are intentionally deferred.
- JSONB metadata is intentionally deferred for later learning/migration work.

## Current tests

20 tests were confirmed passing at the completion of Step 2.

A new Attachment creation test now exists in `tests/test_attachments.py`.

The repository state confirms the test implementation exists, but the latest full `pytest` execution result is not recorded in the repository and should be verified locally before treating Step 3 API work as complete.

Existing coverage includes:

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
- Basic Attachment creation metadata behavior

## Current Step 3 progress

### Completed in code

1. Define the initial `Attachment` data model
2. Associate Attachments with Entries through `entry_id`
3. Add Entry ↔ Attachment ORM relationships
4. Add the Attachment Alembic migration
5. Add Attachment request/response schemas
6. Add the initial authenticated Attachment creation endpoint
7. Generate unique server-side `s3_key` values
8. Add the first Attachment creation test

### Next

1. Verify the latest migration state and run the full test suite locally
2. Add Attachment ownership/failure tests
   - unauthenticated request -> 401
   - nonexistent Entry -> 404
   - another user's Entry -> 404
   - invalid negative size -> 422
3. Introduce S3 and presigned URL concepts without changing unrelated architecture
4. Add the minimal AWS SDK dependency/configuration safely
5. Generate a presigned upload URL for the created Attachment
6. Change `POST /entries/{entry_id}/attachments` to return `AttachmentUploadResponse`
7. Add tests around presigned URL behavior without requiring real AWS calls in normal tests
8. Define how an upload becomes `UPLOADED`
9. Implement secure attachment retrieval/download

## Known issues / deferred decisions

- UUID vs integer IDs
- JSONB metadata structure
- Step 1 filters (`type`, event date range) are not yet implemented and may be revisited with search/filter work
- Production health/readiness endpoint design
- Test schema creation via Alembic vs `Base.metadata.create_all`
- Refresh token rotation/revocation and logout
- Password reset and email verification
- Production authentication provider choice, including whether to keep direct authentication or later adopt a managed service such as Cognito
- Attachment deletion behavior in PostgreSQL vs S3
- How an upload is marked `UPLOADED`
- File size and MIME type validation policy
- Maximum attachment size
- Presigned URL expiration duration

## Last update

2026-08-26
