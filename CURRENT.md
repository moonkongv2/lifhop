# lifhop Current Status

## Current milestone

Step 6.5 — Opt-in automatic-capture feasibility (manual capture and fingerprint-based change detection verified).

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
- Shared external Entry upsert service reused by ChatGPT ZIP import and browser capture
- Chromium extension: scroll-and-collect of the active conversation with message-ID deduplication
- Assistant Markdown and code-block extraction (language metadata and citation cleanup still incomplete)
- Authenticated `POST /captures/chatgpt` with capture diagnostics and canonical ConversationPayload normalization
- Browser capture E2E verified: first capture inserts an Entry; later capture of the same conversation updates the same Entry
- Capture API tests and full local pytest suite reported passing
- SHA-256 manual-capture fingerprint comparison; unchanged conversations skip repeat POST requests
- Successful fingerprints cached in `chrome.storage.local` by API URL, user ID, and conversation ID

---

# Step 6.5 — Verified manual capture and change detection (2026-09-25)

The user verified the following in the local development environment:

```text
ChatGPT Web
    |
    v
Chromium extension: capture the active conversation
    |
    v
POST /captures/chatgpt + JWT
    |
    v
CanonicalItem / ConversationPayload
    |
    v
upsert_external_entry() (shared with ZIP worker)
    |
    v
PostgreSQL Entry INSERT or UPDATE
```

- Scrolling from either end of a tested conversation recovered the expected user/assistant message sequence.
- Markdown/code-block extraction preserved readable structure; some citation UI noise, excess whitespace, and code-language metadata remain.
- Saving an updated conversation returned the same Entry ID; `GET /entries/{entry_id}` showed the collected turns.
- Repeating a manual capture without changing title or messages skips the API request using a SHA-256 fingerprint in extension-local storage.
- When the capture changes, the extension POSTs again and updates its local fingerprint only after API success.
- `CaptureDiagnostics` rejects obvious incomplete scans, mismatched message counts, and captures not starting with a user message. These checks do not prove that every intermediate turn was collected.
- The local extension cache is a request-avoidance optimization, not authoritative synchronization or server-side identity.

## Next experiment — Step 6.5-G

Test opt-in DOM change detection with `MutationObserver` in a ChatGPT content script and notifications to an extension service worker, including after the popup closes. Begin with notifications only (no automatic network submission or database write). Evaluate false positives from scrolling, virtualized messages, and response streaming; then decide whether an opt-in automatic-save path can be made sufficiently reliable.

As of this update, the pushed `main` branch does **not** contain `extension/observer.js` or `extension/service-worker.js`. Auto-capture is not yet implemented or verified.

## Known capture limitations

- `reached_top` and `reached_bottom` do not guarantee complete capture of a virtualized conversation.
- The current full-replacement upsert can overwrite a more complete existing Entry if a later capture is incomplete or older; server-side safeguards / merge policy are deferred.
- `message_id`, `source_url`, and diagnostics are accepted by the capture request but not persisted as structured Entry fields.
- Local fingerprints can become stale if another client, ZIP import, or server-side process modifies the same Entry.
- Browser capture does not cover ChatGPT mobile; provider-policy acceptability and DOM resilience require separate evaluation.
- Local API and manually pasted access token remain development-only UX; do not store tokens or credentials in the repository.

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

# Next — Step 6.5-G: Opt-in DOM change-detection experiment

Manual ChatGPT Web capture, authenticated persistence, stable-identity upsert, and fingerprint-based manual change detection are verified.

Next, validate whether a content script can observe new or changed conversation content after the popup closes. Start with an explicitly enabled `MutationObserver` and service-worker notifications; do not automatically POST captured data until response-completion detection, complete-conversation collection, and overwrite protection are understood.

Then finish the browser-capture PoC with a documented GO / LIMITED GO / NO-GO outcome informed by DOM fragility, maintenance effort, browser-only coverage, privacy, and provider-policy review.

After the PoC, return to the planned frontend learning interlude / Step 7 keyword search rather than expanding into multi-provider capture productization.

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
- Client-side fingerprints only skip redundant manual requests; server-side identity remains `(user_id, provider, external_id)`.
- The caller (ZIP worker or Capture API) owns the DB transaction; `upsert_external_entry()` does not commit.
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

- Server-side incomplete/stale capture overwrite prevention and future merge semantics
- Reliable streaming-answer completion detection and false-positive handling for `MutationObserver`
- Client fingerprint/cache reconciliation after updates from ZIP import or another device
- Structured persistence for source URL, per-message IDs, and capture provenance
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

2026-09-25
