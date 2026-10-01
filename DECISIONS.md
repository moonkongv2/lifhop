# lifhop Architecture Decisions

This document records durable design decisions that are expected to affect multiple roadmap steps or future providers.

The intent is not to freeze the architecture permanently. Each decision should be revisited when new source types or operational constraints provide evidence that the current rule no longer fits.

Capture/acquisition details and the risk register are maintained in `CAPTURE.md`.
References to numbered Steps in older decisions describe the learning plan
at the time of those decisions. `ROADMAP.md` is the active delivery order
after the `learning-complete-f3` baseline.

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

### Implementation note — 2026-09-25

ChatGPT ZIP import and the authenticated browser Capture API both use `upsert_external_entry()`. This service normalizes the canonical item and performs the stable-identity INSERT/UPDATE without calling `db.commit()`; each caller owns its transaction.

The browser extension's SHA-256 fingerprint is only a client-side optimization to skip unchanged manual POST requests. It is not a replacement for the database uniqueness constraint, not proof of complete capture, and not authoritative synchronization state. The fingerprint may become stale after a ZIP import or update from another client. The current upsert replaces Entry content; protecting a fuller Entry against an incomplete or older snapshot remains deferred.

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

### Implementation note — 2026-09-25

The first browser capture path now uses the same canonical `ConversationPayload`, `EntryNormalizer`, and shared upsert service as ChatGPT ZIP import. The synchronous Capture API accepts an authenticated JSON conversation without requiring an S3 artifact, SQS job, or duplicate persistence implementation. Archive imports retain their S3/SQS pipeline. The capture request may include message IDs, source URL, and collection diagnostics, but these are not yet stored as structured Entry fields.

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

### Progress note — 2026-09-25

The Chromium extension demonstrated manual full-conversation collection in tested conversations, authenticated end-to-end storage, stable-identity updates, and fingerprint-based detection of changes between explicit saves. At that point automatic/background DOM observation and auto-save remained unverified, and the PoC outcome was still pending (see closeout note).

### Closeout decision — LIMITED GO (2026-09-26)

The Step 6.5 learning/risk-discovery objective is closed. Early local tests confirmed one-click ChatGPT Web extraction, the authenticated Capture API, common canonical normalization and idempotent Entry upsert, and client-side SHA-256 detection of changed explicit captures. Subsequently, the DOM collector failed in an actual capture attempt with `메시지 DOM을 찾지 못했습니다` before submitting to the API. No cause attributable to deliberate provider behavior has been established.

**Scope of LIMITED GO:** retain the manual extension as research-only code and the reusable server-side capture/ingestion path. The manual extension is not considered presently reliable on the affected page. Do not commit to production browser capture, automatic/background capture, or generalized DOM fallback infrastructure on the basis of the initial successful demo. Automatic capture was not implemented or evaluated, rather than conclusively judged infeasible.

**Sequencing:** end Step 6.5 here, move to the Frontend Learning Interlude (F0–F3) and Step 7 keyword search, and defer capture productization to Step 11 after Steps 7–10 can establish retrieval value. The ChatGPT ZIP importer and manual Entries provide a non-DOM-dependent development dataset.

**Security/data integrity:** keep collector/extension and API fail-closed checks for visibly incomplete captures. A missing message DOM must stop before POST. These guards do not prove complete collection; existing full-replacement upsert could still overwrite fuller data with an incomplete/stale capture that passes basic diagnostics. Server-side completeness, source freshness/merge rules, and explicit opt-in would be prerequisites for later auto-save. Provider-policy/legal acceptance remains a separate launch gate.

**Revisit when:** retrieval-driven user demand justifies capture maintenance, a stable official acquisition method becomes available, or Step 11 provides evidence for a tested provider-specific DOM adapter, regression suite, privacy controls, and overwrite protection.

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

### Step 6.5 safety finding — 2026-09-26

The current Capture API rejects several obvious incomplete requests, and the manual extractor stops before POST when it cannot locate message nodes. These are failure-containment measures, not proof of full coverage. Because the current upsert replaces Entry content, a partial snapshot that passes the diagnostic flags can still overwrite a more complete previous snapshot. Automatic capture and claims of complete history remain out of scope until provenance and server-side completeness/staleness safeguards are designed and tested.

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

---

## ADR-013 — Keep ordinary development and tests off AWS S3

**Status:** Accepted
**Date:** 2026-09-29

### Decision

Use a local S3-compatible SeaweedFS service as the default object store for
development. Keep the existing boto3 storage interface and explicitly select
real AWS S3 with `S3_MODE=aws` only when that integration needs validation.
Local mode uses separate local credentials and bucket and rejects non-loopback
endpoints. Tests block unexpected boto3 client creation and mock storage and
queue operations at their boundaries.

### Rationale

The previous local environment could target a real AWS bucket. Two Markdown
API tests also invoked the real upload function. Repeated imports use new
object keys, so accidental development uploads could accumulate stored
objects and incur charges. The local service preserves the S3 API and
presigned-URL behavior needed for development without contacting AWS S3.

### Consequences

- Real AWS S3 integration is an explicit test/deployment choice.
- The local SeaweedFS service is development infrastructure, not a production
  storage dependency.
- This does not change SQS. A local queue path is needed before ChatGPT ZIP
  imports can be demonstrated with no AWS requests.
- Remote bucket lifecycle and current billing are separate operational
  checks; local mode does not alter existing remote objects.

### Revisit when

- deployment configuration or container networking changes local endpoints
- SeaweedFS no longer provides a suitable local development image
- storage behavior requires verification against real AWS S3

---

## ADR-014 — Finish a private multi-source release before commercial work

**Status:** Accepted direction; implementation pending

**Date:** 2026-09-30

### Decision

Prioritize recovery of past solutions and decision reasons, then period
retrospectives, then project resumption. Support ordinary life records without
requiring a project. Add Codex CLI on the owner's single Mac and selected
personal/organization GitHub repositories to the personal-release requirements,
alongside existing ChatGPT/Markdown/manual inputs.

Both new sources require accessible historical backfill, scheduled collection,
and collect-now controls. GitHub prioritizes direct commits, relevant diffs,
and key documents; PRs/reviews/issues/comments remain required. Exclude
whole-codebase indexing and other provider integrations from this release.
Verify both sources before building cross-source answers; implement scheduling
after the shared ingestion/history behavior is tested.

### Rationale and consequences

The owner's useful context spans several services. A ChatGPT-only archive
cannot establish the intended retrieval value. Full-period collection means
all accessible records within an explicit source/branch/content scope; missing
historical data must be reported, not invented. Codex source format/access and
GitHub repository inventory still need verification.

`ROADMAP.md` now defines the sequence. This refines ADR-007/008: low recurring
effort is required for Codex and GitHub, while manual ChatGPT ZIP imports remain
the planning default. ADR-009's experimental DOM status is unchanged.
Commercial onboarding, billing, and broad provider expansion follow private
release acceptance rather than blocking it.

---

## ADR-015 — Preserve collected history and distinguish two kinds of deletion

**Status:** Accepted direction; implementation pending

**Date:** 2026-09-30

### Decision

Retain changed collected versions under a stable logical Entry identity and
identify the current version explicitly. Unchanged replay creates no new
version. An older or incomplete snapshot must not replace a newer, more
complete current record merely because it arrived later. Preserve source
identity, time, provenance, and completeness information; unknown freshness
requires reconciliation rather than blind replacement.

Confirmed source deletion retains collected content with a deletion marker.
Authorization loss, collection failure, and absence from a partial listing do
not establish source deletion. An explicit lifhop deletion immediately hides
all associated content/versions from retrieval and answers and schedules content
purge; minimal owner/source identity tombstones prevent automatic resurrection.
The suppression check applies to backfill, retries, in-flight jobs, and restore.
Only an explicit owner action may allow reimport.

Define raw-artifact/shared-ZIP handling and backup expiry with the deletion
implementation. Preserve unaffected records without continuing to expose or
indefinitely retain explicitly deleted content in a downloadable archive.

### Rationale and consequences

Historical questions need inspectable past evidence. Current full-replacement
upsert cannot provide this, and source deletion has a different intent from an
owner asking lifhop to forget a record. This refines ADR-001/002: raw preservation
is subject to explicit deletion, and upsert selects a current version without
discarding collected history. It does not reconstruct edits never collected.

Introduce migrations and behavioral tests in Phase 2.2. Existing Entries can
become initial observed versions. Keep imported source content read-only and
personal annotations separate from source updates; manual Entries stay editable.
Retention/cost conflicts must be surfaced rather than silently pruning history.

---

## ADR-016 — Separate collection permission from external-AI permission

**Status:** Accepted direction; implementation pending

**Date:** 2026-09-30

### Decision

Support repository/source and individual-record exclusions from external AI.
Permission to retain a record in lifhop's AWS deployment is separate from
permission to transmit it to a model provider. Collection exclusions operate
before upload; secrets and excluded local payloads must not enter the archive.

Start new sources with external AI disabled until the owner enables it. A
repository/record denial wins over broader permission, survives reimport, and
applies to remote embeddings, reranking, summaries, answer context, and logging/
telemetry that would transmit content. Derived records inherit all contributing
sources' restrictions. Recheck policy before outbound requests; invalidate
queued work and cached derivatives when policy changes. Previously transmitted
content cannot be recalled by changing local policy.

### Rationale and consequences

The owner permits external AI for selected personal data while requiring
exclusions for particular repositories/records. Filtering only the final answer
prompt would still leak content through indexing or intermediate summaries.
Excluded records remain available through owner-scoped keyword search and direct
viewing. Local semantic inference is an optional later optimization within the
budget, not a prerequisite for private records to be useful.

Policies and deletion state must be restored with the data. Test prohibited
egress at every external-AI boundary using synthetic sensitive markers. Actual
repository policies are selected during setup; no private corpus has been
uploaded or authorized for AI processing by this documentation change.

---

## ADR-017 — Bound the private deployment by a combined monthly budget

**Status:** Accepted constraint; hosting choice pending

**Date:** 2026-09-30

### Decision

Provide authenticated access from external networks and other devices, prefer
AWS, and fit lifhop's combined hosting/storage/backups/AI usage within USD 20
per month. Account for applicable taxes, network, queues, logs, and any new
DNS/domain costs. Initial historical indexing is part of the budget as well.
Do not rely on trial credits or assume model APIs are covered by subscriptions.

Evaluate a small single-host deployment before multi-service infrastructure.
The README's potential ECS/RDS/ALB architecture is not a required resource list.
Choose host, region, credential strategy, and model only after corpus sizing,
memory/load checks, and a total cost estimate. Preserve role-based AWS access
where supported and document any required alternative; do not silently introduce
permanent embedded credentials. No hosting service is selected by this ADR.

### Rationale and consequences

The private release serves one owner and must remain affordable. Source history
and model work are variable costs, so enforce bounded imports, storage growth,
paid-job concurrency, and model spend with headroom. Pause optional paid work
when its allowance is exhausted while preserving stored records and keyword
search. Billing alerts supplement these controls; they are not a hard spending
cap. Fixed infrastructure continues to accrue costs when jobs pause.

Do not silently increase the budget or discard agreed source coverage to fit.
If measurements cannot satisfy the constraints, present the concrete tradeoff
and revise the plan. Revisit deployment architecture for commercial demand or
measured personal-release capacity limits.

---

## ADR-018 — Use durable ImportJob polling for the local import queue

**Status:** Accepted
**Date:** 2026-10-01

### Decision

Default `QUEUE_MODE=local` uses existing PostgreSQL ImportJob rows as the durable
work queue, alongside default local SeaweedFS storage. The separate worker polls
PENDING jobs and recoverable stale RUNNING jobs. `QUEUE_MODE=aws` explicitly
selects the existing SQS interface; S3 and queue selection remain independent.

### Rationale and alternatives

Phase 1.2 needs ZIP uploads to work locally without contacting AWS. In-memory
queues lose work across restarts and cannot connect separate API/worker
processes. An additional SQS-compatible service adds development infrastructure.
For the current single-owner archive, polling the already-persisted ImportJob
is sufficient and requires no new service or package. This is a local delivery
path, not a change to the private-release hosting/queue decision.

### Processing and failure behavior

Job claims use row locks; processing retains a row lock through the durable
result commit and an owner advisory lock to serialize imports for that owner.
Completed/partial/failed deliveries are no-ops until explicit retry. Retry accepts
only FAILED/PARTIAL jobs, with a configurable processing-attempt budget (default
3). Infrastructure failures allow bounded automatic redelivery; invalid archives
are recorded as permanent failures and require explicit owner action. In AWS
mode, acknowledgement follows a durable result, including a permanent rejection.
This refines ADR-012's former behavior of leaving every processing exception
unacknowledged. Unknown failures still leave their messages unacknowledged.

A RUNNING job left by a crash is eligible after the processing budget plus 60
seconds; a live transaction's row lock prevents replacement. Per-item savepoints
isolate malformed DB values. Limits cover upload/body bytes, declared extracted
bytes, archive member count, conversation/node counts, query timeout, and deadline
checks. These are bounded-work controls, not an exact-time process watchdog.

Result Entry IDs, sanitized positional item errors, and attempts are persisted.
New imports link Entries to their latest original artifact. Migration defaults
do not reconstruct result/original links for pre-existing imports. Versioning,
freshness/completeness reconciliation, deletion suppression, and artifact purge
remain Phase 2.2; new-job reimport still uses the existing content-replacement
semantics. There are no new AWS resources or recurring costs in this slice.

---

## ADR-019 — Start archive search with literal phrases and explicit dates

**Status:** Accepted
**Date:** 2026-10-01

### Decision

Phase 1.3 searches owner-scoped Entry titles and content using PostgreSQL ILIKE
with escaped wildcards. Trim the query's outer whitespace; preserve its internal
spaces and punctuation. Rank case-insensitive exact titles, title substrings,
then body-only matches, breaking ties by created_at DESC and id DESC. This
supports Korean/English phrases, names, numbers, units, and code symbols without
introducing a language tokenizer. GET /entries/search returns total/items and
limit/offset; retain the existing array-returning GET /entries for compatibility.
Browser pages use 20 items, preserving filters/page in the list URL.

Use existing provider values for provenance: manual, markdown, and chatgpt.
New manual/Markdown Entries set their provider explicitly. Backfill old Markdown
only when the artifact owner matches and MIME is text/markdown. Other unproven
or unrecognized providers display unknown; do not guess from type or content.

created_at means registration in lifhop, while event_at means the known source/
event timestamp (ChatGPT conversation creation for current imports). Display and
filter dates in Asia/Seoul initially. Inclusive date ranges become local midnight
through the next midnight, converted to UTC. Event-date filters exclude NULL;
neither registration time nor dates mentioned in text fill missing event_at.
Require an offset on API event_at input. Keep timezone-aware PostgreSQL columns.

### Query-plan evidence and limits

An isolated PostgreSQL 17 temporary table used 100,000 synthetic records across
20 owners, including Korean titles and numeric/code content, with the existing
user/provider/external-ID index. EXPLAIN ANALYZE of one owner's newest 20 rows
changed from Bitmap Heap Scan of 5,000 owned rows plus top-N Sort to Index Scan
with early LIMIT using (user_id, created_at DESC, id DESC). In one run the list
query took about 2.40 ms before and 0.03 ms after; these are illustrative local
synthetic timings, not a real-corpus latency guarantee. Add that B-tree index.

The actual title-ranked phrase query retained a Bitmap Heap Scan plus Sort
before/after; this index does not accelerate arbitrary substring ranking or
exact total counts. Do not claim full-text-search performance from the list
measurement. Synthetic relevance tests cover Korean/English phrases, exact
names, numbers/units, literal %, _, backslash and code punctuation, title ranking,
owner isolation, tied timestamps, and Seoul calendar boundaries. Validate real
corpus relevance/volume before selecting pg_trgm or language-aware full-text
indexes. There is no fuzzy matching, stemming, synonym expansion, attachment
extraction, new service, or added dependency. Offset pages may shift during
concurrent writes; cursor/snapshot pagination remains a later measured need.
