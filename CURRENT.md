# lifhop Current Status

## Current milestone

Step 6 — Async Processing with SQS

Status: Core async implementation complete; operational hardening remains where not yet verified.

Next milestone: **Step 6.5 — ChatGPT Web Capture PoC**

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
- SQS producer/consumer path for ChatGPT imports
- Separate import worker process
- Worker success deletes the SQS message
- Worker processing failure leaves the SQS message undeleted for queue redelivery behavior
- Tests for queue-oriented import submission and worker behavior
- Full test suite reported passing after the Step 6 implementation work

---

# Step 6 — Current implementation

The ChatGPT import request no longer performs the expensive conversation processing in the API request path.

Current flow:

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
```

On successful worker processing, the SQS message is deleted.

If worker processing raises an exception, the current worker does not delete the message. This allows SQS visibility timeout/redelivery behavior to retry the message.

## Step 6 implementation files

Important current files include:

```text
app/api/imports.py
- creates raw artifact + PENDING job
- enqueues job_id
- returns HTTP 202

app/sqs.py
- SQS client
- send message
- receive message
- delete message

app/workers/import_worker.py
- long-running queue consumer
- processes one ImportJob at a time
- deletes only successful messages

app/services/import_jobs.py
- RUNNING / COMPLETED / PARTIAL / FAILED lifecycle
- artifact download
- importer / normalizer / Entry upsert
```

## Step 6 operational items still worth exercising/documenting

Where not already completed and recorded, continue to verify:

- worker crash during processing and SQS redelivery
- duplicate delivery does not duplicate Entries
- visibility timeout behavior
- retry behavior
- DLQ creation/redrive behavior
- poison-message behavior
- logging beyond current simple `print()` output
- API-commit vs queue-send failure window

These do not block the short Step 6.5 capture PoC, but they remain part of the queue/production learning path.

---

# Capture strategy update — 2026-09-10

A product-level risk review identified that recurring user export/download/upload is too cumbersome to be lifhop's long-term acquisition experience, especially as the number of supported providers grows.

The agreed product direction is:

> Use zero-effort capture where a stable and acceptable integration exists, and the lowest practical user effort where it does not.

Historical exports remain useful, but their role changes to **optional historical enrichment / migration**, not required ongoing capture or required onboarding.

Capture/acquisition should remain separate from downstream ingestion:

```text
Capture / Acquisition
        |
        v
Provider raw data
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

Detailed strategy and risks are now documented in `CAPTURE.md`.

---

# Next — Step 6.5: ChatGPT Web Capture PoC

## Goal

Validate whether a Chromium extension can provide low-effort ChatGPT Web capture early, before lifhop spends significant time productizing capture across many providers.

This is a small PoC, not the production extension.

## Initial progression

### PoC v0 — one-click capture

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
reuse Conversation normalization/upsert
```

Verify:

- active conversation can be identified
- required user/assistant message text can be extracted
- stable conversation identity can be obtained reliably enough
- first capture inserts the Entry
- repeat capture of the same conversation updates it

### PoC v0.x — update detection

Verify that the extension can detect that new messages were added to the active conversation without continuously resending identical content.

### PoC auto-capture experiment

If v0 works, test opt-in automatic capture with a reasonable debounce/completion boundary.

Do not assume this will become a production feature merely because it is technically possible.

## PoC risk checklist

The result must explicitly document:

- DOM/UI fragility
- conversation identity reliability
- Chromium/browser dependency
- Safari/Firefox non-coverage
- ChatGPT mobile-app non-coverage
- privacy and over-capture implications
- minimum browser permissions
- provider terms/policy questions around automated/programmatic extraction
- ongoing maintenance burden

Finish with one of:

```text
GO
LIMITED GO
NO-GO
```

Then return to the main retrieval roadmap.

---

# Planned acquisition direction after retrieval validation

Do not implement all of this now. The agreed later direction is:

```text
Browser
→ Chromium extension
→ one-click / opt-in continuous capture

Mobile
→ iOS Share Extension / Android Share Target
→ explicit Share -> lifhop
→ lifhop only receives what the source app actually shares

Official provider integration
→ OAuth / API / webhook
→ initial + incremental sync
→ Notion / GitHub / Google Drive candidates

Developer tools
→ MCP / plugin / CLI hook where supported
→ Codex / Claude Code / similar tools

Later candidates
→ Safari / Firefox
→ local folder / Obsidian sync
→ email forwarding / selective mail capture
```

ChatGPT mobile remains a known limitation: a lifhop app cannot automatically read the private contents of the ChatGPT mobile app. If ChatGPT sharing exposes only a shared URL rather than transcript text, reliable conversation extraction from that URL is a separate feasibility/policy question and must not be assumed.

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

2026-09-10
