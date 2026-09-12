# lifhop Current Status

## Current milestone

Step 6.5 — ChatGPT Web Capture PoC

Step 6 — Async Processing with SQS is complete as of 2026-09-12.

After the capture PoC, return to the planned frontend learning interlude / Step 7 keyword search rather than expanding immediately into multi-provider capture productization.

## Completed work

- FastAPI application bootstrap and `GET /health`
- PostgreSQL via Docker Compose
- SQLAlchemy 2.x, psycopg, Alembic, and Pydantic Settings
- Entry CRUD API with pagination
- pytest integration tests with isolated PostgreSQL transactions/savepoints
- User registration, login, JWT access/refresh tokens, and ownership authorization
- Attachment model and S3 integration
- Presigned PUT upload, S3 completion check, and secure presigned GET download
- Import framework with provider-neutral Canonical Items and Entry normalization
- Plain Text and Markdown import
- Raw `ImportArtifact` preservation and secure original-file download
- ChatGPT export ZIP import with conversation-aware parsing
- ChatGPT external identity using `(user_id, provider, external_id)`
- Idempotent ChatGPT upsert for repeated/newer exports
- `ImportJob` lifecycle with `PENDING`, `RUNNING`, `COMPLETED`, `PARTIAL`, and `FAILED`
- Asynchronous ChatGPT import submission: raw artifact + `PENDING` job + SQS enqueue + HTTP 202
- Separate long-running SQS import worker
- `GET /import-jobs/{job_id}` status API with ownership protection
- Worker success deletes the SQS message only after durable processing completes
- Worker processing failure leaves the message undeleted for SQS redelivery
- Unit/integration coverage for async submission, worker behavior, processor lifecycle, idempotent upsert, and ImportJob status retrieval
- Full pytest suite passing after the Step 6 status API work

---

# Step 6 — Verified async import behavior

Current request flow:

```text
POST /imports/chatgpt
        |
        v
Upload raw ZIP to S3
        |
        v
Create ImportArtifact
        |
        v
Create PENDING ImportJob
        |
        v
COMMIT
        |
        v
SQS: { job_id }
        |
        v
HTTP 202
```

Worker flow:

```text
SQS
 |
 v
receive message
 |
 v
open DB Session
 |
 v
process_chatgpt_import_job(job_id)
 |
 +--> RUNNING
 |
 +--> download preserved artifact from S3
 |
 +--> ChatGPT importer
 |
 +--> canonical ConversationPayload
 |
 +--> EntryNormalizer
 |
 +--> idempotent Entry upsert
 |
 v
COMPLETED / PARTIAL / FAILED
 |
 v
successful processing -> delete SQS message
```

Import status can be read through:

```text
GET /import-jobs/{job_id}
```

The API exposes job state, counters, timestamps, artifact identity, and top-level error information without exposing another user's job.

## SQS redelivery / idempotency verification

The Step 6 failure exercise was completed against the real development SQS queue.

Verified sequence:

```text
receive SQS message
        |
        v
process ImportJob successfully
        |
        v
commit ImportJob / Entries
        |
        v
intentionally do NOT delete SQS message
        |
        v
visibility timeout expires
        |
        v
same message becomes visible again
        |
        v
same job_id is processed again
        |
        v
existing ChatGPT Entries are updated by stable identity
        |
        v
no duplicate Entries are created
        |
        v
normal worker deletes the redelivered message
```

This confirms the intended at-least-once processing model: queue delivery may repeat, so correctness depends on idempotent application behavior rather than assuming exactly-once delivery.

---

# Step 6 operational hardening deferred for later

The learning objective for Step 6 is complete. The following remain production/operations follow-up rather than blockers for Step 6.5:

- explicit DLQ creation and redrive verification
- poison-message exercise
- visibility-timeout tuning for realistic import duration
- structured logging/observability beyond current simple `print()` output
- API DB commit followed by SQS-send failure handling / possible outbox pattern
- production worker deployment and process supervision

These should be revisited during production AWS / operations steps unless an earlier real requirement makes them necessary.

---

# Next — Step 6.5: ChatGPT Web Capture PoC

## Goal

Validate whether a Chromium extension can provide low-effort ChatGPT Web capture before lifhop spends significant time productizing capture across many providers.

This is a small PoC, not the production extension.

Initial progression:

```text
ChatGPT Web
    |
    v
[Save to lifhop]
    |
    v
read active conversation
    |
    v
send to lifhop
    |
    v
reuse Conversation normalization / stable identity / upsert
```

Verify:

- active conversation can be identified
- required user/assistant message text can be extracted
- stable conversation identity can be obtained reliably enough
- first capture inserts the Entry
- repeat capture of the same conversation updates it
- new-message detection is feasible enough to evaluate optional auto-capture

The PoC must explicitly evaluate DOM fragility, browser coverage, privacy/over-capture, minimum permissions, provider-policy questions, and ongoing maintenance burden.

Finish with one of:

```text
GO
LIMITED GO
NO-GO
```

Detailed capture strategy and risks remain in `CAPTURE.md`.

---

# Current data ownership/storage model

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

SQS
└── asynchronous ImportJob messages
```

PostgreSQL stores normalized data, references, external identity, and processing state. S3 stores original file contents. SQS carries asynchronous processing work.

---

# Important current architecture decisions

- Canonical models remain application-layer models and are not persisted directly.
- `event_at` represents when the source event occurred; `created_at` represents when lifhop stored the record.
- Raw Import Artifacts remain distinct from Entry Attachments even though both use S3.
- Raw artifact preservation and normalized Entry deduplication are separate concerns.
- Mutable external resources with stable IDs generally use `(user_id, provider, external_id)` and upsert semantics.
- SQS import delivery is treated as at-least-once; consumers must remain idempotent and messages are deleted only after durable successful processing.
- Provider acquisition/capture is separate from provider parsing/canonical normalization.
- Historical export import is an optional enrichment path, not the intended primary recurring capture workflow.
- Capture mechanism should vary by provider/platform instead of forcing a universal method.
- ChatGPT Web extension capture must be validated as a PoC before product commitment.
- Partial capture must not later be presented as complete user history.
- Exact future `SourceConnection` / continuous raw-capture schema is intentionally deferred until real workflows demonstrate the lifecycle needed.

See `DECISIONS.md` and `CAPTURE.md`.

---

# Known issues / deferred decisions

## Existing backend decisions

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
- Strict Pydantic canonical validation policy
- Exact DevSession structure for Codex CLI and Claude Code
- ProjectEvent canonical payload for GitHub
- Source-specific exceptions to the default external-resource upsert policy

## Queue/worker decisions

- DLQ/redrive production configuration
- visibility timeout tuning
- poison-message handling
- worker logging/observability
- API DB commit followed by SQS-send failure handling / possible outbox pattern
- worker deployment/process supervision

## Capture decisions

- ChatGPT Web PoC outcome: GO / LIMITED GO / NO-GO
- exact provider-policy/legal acceptability of production browser auto-capture
- stable ChatGPT Web conversation identity strategy
- how much raw browser-capture source data to preserve
- whether continuous raw data should evolve `ImportArtifact` or introduce a separate capture/source record model
- exact `SourceConnection` schema
- capture-mode enum names
- browser capture permissions and privacy controls
- mobile Share payload support by provider
- handling ChatGPT mobile shared links if only URLs are exposed
- Safari / Firefox priority
- initial official connected provider: Notion vs GitHub vs Google Drive
- native capture mechanism for Codex / Claude Code
- local-folder / email capture priority
- source coverage/provenance persistence model

---

# Last update

2026-09-12
