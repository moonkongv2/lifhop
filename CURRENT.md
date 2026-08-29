# lifhop Current Status

## Current milestone

Step 4 — Import Framework

Status: In Progress

Previous milestone: Step 3 — Attachments and S3 — Complete

## Completed work

- FastAPI application bootstrap
- `GET /health`
- PostgreSQL 17 via Docker Compose
- SQLAlchemy 2.x and psycopg setup
- Environment configuration with Pydantic Settings
- Alembic migration setup
- Entry CRUD API with pagination and Pydantic schemas
- pytest-based API integration tests with isolated test PostgreSQL database
- User model, registration, login, JWT access/refresh tokens, and authorization
- Entry ownership enforcement and cross-user protection
- Attachment ORM model, schemas, ownership checks, and S3 integration
- Presigned PUT upload flow
- Attachment completion flow with S3 `HeadObject`
- Secure presigned GET download flow
- Attachment tests with mocked AWS-facing behavior
- Manual S3 integration verification
- Full pytest suite confirmed passing after Step 3

## Step 4 progress

### Step 4-0 — Source Format Survey

Reviewed representative source categories:

```text
Documents
├── Markdown
└── Notion

AI Conversations
├── ChatGPT
├── Claude
└── Gemini

Coding Agent Sessions
├── Codex CLI
└── Claude Code

Development Systems
└── GitHub
```

Key architecture conclusion:

```text
External Source
      |
      v
Provider Parser / Adapter
      |
      v
Canonical Item
      |
      v
Entry Normalizer
      |
      v
Entry
```

Provider-specific raw formats should not leak into the core Entry model.

`ROADMAP.md` was updated to reflect the canonical-item architecture, expanded source set, and Step 11 abstraction-validation goals.

### Step 4-1 — Canonical Model

Canonical import models were introduced under:

```text
app/importers/
├── __init__.py
└── canonical.py
```

Initial provider-neutral types include:

```text
SourceProvider
CanonicalKind
CanonicalMessage
DocumentPayload
ConversationPayload
DevSessionPayload
CanonicalItem
```

Current canonical categories:

```text
DOCUMENT
CONVERSATION
DEV_SESSION
```

Provider and content kind are intentionally separated:

```text
provider = where the data came from
kind     = what kind of information it represents
```

Examples:

```text
ChatGPT     -> CONVERSATION
Claude      -> CONVERSATION
Markdown    -> DOCUMENT
Codex CLI   -> DEV_SESSION
Claude Code -> DEV_SESSION
```

Structured conversation/session data is preserved until Entry normalization rather than being flattened immediately into a string.

Canonical payloads use a Pydantic discriminated union with `payload.kind` as the discriminator. The outer `CanonicalItem` does not duplicate `kind`, keeping `payload.kind` as the single source of truth.

Pydantic's default extra-field behavior is currently retained. `extra="forbid"` was considered but intentionally deferred while the canonical schema is still evolving and before several real providers have been implemented.

## Step 4 tests

Canonical import tests currently cover:

- `DocumentPayload` creation
- `ConversationPayload` message structure preservation
- `CanonicalItem` with conversation payload
- discriminated-union validation
- rejection of payloads whose declared `kind` does not match their structure

All Step 4-1 canonical model tests are passing.

## Current architecture

```text
External Source
      |
      v
Provider Parser / Adapter
      |
      v
Canonical Model
      |
      v
Entry Normalizer
      |
      v
Entry ORM
      |
      v
PostgreSQL
```

Canonical models are application-layer transfer models. They are intentionally separate from raw provider formats, API request schemas, and database ORM models.

## Important implementation notes

- PostgreSQL host port is `5433`; Docker maps host `5433` to container port `5432`.
- SQLAlchemy `Session` is injected through FastAPI `Depends(get_db)`.
- Tests replace `get_db` using `app.dependency_overrides`.
- PostgreSQL stores attachment metadata only; attachment bytes live in S3.
- `event_at` represents when the source event occurred; `created_at` represents when an Entry was stored in lifhop.
- Canonical models are implemented with Pydantic and are not persisted directly to PostgreSQL.
- `CanonicalItem.external_id` is optional because some sources such as standalone Markdown files may not provide a stable external identifier.
- Provider-specific schemas must remain outside the core Entry model.
- Strict canonical extra-field validation may be revisited after several real importers are implemented.

## Next — Step 4-2: Importer Interface

Define the provider parser / importer abstraction.

Initial goals:

1. Define what input an importer receives
2. Define what an importer returns
3. Make `CanonicalItem` the output boundary
4. Keep provider-specific parsing isolated
5. Start with a minimal Markdown importer
6. Add importer tests before persistence or API integration

Do not introduce Source persistence, ImportJob, queues, workers, or ChatGPT-specific parsing yet.

## Known issues / deferred decisions

- UUID vs integer IDs
- JSONB metadata structure
- Step 1 filters (`type`, event date range)
- Production health/readiness endpoint design
- Test schema creation via Alembic vs `Base.metadata.create_all`
- Refresh token rotation/revocation and logout
- Password reset and email verification
- Production authentication provider choice
- Attachment deletion behavior in PostgreSQL vs S3
- File size and MIME type validation policy
- Maximum attachment size
- Presigned URL expiration duration
- Cleanup policy for abandoned `PENDING` Attachments and orphaned S3 objects
- Canonical metadata representation
- Canonical attachment representation
- External source persistence model
- `source_id` / `external_id` database constraints
- Strict Pydantic canonical validation policy
- Exact DevSession structure for Codex CLI and Claude Code
- ProjectEvent canonical payload for GitHub

## Last update

2026-08-29
