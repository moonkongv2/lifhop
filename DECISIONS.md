# lifhop Architecture Decisions

This document records durable design decisions that are expected to affect multiple roadmap steps or future providers.

The intent is not to freeze the architecture permanently. Each decision should be revisited when new source types or operational constraints provide evidence that the current rule no longer fits.

Capture/acquisition details and the risk register are maintained in `CAPTURE.md`.

---

## ADR-001 — Preserve raw import artifacts independently from normalized Entries

**Status:** Accepted  
**Date:** 2026-09-03

### Decision

When an import originates from a file or archive, preserve the original input as an `ImportArtifact` independently from the normalized Entries produced from it.

```text
Uploaded source
    |
    +--> ImportArtifact / S3 raw object
    |
    +--> Parse / normalize
             |
             v
           Entries
```

Multiple uploads of overlapping or equivalent source data may therefore create multiple `ImportArtifact` records while still producing a deduplicated set of normalized Entries.

### Rationale

Raw artifacts and normalized Entries answer different questions:

```text
ImportArtifact
- What exact source did the user provide?
- Can it be downloaded, inspected, retried, or reprocessed later?

Entry
- What normalized lifhop information should be searchable and user-visible?
```

Preserving the source separately allows parser changes, bug investigation, recovery from normalization mistakes, and future reprocessing without requiring another user export.

### Consequence

Artifact duplication and Entry duplication are separate concerns. Exact-file checksums may be added later for diagnostics or upload deduplication, but raw-file equality is not the primary identity mechanism for normalized external records.

### Revisit when

- storage-retention cost becomes material
- users need explicit artifact deletion/retention controls
- artifact versioning or content-addressed storage is introduced
- continuous capture introduces raw payloads that do not fit a file/archive-oriented `ImportArtifact`

---

## ADR-002 — Use stable external identity and upsert for mutable external resources

**Status:** Accepted  
**Date:** 2026-09-03

### Decision

When an external provider supplies a stable identifier for a mutable external resource, persist the Entry identity using:

```text
(user_id, provider, external_id)
```

and use upsert semantics:

```text
no matching identity
→ INSERT

matching identity exists
→ UPDATE with the latest normalized source state
```

The database enforces the identity with a unique constraint on:

```text
(user_id, provider, external_id)
```

For ChatGPT imports:

```text
provider    = chatgpt
external_id = conversation_id
```

### Rationale

A later export can contain both previously imported and newly created records. Insert-only behavior would duplicate existing records, while skip-only behavior would fail to capture updates to an existing resource.

Example:

```text
First export
A, B, C

Later export
A(updated), B, C, D, E

Result
A -> UPDATE
B -> UPDATE
C -> UPDATE
D -> INSERT
E -> INSERT
```

The raw first and second exports remain preserved separately under ADR-001.

### Scope

This is a default policy for **mutable external resources with stable IDs**, not a universal rule for every provider record.

Future immutable events, append-only histories, or providers without trustworthy stable identifiers may require a different persistence strategy.

### Revisit when

- a provider's external IDs are unstable or reused
- immutable event streams are introduced
- Entry history/versioning becomes a requirement
- provider-specific merge semantics become necessary

---

## ADR-003 — Model raw artifacts and processing attempts separately

**Status:** Accepted  
**Date:** 2026-09-03

### Decision

Use separate models for source preservation and processing lifecycle:

```text
ImportArtifact
- raw source identity and S3 metadata

ImportJob
- processing attempt, state, counters, and error information
```

An `ImportArtifact` may be associated with multiple `ImportJob` records so the same source can later be retried or reprocessed with different parser versions or execution strategies.

### Rationale

A source file and an attempt to process that file have different lifecycles. Combining them would make retry/reprocessing history ambiguous and would make Step 6 asynchronous processing harder to model cleanly.

### Revisit note — 2026-09-10

Step 6 introduced SQS and a separate import worker while retaining this separation. The decision remains valid.

Continuous synchronization may later create jobs whose source is not an uploaded file/archive. Do not assume every future capture or sync job must have the exact same `ImportArtifact` lifecycle.

### Revisit when

- parser/version metadata is added to jobs
- import retry APIs are introduced
- source synchronization creates jobs without uploaded artifacts
- continuous capture requires a provider-neutral raw-source model

---

## ADR-004 — Persist ImportJob lifecycle across processing transaction failures

**Status:** Accepted  
**Date:** 2026-09-03

### Decision

For archive imports, persist the raw artifact and initial `ImportJob` before processing Entries.

Conceptually:

```text
Transaction 1
S3 source preserved
→ ImportArtifact
→ ImportJob RUNNING / PENDING
→ COMMIT

Transaction 2
parse / normalize / upsert Entries
→ COMPLETED or PARTIAL
→ COMMIT
```

If an import-wide processing error occurs:

```text
rollback Entry-processing transaction
→ reload persisted ImportJob
→ mark FAILED and record error
→ COMMIT
```

### Rationale

If artifact, job, and Entries were all part of one transaction, a processing failure would erase the very job record needed to explain that the import failed.

Persisting job lifecycle separately makes failed imports observable and prepares the system for async workers and retries.

### Testing consequence

Tests use an outer transaction plus SQLAlchemy savepoints so application code can exercise multiple `commit()` and `rollback()` boundaries while test cleanup still rolls back all test data.

### Revisit note — 2026-09-10

The async Step 6 implementation now creates/persists the artifact and `PENDING` job in the API process, enqueues the `job_id`, and lets the worker transition/process the job separately. This preserves the original intent of this ADR.

### Revisit when

- job state transitions become more complex
- an outbox or event-driven persistence model is introduced
- API commit and queue-send atomicity becomes an operational concern

---

## ADR-005 — Distinguish import-wide failure from item-level partial failure

**Status:** Accepted  
**Date:** 2026-09-03

### Decision

Use `ImportJob` states to distinguish whole-job failure from recoverable item-level failures:

```text
COMPLETED
- all source items processed successfully

PARTIAL
- source/archive was valid
- at least one item succeeded
- one or more items failed independently

FAILED
- import could not proceed as a whole
- example: invalid ZIP or archive-level parsing failure
```

Counters represent:

```text
total_items
processed_items
failed_items
```

Conversation-level processing is isolated so one malformed ChatGPT conversation does not necessarily discard all successfully processed conversations in the same export.

### Rationale

Large imports should not lose hundreds of valid records because one source item is malformed. At the same time, archive-level failures should be clearly distinguishable from partial success.

### Deferred work

Per-item error details are not persisted yet. A future model may record item identity and error diagnostics if debugging or user-facing retry behavior requires it.

### Revisit when

- per-item retry is implemented
- detailed import reports become user-visible
- partial processing needs stricter transactional guarantees

---

## ADR-006 — Treat acquisition/capture as separate from ingestion and normalization

**Status:** Accepted  
**Date:** 2026-09-10

### Decision

How lifhop obtains source data must remain separate from how provider data is parsed, canonicalized, normalized, and persisted.

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

Possible acquisition mechanisms include:

```text
export/archive upload
browser extension
mobile share
OAuth/API sync
webhook
MCP / plugin / CLI hook
local folder watcher
```

These mechanisms should converge on the existing importer/canonical/persistence boundaries instead of creating unrelated Entry-writing implementations.

### Rationale

Provider acquisition methods change for reasons unrelated to the provider's semantic data model.

For example, the same ChatGPT conversation concept might eventually arrive through an export archive, a browser capture, or a future official integration. Replacing the acquisition path should not require redesigning the core Entry model or downstream retrieval system.

### Consequence

The current ChatGPT ZIP importer remains useful but is no longer treated as the architectural model for all future capture.

### Revisit when

- a provider's capture form materially changes the canonical semantics
- streaming/event sources cannot reasonably reuse the existing normalization boundary

---

## ADR-007 — Historical export import is optional enrichment, not the primary recurring product workflow

**Status:** Accepted  
**Date:** 2026-09-10

### Decision

Export/download/upload workflows remain supported for historical data, migration, recovery, and providers without better history access, but should not be required for ongoing use or first value.

Desired product direction:

```text
Sign up
   |
   v
Start capturing current/new records
   |
   v
Use lifhop
   |
   +--> optional connected initial sync
   |
   +--> optional historical export import later
```

### Rationale

Repeated export workflows create too much user effort and become increasingly cumbersome as more providers are supported. Provider export generation can also be slow, making it unsuitable as a required onboarding dependency.

### Consequence

Existing ChatGPT ZIP import work remains valuable as a historical-enrichment path and test data source for the retrieval roadmap.

### Revisit when

- a provider offers no other legally/technically acceptable capture path
- users strongly prefer explicit manual import over continuous capture for privacy reasons

---

## ADR-008 — Minimize capture effort per provider instead of forcing one universal mechanism

**Status:** Accepted  
**Date:** 2026-09-10

### Decision

Use the lowest practical recurring user effort supported by each provider and platform.

Priority direction:

```text
Official connected source available
→ OAuth/API/webhook/incremental sync

Native developer integration available
→ MCP / plugin / hook / SDK capture

Supported browser surface
→ browser one-click or opt-in continuous capture after validation

Closed mobile-app surface
→ Share Extension / Share Target when useful

No lower-effort path
→ optional historical export/import
```

The target is not "everything must be fully automatic." The target is to avoid unnecessary repeated effort while respecting technical, privacy, security, and provider-policy constraints.

### Rationale

Different providers expose fundamentally different acquisition capabilities. A uniform capture implementation would either be too restrictive or rely on fragile/unsupported techniques.

### Consequence

Capture-state modeling may eventually need to represent multiple modes such as historical import, browser capture, mobile share, connected sync, and native capture.

The exact schema and enum names are intentionally deferred until productization provides concrete lifecycle requirements.

---

## ADR-009 — Validate ChatGPT Web browser capture early as a PoC before product commitment

**Status:** Accepted  
**Date:** 2026-09-10

### Decision

Place a small ChatGPT Web Chromium-extension PoC immediately after Step 6 and before the main search roadmap.

The PoC should progress from explicit one-click capture to evaluating opt-in automatic capture, while reusing stable external identity/upsert and the existing downstream ingestion boundary.

It must not expand into full extension productization before Step 7–10 retrieval work.

### Rationale

ChatGPT Web continuous capture could materially reduce user effort, but it has significant uncertainty:

- DOM/UI fragility
- browser/platform coverage
- stable conversation identity
- privacy/over-capture
- provider terms/policy
- ongoing maintenance cost
- no coverage of ChatGPT mobile-app usage

These risks are important enough to validate early, but not important enough to postpone proving that lifhop can create value from captured records.

### Required result

Finish the PoC with an explicit outcome:

```text
GO
LIMITED GO
NO-GO
```

and document the reasons in `CAPTURE.md` / `CURRENT.md` before later productization.

### Non-decision

A technically successful DOM extraction PoC is not a legal/policy approval for commercial deployment.

---

## ADR-010 — Do not equate partial capture with complete user history

**Status:** Accepted  
**Date:** 2026-09-10

### Decision

As ongoing capture is productized, retain enough source/capture state to distinguish what lifhop actually collected from what it could not observe.

Examples of useful future state:

```text
provider
capture method
capture enabled / disabled
capture start
last successful sync/capture
known unsupported surface where relevant
```

### Rationale

A browser extension can capture ChatGPT Web while missing ChatGPT mobile-app conversations. Similar gaps can occur when OAuth scopes, selected folders, labels, workspaces, or provider API limitations exclude data.

Archive-wide analysis becomes misleading if lifhop silently presents a partial sample as complete history.

### Consequence

Capture coverage/provenance is a product-trust requirement, not only an operations/debugging concern.

The exact persistent coverage model should be introduced when Step 11 productization makes the required fields concrete.

---

## ADR-011 — Prefer independent implementation and targeted IP review before commercial launch

**Status:** Accepted  
**Date:** 2026-09-10

### Decision

lifhop may implement broadly similar capture/archive ideas to existing products, but should be designed and coded independently.

Do not copy competitor source code, distinctive UI, wording, branding, or proprietary implementation details.

Retain repository history and architecture decisions that show the project's independent design process.

Before commercial launch, consider a targeted freedom-to-operate / patent review for the final core mechanisms that materially define the product, especially browser capture and personal-history retrieval/analysis.

### Rationale

Similar products already exist and future or unpublished patent claims cannot be ruled out merely because a broad concept is common. Early independent design plus focused review at the point where the commercial implementation is concrete is more useful than trying to freeze development around speculative IP risk now.

---

## ADR-012 — Treat SQS import delivery as at-least-once and require idempotent consumers

**Status:** Accepted  
**Date:** 2026-09-12

### Decision

SQS-backed import processing must assume that the same message and the same `ImportJob` may be processed more than once.

The worker therefore follows this rule:

```text
receive message
    |
    v
process job
    |
    v
durable DB commit
    |
    v
delete SQS message
```

If processing raises or the worker exits before `DeleteMessage`, the message must remain undeleted so SQS visibility-timeout/redelivery behavior can retry it.

Consumers must not depend on exactly-once delivery for correctness. Reprocessing the same logical resource must converge on the same persisted result.

For current ChatGPT imports, idempotency is provided primarily by the stable external identity rule from ADR-002:

```text
(user_id, provider, external_id)
```

Repeated processing updates the existing conversation Entry instead of creating another one.

### Verification

The Step 6 failure exercise was verified against the real development SQS queue:

```text
receive job
→ process and commit successfully
→ intentionally skip SQS deletion
→ visibility timeout expires
→ same message becomes visible again
→ same job_id is processed again
→ Entry count remains unchanged
→ normal worker deletes the redelivered message
```

This demonstrates the intended at-least-once processing model rather than relying only on mocked queue tests.

### Rationale

Queue delivery and application persistence cannot be treated as one atomic operation. A worker can successfully commit database changes and then crash before deleting the queue message.

If the processor were not idempotent, that ordinary failure window could create duplicate or corrupted data on redelivery.

### Consequences

- Future SQS consumers must define an idempotency strategy before being considered production-safe.
- Message deletion is an acknowledgement of durable successful processing, not merely successful receipt.
- Queue retries may re-enter an existing `ImportJob`; processor state must tolerate another run.
- `PARTIAL` is currently a successful processing result from the queue perspective and is therefore deleted after the processor returns successfully.
- Poison-message isolation and maximum retry handling remain a later DLQ/redrive concern.
- API database commit followed by SQS-send failure remains a separate atomicity gap and may later justify an outbox-style pattern.

### Revisit when

- a future workload cannot be made naturally idempotent
- a different queue technology changes delivery guarantees
- per-item retries or compensating actions are introduced
- an outbox/inbox or deduplication-key mechanism is needed beyond current Entry upsert semantics
