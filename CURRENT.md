# lifhop Current Status

## Current milestone

Step 4 — Import Framework

Status: Ready to Start

Previous milestone: Step 3 — Attachments and S3 — Complete

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
- `Attachment` ORM model and migration
  - Attachment belongs to an Entry through `entry_id`
  - Entry ↔ Attachment ORM relationship
  - S3 object key metadata via `s3_key`
  - filename, MIME type, and optional size metadata
  - upload status using `PENDING` and `UPLOADED`
- Attachment Pydantic schemas
  - `AttachmentCreate`
  - `AttachmentResponse`
  - `AttachmentUploadResponse`
  - `AttachmentDownloadResponse`
- S3 integration with boto3
  - local development uses the `lifhop-dev` AWS CLI profile
  - bucket and region are provided through application settings
  - no AWS access keys are stored in the repository
- Attachment upload flow
  - `POST /entries/{entry_id}/attachments`
  - authenticated Entry ownership check
  - server-generated unique `s3_key`
  - creates Attachment with `PENDING` status
  - generates a temporary presigned S3 PUT URL
  - client uploads file contents directly to S3
- Attachment completion flow
  - `POST /entries/{entry_id}/attachments/{attachment_id}/complete`
  - validates ownership through Attachment -> Entry -> User
  - checks S3 object existence with `HeadObject`
  - returns 409 when the expected S3 object does not exist
  - changes status from `PENDING` to `UPLOADED` only after object existence is confirmed
- Secure attachment download flow
  - `GET /entries/{entry_id}/attachments/{attachment_id}/download`
  - validates ownership before issuing access
  - rejects `PENDING` attachments
  - generates a temporary presigned S3 GET URL
  - actual file contents are downloaded directly from S3
- Attachment tests cover successful and failure paths without requiring real AWS calls
  - presigned URL generation is mocked in normal tests
  - unauthenticated access
  - nonexistent Entry
  - cross-user access
  - invalid negative size
  - upload completion success
  - missing S3 object on completion
  - secure download success
  - download rejected while `PENDING`
  - cross-user download protection
- Full pytest suite confirmed passing locally after Step 3 implementation
- Manual S3 integration verified successfully
  - presigned PUT upload to S3
  - `HeadObject`-based completion path
  - presigned GET download through the API
  - downloaded file contents verified

## Current architecture

```text
Client
  |
  +------------------------------+
  |                              |
  | API requests                 | presigned PUT / GET
  v                              v
FastAPI                         S3
  |
  +--> Authentication dependencies
  |      |
  |      v
  |    JWT validation
  |      |
  |      v
  |    Current User
  |
  +--> Attachment ownership checks
  |
  +--> boto3
  |      |
  |      +--> Presigned URLs
  |      +--> HeadObject
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

Completed attachment lifecycle:

```text
Client
  |
  | 1. POST attachment metadata
  v
lifhop API
  |
  | 2. verify Entry ownership
  | 3. create Attachment(status=PENDING)
  | 4. generate presigned PUT URL
  v
Client
  |
  | 5. upload file directly
  v
S3

Client
  |
  | 6. POST complete
  v
lifhop API
  |
  | 7. HeadObject verifies object exists
  | 8. status -> UPLOADED
  v
PostgreSQL

Client
  |
  | 9. request download
  v
lifhop API
  |
  | 10. verify ownership and UPLOADED status
  | 11. generate presigned GET URL
  v
Client
  |
  | 12. download directly
  v
S3
```

## Important implementation notes

- PostgreSQL host port is `5433`; Docker maps host `5433` to container port `5432`.
- SQLAlchemy `Session` is injected through FastAPI `Depends(get_db)`.
- Tests replace `get_db` using `app.dependency_overrides`.
- Entry, User, and Attachment currently use integer auto-increment primary keys.
- `entries.user_id` references `users.id` and is non-nullable.
- `attachments.entry_id` references `entries.id` and is non-nullable.
- Attachment does not contain a separate `user_id`; ownership is derived from its Entry.
- SQLAlchemy `relationship()` provides Python-side object navigation, while database foreign keys enforce persistent relational constraints.
- PostgreSQL stores attachment metadata only; actual attachment file contents are stored in S3.
- `Attachment.status` currently supports `PENDING` and `UPLOADED`.
- `Attachment.size` is nullable and validated as non-negative when provided by the client.
- `s3_key` is generated server-side and uniquely identifies the intended S3 object.
- `s3_key` does not include the bucket name, allowing storage configuration to change without rewriting database keys.
- `s3_key` is not exposed in the public Attachment response schema.
- Presigned upload/download URLs are temporary values and are not stored in PostgreSQL.
- Current `s3_key` format includes user id, entry id, a random UUID, and the original filename to avoid object-key collisions.
- Local AWS authentication uses credentials stored by AWS CLI outside the repository and selected through the `lifhop-dev` profile.
- Normal pytest runs mock AWS-facing functions so tests do not depend on network access, credentials, or the real S3 bucket.
- `event_at` represents when the source event occurred.
- `created_at` represents when an Entry was stored in lifhop.
- Passwords are never stored directly; only password hashes are stored.
- Access and refresh JWTs include separate token types.
- Current refresh tokens are stateless JWTs; rotation, revocation, logout, and server-side refresh-token state are intentionally deferred.
- JSONB metadata is intentionally deferred for later learning/migration work.

## Current tests

The full pytest suite was confirmed passing locally at Step 3 completion.

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
- Attachment creation and metadata validation
- Attachment authentication and ownership protection
- Presigned upload response behavior
- Attachment completion with S3 object existence validation
- Rejection of completion when the S3 object is missing
- Secure presigned download behavior
- Rejection of downloads for `PENDING` attachments
- Cross-user attachment download protection

## Step 3 completion summary

Step 3 — Attachments and S3 is complete.

The completed implementation demonstrates:

1. S3 object storage and object keys
2. IAM-based AWS access for local development
3. boto3 and the AWS credential/profile chain
4. Presigned PUT URLs for direct client uploads
5. Attachment metadata stored separately in PostgreSQL
6. `PENDING` -> `UPLOADED` lifecycle management
7. S3 `HeadObject` validation before marking an upload complete
8. Presigned GET URLs for secure downloads
9. Resource ownership checks before issuing storage access
10. Mocking AWS dependencies in automated tests

## Next — Step 4: Import Framework

Start the generic external-data ingestion architecture defined in `ROADMAP.md`.

Initial direction:

1. Revisit the common Entry representation needed by importers
2. Define the importer abstraction and normalization boundary
3. Start with a simple Markdown importer
4. Convert imported content into normal lifhop Entries
5. Keep provider-specific parsing outside the core Entry model
6. Add tests before moving to ChatGPT-specific import behavior

Do not introduce queues or background workers yet; those are intentionally deferred to later roadmap steps.

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
- File size and MIME type validation policy
- Maximum attachment size
- Presigned URL expiration duration
- Cleanup policy for abandoned `PENDING` Attachments and orphaned S3 objects

## Last update

2026-08-27
