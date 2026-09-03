# lifhop Architecture Decisions

This document records durable design decisions that are expected to affect multiple roadmap steps or future providers.

The intent is not to freeze the architecture permanently. Each decision should be revisited when new source types or operational constraints provide evidence that the current rule no longer fits.

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

### Revisit when

- parser/version metadata is added to jobs
- import retry APIs are introduced
- source synchronization creates jobs without uploaded artifacts

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
→ ImportJob RUNNING
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

### Revisit when

- Step 6 moves processing to a worker
- job state transitions become more complex
- an outbox or event-driven persistence model is introduced

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
