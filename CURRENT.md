# lifhop Current Status

## Current milestone

Step 3 — Attachments and S3

Status: In Progress

Previous milestone: Step 2 — Authentication and Authorization — Complete

## Completed work

* FastAPI application bootstrap
* `GET /health`
* PostgreSQL 17 via Docker Compose
* SQLAlchemy 2.x and psycopg setup
* Environment configuration with Pydantic Settings
* Alembic migration setup
* `Entry` ORM model and `entries` table migration
* Entry CRUD API

  * `POST /entries`
  * `GET /entries`
  * `GET /entries/{entry_id}`
  * `PATCH /entries/{entry_id}`
  * `DELETE /entries/{entry_id}`
* Pagination with `limit` and `offset`
* Pydantic request/response schemas for Entry
* pytest-based API integration tests
* Separate `lifhop_test` PostgreSQL database
* FastAPI dependency override for test DB sessions
* Transaction rollback-based test isolation
* `User` ORM model and `users` table migration
* `entries.user_id` foreign key and User ↔ Entry ORM relationship
* Password hashing with Argon2 via `pwdlib`
* User registration via `POST /auth/register`
* User login via `POST /auth/login`
* JWT access tokens
* JWT refresh tokens via `POST /auth/refresh`
* `get_current_user` authentication dependency
* Authenticated Entry creation with ownership assigned from `current_user.id`
* Entry authorization rules restricting list/read/update/delete to the authenticated user's own Entries
* Cross-user access protection returning 404 for resources not owned by the current user
* Initial `Attachment` ORM model

  * Attachment belongs to an Entry through `entry_id`
  * Entry ↔ Attachment ORM relationship
  * S3 object key metadata via `s3_key`
  * filename, MIME type, and optional size metadata
  * upload status using `PENDING` and `UPLOADED`
* Alembic migration generated for the `attachments` table

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
User-scoped resource access
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

* PostgreSQL host port is `5433`; Docker maps host `5433` to container port `5432`.
* SQLAlchemy `Session` is injected through FastAPI `Depends(get_db)`.
* Tests replace `get_db` using `app.dependency_overrides`.
* Entry, User, and Attachment currently use integer auto-increment primary keys.
* `entries.user_id` references `users.id` and is non-nullable.
* `attachments.entry_id` references `entries.id` and is non-nullable.
* Attachment does not currently contain a separate `user_id`; ownership is derived from its Entry.
* SQLAlchemy `relationship()` provides Python-side object navigation, while database foreign keys enforce persistent relational constraints.
* Actual attachment file contents will not be stored in PostgreSQL.
* PostgreSQL stores attachment metadata; S3 will store the actual file contents.
* `Attachment.status` currently supports `PENDING` and `UPLOADED`.
* `Attachment.size` is nullable because file size may not yet be known before an S3 upload is completed.
* `s3_key` uniquely identifies the intended S3 object.
* `event_at` represents when the source event occurred.
* `created_at` represents when an Entry was stored in lifhop.
* Passwords are never stored directly; only password hashes are stored.
* Access and refresh JWTs include separate token types.
* Current refresh tokens are stateless JWTs; rotation, revocation, logout, and server-side refresh-token state are intentionally deferred.
* JSONB metadata is intentionally deferred for later learning/migration work.

## Current tests

20 tests passed at the completion of Step 2 with:

```bash
pytest -v
```

Coverage includes:

* Health endpoint
* Entry create/read/list/update/delete
* Missing Entry -> 404
* Invalid Entry type -> 422
* Invalid pagination -> 422
* User registration
* Duplicate email -> 409
* User login
* Incorrect password -> 401
* Unauthenticated Entry creation -> 401
* User-scoped Entry listing
* Cross-user single Entry access protection
* Cross-user update protection
* Cross-user delete protection
* Refresh token issuing and refresh flow
* Access token rejected when used as a refresh token

Step 3 model and migration changes still need regression-test verification.

## Current Step 3 progress

### Completed

1. Define the initial `Attachment` data model
2. Associate Attachments with Entries through `entry_id`
3. Add Entry ↔ Attachment ORM relationships
4. Generate the Alembic migration for the `attachments` table

Generated migration:

```text
72ee7e9fc709_create_attachments_table
```

### Next

1. Apply and verify the Attachment migration
2. Run the existing regression test suite
3. Design the initial Attachment API
4. Define the attachment creation / upload lifecycle
5. Introduce S3 and presigned URL concepts
6. Add AWS SDK configuration safely
7. Implement presigned upload URL generation
8. Add attachment metadata APIs and ownership authorization
9. Add attachment integration tests
10. Implement secure retrieval

Target upload flow:

```text
Client
  |
  | request attachment upload
  v
lifhop API
  |
  | create Attachment(status=PENDING)
  | generate presigned URL
  v
Client
  |
  | upload file directly
  v
S3
```

## Known issues / deferred decisions

* UUID vs integer IDs
* JSONB metadata structure
* Step 1 filters (`type`, event date range) are not yet implemented and may be revisited with search/filter work
* Production health/readiness endpoint design
* Test schema creation via Alembic vs `Base.metadata.create_all`
* Refresh token rotation/revocation and logout
* Password reset and email verification
* Production authentication provider choice, including whether to keep direct authentication or later adopt a managed service such as Cognito
* Attachment deletion behavior in PostgreSQL vs S3
* How an upload is marked `UPLOADED`
* File size and MIME type validation policy
* Maximum attachment size

## Last update

2026-08-26

