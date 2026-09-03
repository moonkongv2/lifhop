# lifhop Current Status

## Current milestone

Step 5 — ChatGPT Export Import

Status: Complete

Next milestone: Step 6 — Async Processing with SQS

## Completed work

- FastAPI application bootstrap and `GET /health`
- PostgreSQL 17 via Docker Compose
- SQLAlchemy 2.x, psycopg, Alembic, and Pydantic Settings
- Entry CRUD API with pagination
- pytest integration tests with isolated PostgreSQL transactions
- User registration, login, JWT access/refresh tokens, and ownership authorization
- Attachment model and S3 integration
- Presigned PUT upload, S3 completion check, and secure presigned GET download
- Import framework with provider-neutral Canonical Items and Entry normalization
- Plain Text and Markdown import
- Raw ImportArtifact preservation and secure original-file download
- ChatGPT export ZIP import with conversation-aware parsing, idempotent upsert, and ImportJob status tracking

## Step 5 — ChatGPT Export Import completed

### ChatGPT export parsing

Implemented ChatGPT export ingestion from ZIP archives containing `conversations.json`.

The source factory handles the archive/container format while `ChatGPTImporter` handles provider-specific conversation structure:

```text
ChatGPT ZIP
    |
    v
Source Factory
    |
    v
ChatGPTSource
    |
    v
ChatGPTImporter
    |
    v
ConversationPayload
    |
    v
EntryNormalizer
    |
    v
CONVERSATION Entry
```

ChatGPT exports are treated as node-based conversation trees. The currently selected branch is reconstructed by following `current_node` through parent links and reversing the result. The initial implementation normalizes user and assistant text messages on that active branch.

The original export ZIP is preserved independently, so future parser versions can reprocess the raw source if branch or message-selection policy changes.

### Conversation normalization

`EntryNormalizer` now supports both document and conversation payloads.

Current conversation representation:

```text
ConversationPayload
      |
      v
EntryNormalizer
      |
      v
EntryType.CONVERSATION
```

Conversation messages are flattened into searchable Entry content while the provider-specific raw structure remains outside the Entry model.

After the Step 5 checkpoint, the central `EntryNormalizer` remains sufficiently small and clear. A Strategy / ABC split is deferred until additional canonical payload kinds or materially more complex normalization rules justify it.

### ImportArtifact and ImportJob

Batch/archive imports now distinguish the original source from processing history:

```text
ImportArtifact
- what raw file/archive was uploaded

ImportJob
- what happened while processing that artifact
```

One `ImportArtifact` can have multiple `ImportJob` records so the same preserved source can later be retried or reprocessed with newer parser logic.

Current `ImportJob` states:

```text
PENDING
RUNNING
COMPLETED
FAILED
PARTIAL
```

The ChatGPT endpoint creates an artifact and processing job, records item counts, and tracks completion or failure state.

### External identity and upsert

Entries imported from external systems can now persist:

```text
provider
external_id
```

The database protects stable external identity with:

```text
(user_id, provider, external_id)
```

as a unique constraint.

For sources that provide a stable external identifier, the default import policy is upsert rather than insert-only:

```text
matching external identity not found
→ INSERT

matching external identity found
→ UPDATE with the latest normalized source data
```

For ChatGPT:

```text
provider    = chatgpt
external_id = conversation_id
```

This allows a later ChatGPT export to contain both old and new conversations without duplicating existing Entries. Existing conversations are refreshed from the newer export, while newly discovered conversation IDs create new Entries.

Raw artifacts are handled separately from normalized Entry identity. Each uploaded export remains preserved as its own `ImportArtifact` even when its conversations overlap with earlier exports.

### Failure and partial-result handling

ChatGPT import processing now separates source/job persistence from Entry processing transaction boundaries.

High-level flow:

```text
S3 upload
→ ImportArtifact + RUNNING ImportJob commit
→ parse/process conversations
```

If the archive itself cannot be parsed or another import-wide failure occurs:

```text
Entry transaction rollback
→ ImportJob = FAILED
→ error recorded
```

The preserved raw artifact and failed job remain available for inspection.

Conversation processing can also isolate item-level failures. If only some conversations fail:

```text
total_items     = all conversations in source
processed_items = successful conversations
failed_items    = failed conversations
status          = PARTIAL
```

Successful conversations are retained rather than rolling back the whole archive.

### Test transaction support

The pytest database fixture now uses SQLAlchemy savepoint-aware transaction joining so application code can exercise multiple `commit()` / `rollback()` boundaries while each test still rolls back its outer transaction afterward.

This supports realistic testing of ImportJob lifecycle and prepares the test infrastructure for later queue/retry work.

### Step 5 tests

Tests now cover the important ChatGPT import contracts, including:

- ChatGPT ZIP source creation
- invalid ZIP rejection
- active conversation branch parsing
- conversation normalization
- authenticated `/imports/chatgpt` integration
- original ZIP `ImportArtifact` persistence
- completed `ImportJob` persistence and counters
- idempotent repeated imports
- updating an existing conversation when the same `conversation_id` appears with newer data
- preserving multiple raw artifacts while normalized Entries remain deduplicated
- whole-import `FAILED` behavior
- conversation-level `PARTIAL` behavior
- regression coverage for the existing application

The full test suite is passing at the end of Step 5.

## Current data ownership/storage model

```text
PostgreSQL
├── User
├── Entry
│   ├── provider
│   └── external_id
├── Attachment metadata
├── ImportArtifact metadata
└── ImportJob state/history

S3
├── Entry attachment bytes
└── Original import files / archives
```

PostgreSQL stores normalized data, references, metadata, external identity, and processing state. S3 stores original file contents.

## Important implementation notes

- PostgreSQL host port is `5433`; Docker maps host `5433` to container port `5432`.
- SQLAlchemy `Session` is injected through FastAPI `Depends(get_db)`.
- Tests replace `get_db` using `app.dependency_overrides` and isolate tests with an outer transaction plus savepoints.
- Canonical models are application-layer models and are not persisted directly.
- `event_at` represents when the source event occurred; `created_at` represents when lifhop stored the record.
- `CanonicalItem.external_id` remains optional because simple local documents may not have a stable external identifier.
- Raw Import Artifacts remain distinct from Entry Attachments even though both use S3.
- Raw artifact preservation and normalized Entry deduplication are intentionally separate concerns.
- Stable external resources should generally use `(user_id, provider, external_id)` identity and upsert semantics.
- The rule is not universal for every future source: immutable events or sources without stable IDs may need a different persistence policy.
- ImportJob failure state is persisted independently from the Entry-processing transaction so failed imports remain observable.

## Next — Step 6: Async Processing with SQS

Move expensive imports away from the synchronous API request path.

Initial goals:

1. Reuse the existing `ImportJob` lifecycle rather than creating a second job concept
2. Introduce SQS as the queue between API and worker
3. Let the API preserve/create the raw artifact and job, then enqueue work
4. Let a worker load the preserved artifact and perform provider import processing
5. Preserve idempotent upsert behavior when messages are redelivered
6. Add retry and failure exercises
7. Introduce a Dead Letter Queue after the basic worker flow is understood

The existing synchronous ChatGPT implementation is the behavioral baseline for Step 6.

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
- Artifact checksum / exact-file duplicate detection policy
- Per-item import error persistence and diagnostics
- Canonical metadata representation
- Canonical attachment representation
- External Source persistence model and `source_id`
- Strict Pydantic canonical validation policy
- Exact DevSession structure for Codex CLI and Claude Code
- ProjectEvent canonical payload for GitHub
- Source-specific exceptions to the default external-resource upsert policy

## Last update

2026-09-03
