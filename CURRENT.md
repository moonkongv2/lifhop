# lifhop Current Status

## Current milestone

Step 4 — Import Framework

Status: Complete

Next milestone: Step 5 — ChatGPT Export Import

## Completed work

- FastAPI application bootstrap and `GET /health`
- PostgreSQL 17 via Docker Compose
- SQLAlchemy 2.x, psycopg, Alembic, and Pydantic Settings
- Entry CRUD API with pagination
- pytest integration tests with isolated test PostgreSQL transactions
- User registration, login, JWT access/refresh tokens, and ownership authorization
- Attachment model and S3 integration
- Presigned PUT upload, S3 completion check, and secure presigned GET download
- Manual S3 integration verification

## Step 4 — Import Framework completed

### Source survey and architecture

Reviewed representative source categories:

```text
User-provided Documents
├── Plain Text
├── Markdown
├── PDF
└── Image

External Documents
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

Core import architecture:

```text
Source
  |
  +--> Preserve original file/archive in S3 when applicable
  |
  v
Provider / Format Parser
  |
  v
Canonical Item
  |
  v
Entry Normalizer
  |
  v
Entry
  |
  v
PostgreSQL
```

Provider-specific raw formats are kept outside the core Entry model.

### Canonical model

Implemented provider-neutral canonical models under `app/importers/`:

```text
SourceProvider
CanonicalKind
CanonicalMessage
DocumentPayload
ConversationPayload
DevSessionPayload
CanonicalItem
```

`CanonicalItem.payload` uses a Pydantic discriminated union with `payload.kind` as the discriminator.

Provider and content kind are intentionally separate:

```text
provider = where the data came from
kind     = what kind of information it represents
```

### Importer interface

Implemented an explicit generic ABC importer boundary.

```text
Importer[SourceT]
    |
    v
list[CanonicalItem]
```

This keeps source-specific parsing isolated while preserving implementation-specific input types.

### Initial document importers

Implemented:

```text
PlainTextSource
MarkdownSource
PlainTextImporter
MarkdownImporter
```

Both Plain Text and Markdown normalize into the same canonical `DocumentPayload` representation.

Markdown title resolution priority:

```text
explicit title
→ first H1
→ filename stem
→ Untitled
```

### Entry normalization

Implemented `EntryNormalizer` and `NormalizedEntry`.

Current document flow:

```text
DocumentPayload
      |
      v
EntryNormalizer
      |
      v
EntryType.DOCUMENT
```

The normalizer intentionally starts with simple payload-type dispatch. Step 5 is the explicit checkpoint for deciding whether normalization should evolve into payload-specific Strategy / ABC implementations.

### Markdown import API and Entry persistence

Implemented authenticated Markdown import:

```text
POST /imports/markdown
```

Flow:

```text
UploadFile
   |
   v
MarkdownSource
   |
   v
MarkdownImporter
   |
   v
CanonicalItem
   |
   v
EntryNormalizer
   |
   v
Entry
   |
   v
PostgreSQL
```

Imported Markdown content is persisted as a normal lifhop `DOCUMENT` Entry and can be retrieved through the existing Entry API.

### Raw Import Artifact preservation

Step 4 now distinguishes:

```text
Entry Attachment
- a user-visible file belonging to an Entry

ImportArtifact
- the original source file/archive used to perform an import
```

Implemented minimal `ImportArtifact` persistence:

```text
ImportArtifact
- id
- user_id
- s3_key
- filename
- mime_type
- size
- created_at
```

Original Markdown files are uploaded to S3 using a dedicated raw-import namespace:

```text
users/{user_id}/imports/raw/{uuid}/{filename}
```

The raw source and normalized Entry are stored independently so future parser versions can reprocess the original source.

### Original source download

Implemented secure original-artifact retrieval:

```text
GET /import-artifacts/{artifact_id}/download
```

The API verifies artifact ownership and returns a presigned S3 GET URL. Cross-user access returns 404.

### Database migration

Added Alembic migration:

```text
02057caff6ce_add_import_artifacts.py
```

### Step 4 tests

Tests now cover the important lifhop contracts, including:

- canonical document/conversation payload behavior
- importer interface behavior
- Plain Text and Markdown normalization
- Markdown source decoding
- Entry normalization
- Markdown import persistence
- retrieving an imported Markdown Entry through `/entries/{id}`
- original Markdown S3 upload behavior
- ImportArtifact download URL generation
- cross-user ImportArtifact access protection

The Step 4 test suite is passing.

## Current data ownership/storage model

```text
PostgreSQL
├── User
├── Entry
├── Attachment metadata
└── ImportArtifact metadata

S3
├── Entry attachment bytes
└── Original import files / archives
```

PostgreSQL stores references and metadata; S3 stores file contents.

## Important implementation notes

- PostgreSQL host port is `5433`; Docker maps host `5433` to container port `5432`.
- SQLAlchemy `Session` is injected through FastAPI `Depends(get_db)`.
- Tests replace `get_db` using `app.dependency_overrides` and rollback each test transaction.
- Canonical models are application-layer models and are not persisted directly.
- `event_at` represents when the source event occurred; `created_at` represents when lifhop stored the record.
- `CanonicalItem.external_id` remains optional because simple local documents may not have a stable external identifier.
- Raw Import Artifacts are distinct from Entry Attachments even though both use S3.
- `ImportJob` has intentionally not been introduced yet; it becomes concrete in Step 5 with batch ChatGPT export processing.

## Next — Step 5: ChatGPT Export Import

Use the Step 4 framework with the first complex real-world provider.

Initial goals:

1. Inspect the actual ChatGPT export ZIP structure
2. Preserve the original ZIP as an `ImportArtifact`
3. Parse exported conversations into canonical `ConversationPayload` items
4. Normalize conversations into lifhop Entries
5. Introduce an `ImportJob` model for batch processing state
6. Design idempotency so re-uploading the same export does not duplicate conversations
7. Re-evaluate the `EntryNormalizer` design after the first non-document payload is implemented

Do not introduce SQS or background workers yet. Step 5 should first implement the batch import synchronously so its limitations are visible before Step 6 introduces asynchronous processing.

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
- Maximum attachment/import size
- Presigned URL expiration duration
- Cleanup policy for abandoned Attachments and orphaned S3 objects
- ImportArtifact retention, deletion, storage-cost, and expiration policy
- What happens to Entries when their raw ImportArtifact is deleted
- Canonical metadata representation
- Canonical attachment representation
- External Source persistence model
- `source_id` / `external_id` database constraints
- Duplicate-import detection and idempotency strategy
- Strict Pydantic canonical validation policy
- Exact DevSession structure for Codex CLI and Claude Code
- ProjectEvent canonical payload for GitHub

## Last update

2026-08-31
