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

---

## ADR-020 — Stream large ChatGPT exports and persist import progress

**Status:** Accepted
**Date:** 2026-10-01

### Requirement and decision

An owner export near 500 MiB contains numbered conversation JSON shards and
substantial non-conversation data. Support legacy `conversations.json` and
`conversations-<number>.json` / `conversations_<number>.json` arrays, including
nested paths. Preserve archive order as the stable processing order.

Keep FastAPI's spooled upload as a file and use a bounded, serial S3 multipart
transfer. The worker streams the object into an automatically cleaned temporary
file; JSON arrays are decoded one bounded record at a time with the standard
library. A complete preflight pass validates shards and determines the total
before Entry writes. A second pass converts records. This requires no new service
or package and leaves media in the preserved original.

Defaults are 1 GiB compressed ZIP, 1 GiB total declared uncompressed content,
256 MiB conversation JSON, and 16 MiB per JSON record. Markdown retains 25 MiB.
Conversation/node/file/attempt limits remain unchanged. Local measurements fit
the existing 120-second cooperative processing budget; deployment capacity must
be measured separately. Temporary disk and concurrent requests remain relevant
resource costs even though ZIP content is no longer materialized in RAM.

### Commit and retry semantics

Save Entries, success/failure counts, result IDs, and sanitized item errors in
one transaction per 25 records. The sum of committed processed/failed counts is
the resume cursor into the preserved immutable archive. Roll back the current
batch on infrastructure failure; retain earlier batches and resume after them.
Preflight may be repeated after restart and is read-only. No new schema field is
needed because progress counters already exist and are committed with the data.

Replace ADR-018's whole-import row/transaction lock with an owner session advisory
lock on a pinned physical PostgreSQL connection, retained across batch commits.
Each active batch also locks its job row. The connection is closed/invalidated
if lock cleanup fails, and process exit releases the lock. Live work cannot be
superseded just because RUNNING age crosses the stale threshold. A crashed worker
is eligible after the processing budget plus 60 seconds; an infrastructure error
can make it immediately PENDING within the attempt budget.

Completed/partial/failed deliveries still do no work without explicit retry.
Retry resumes incomplete work. When all items were visited and errors remain,
explicit retry resets progress and reprocesses the archive, preserving the prior
full-retry behavior. Stable source IDs prevent duplicate Entries. Full replay
can still replace current content or recreate a deleted record; Phase 2.2
versioning/tombstones remain outstanding. A textless active branch stays an
observable EMPTY_CONVERSATION error rather than silently disappearing.

### Evidence and verification boundaries

Actual local HTTP upload, SeaweedFS storage, and separate worker processes were
checked with synthetic and owner-provided large archives in disposable schemas.
Checks covered saved progress, original byte equality, result search counts,
reimport uniqueness, and synthetic termination after a saved batch followed by
recovery. Worker peak RSS was approximately 119 MiB for the synthetic archive
and 211 MiB for the owner archive. These are local measurements, not hosting
sizing guarantees. No external AI service or AWS storage was used.

The integration script sets its environment before importing application settings,
verifies the disposable DB and unique schema, and records exactly the object keys
it created for cleanup. These checks are required following a corrected validation
incident described in CURRENT.md. Private archive contents never enter fixtures,
Git, or tool output. The owner confirmed the expected large-import browser
result on 2026-10-02.

---

## ADR-021 — Verify acquisition with local previews before persistent ingestion

**Status:** Accepted for Phase 2.1
**Date:** 2026-10-02

Use a separate read-only acquisition CLI and private HTML/JSON previews to verify
Codex/GitHub access, source IDs/dates, actual messages/results/diffs, and coverage.
Do not write Entries or expand the canonical model before Phase 2.2 introduces
versions, deletion suppression, and external-AI policy. No dependency/service or
schema change is required for these checks. Private previews stay out of Git and
are not sent to external AI; sanitized/truncated previews are not exact originals.

Prefer official Codex app-server reads over a version-dependent content parser.
The verified CLI is 0.158.0. Paginated sessions require the history projection DB
and experimental `thread/turns/list`; JSONL-only full-history reads returned no
turns for the selected sample. Run against disposable copies of selected rollouts
and a read-only SQLite backup so app-server scan/repair or migrations cannot
alter source history. Copy no auth/config/state DB. Allow only history read RPCs;
never resume a session, execute captured commands, or start model turns. Record
version, snapshot identity, page limits, unsupported items, and unknown outputs.
An idle-session snapshot is the verified path; full backfill and a future CLI/DB
format require renewed checks rather than a silent fallback.

Use GitHub versioned REST GET with a pinned selected branch head. Inventory
reachable commits with pagination, preserve repository ID and commit SHA, and
read sample documents at that same SHA. Public read is sufficient for the
selected user-owned repository; do not add a token solely for this sample.
Private/organization credentials need separate least-privilege, SSO, and expiry
checks. An absent patch, inaccessible document, 401/403/404/429, or incomplete
page walk is an explicit gap and never proof of deletion. Enumerated branches
are not automatically selected for ingestion. Full commits/documents followed
by PR/review/issue collection remains Phase 2.4.

Real evidence and owner verification steps are recorded in `ACQUISITION.md`.


---

## ADR-022 — Preserve observations and separate collection, AI and deletion

**Status:** Accepted for Phase 2.2
**Date:** 2026-10-02

Keep Entry as the current searchable projection and retain EntryVersion with an
explicit current pointer. Preserve source identity/scope, locator, source/observed
times, parser, completeness, normalized hash and structured message/command/diff
evidence. Immutable source versions use retained JSON; exact uploads reference
ImportArtifact. EntryMaterial also links unchanged repeated uploads for deletion.
Existing rows become one unknown-completeness initial observed version, with no
invented source modification times or earlier history. Known Markdown byte
identities deduplicate future replay; existing duplicate rows remain independent.

Changed content/evidence is retained. Auto-select only a strictly newer source
snapshot whose completeness does not decrease. Unchanged current observations
advance a freshness frontier without duplicate versions; older/partial/unknown
candidates need explicit selection. Imported text is read-only; owner annotation
is separate. Source-deleted records remain visible; auth/fetch failures are not
deletion. Local search includes retained source states by default and explicitly
filters them; future AI source-deletion inclusion is opt-in within policy.

SourcePolicy scopes collection and external-AI permission independently; record
AI permission is an additional deny boundary. Both AI permissions default false
and upsert never resets them. Future AI/derived results must use the common
dependency/epoch egress boundary for embedding/reranking/summary/answer/telemetry.
Every dependency must be allowed, and changed owner policy/content invalidates
prepared work or cached results. No remote AI service or AI cache/job is added.

A transaction advisory owner lock (namespace 12022), acquired before job/record
locks, serializes ingest commits, deletion, policy and egress. Keep the existing
import session lock (12012) across batches; reacquire policy lock per batch and
check suppression per item before its atomic commit. A lifhop delete removes
all versions/annotations, retains minimal identity suppression, immediately
blocks raw downloads and records durable object deletion in a PostgreSQL outbox.
This reuses the current worker and adds no AWS service, queue or dependency.

A shared ZIP is purged whole when any collected member is deleted; other
normalized records remain. Every newly detected suppressed ZIP upload is also
blocked/purged. All attachment final purges wait 11 minutes because PUT URLs can
rewrite objects after completion; raw downloads already issued have 10-minute
expiry. Retry failures remain observable. AWS purge explicitly deletes all
exact-key object versions/delete markers and treats partial errors as failures.
Real AWS IAM/Object Lock/versioned deletion are deployment checks.

Keep deletion ledger rows after explicit Allow reimport so old backups still
exclude pre-deletion content. Export/apply the latest minimal ledger before
serving a restore; current denies must also be reapplied, with restored AI off
until verified. Content backup expiry target is 30 days; automatic journal,
backups, expiry and restore supervision remain Phase 5. Logical deletion does
not promise secure erasure of PostgreSQL pages/WAL or owner source originals.
Operator commands and user verification are in HISTORY.md.

---

## ADR-023 — Ingest reviewed Codex turns with atomic durable receipts

**Status:** Accepted for Phase 2.3
**Date:** 2026-10-03

Use one recorded Codex turn per PROJECT_EVENT Entry, retaining ordered messages,
command results and diffs as structured evidence and readable searchable text.
The source identity is device UUID + original thread/turn ID (a deterministic
hash when the composite exceeds the identity limit); archived/fork context is
retained without merging separate source turns. Never invent command outcomes.
Keep the device UUID in a private persistent config; recovery requires explicit
reuse of the authenticated source UUID instead of silently generating a new one.

Read with official app-server history RPCs against disposable rollout copies and
a read-only history projection backup. Parent credentials are excluded from the
child environment. Source changes, active sessions, duplicate thread sources,
unknown/divergent identifier/order verification, unsupported CLI/formats and
resource limits remain coverage/completeness gaps. Pin support to CLI 0.158.0;
there is no implicit raw-content parser fallback.

Explicit preview creates a sanitized private immutable manifest/payload bundle;
apply requires that exact reviewed config/device/hash contract. Credential/path
filtering is incomplete, so personal preview review remains required. Original
rollouts/history DB stay local. Store sanitized canonical text/evidence directly
in PostgreSQL over authenticated HTTP, reusing Phase 2.2 history and owner locks.
The synchronous local collector provides natural backpressure and does not need
S3/SQS, a new worker, dependency or AWS resource for this flow.

CollectionRun and minimal body-free CollectionRunItem receipts persist Entry/
version outcomes in the same transaction before ACK. Stable run manifests and
receipt digests reject changed replay; a local owner/origin/device-bound checkpoint
is checked against the server before skipping a turn. Lost ACK, interrupted
apply and server restore can replay safely. Preflight policy/deletion checks avoid
blocked body transmission; the server rechecks under the owner lock. A policy
change after preflight can reject an already transmitted body without storing it.
Successful receipts are historical facts and survive later Entry deletion; they
do not bypass current suppression or represent current retained Entry counts.
Blocked outcomes are terminal for that run; explicit re-enable/reimport requires
a new reviewed preview. Existing annotations/permissions remain intact, with AI
off by default and no external model calls.

Sources shows run outcomes and coverage separately from record completeness.
Completed means the selected reviewed manifest has durable outcomes, not complete
recovery of every historical source or continuously current collection. Scheduled
collection and browser collect-now remain Phase 4. Operational commands and
verification boundaries are in `CODEX_BACKFILL.md`.

---

## ADR-024 — Derive Codex sessions and primary reading from retained turns

**Status:** Accepted for the checkpoint after Phase 2.3
**Date:** 2026-10-04

Keep turn-level Entries, immutable observed versions and full normalized evidence.
Derive session browsing from current version payloads grouped by owner, Codex
source scope and thread ID. Group before pagination; forks and devices remain
separate. Counts describe retained turns, not full source coverage. Verified turn
positions determine order; missing/duplicate positions use a warned date/ID fallback.
Keep deletion, annotations and permissions per turn.

Preserve official assistant phases and original turn positions in v2 DevSession
metadata. Basic reading includes user/assistant messages and excludes explicit
commentary; unknown assistant messages remain visible. Default search still includes
user/unknown/final messages, command results and diffs, excluding commentary. Full evidence is
available in Work details and commentary search is opt-in. Reasoning items remain
outside collection. Store nullable current Entry.primary_content for SQL search,
refresh it atomically on current version changes, and distinguish NULL from an
empty projection. Existing content, hashes and version bodies are not rewritten.

Serialize absent new metadata exactly as v1 to preserve old preview/receipt digests.
Accept the explicit supported parser versions; never reinterpret legacy phases.
Same-time observations can remain candidates requiring explicit current selection.
Extend the collector's installed CLI support to 0.160.0 after official schema and
actual read verification, retaining 0.158.0 support. The separate Phase 2.1 probe
remains pinned. No new dependency, AWS service or automatic personal apply is added.

Prefer saved Codex thread names for session display; retain original turn titles.
Capture optional sanitized thread_name from official thread metadata or the latest
valid matching row of the persisted resume index. Read that index only from a
bounded private disposable copy (8 MiB maximum), without exposing the original
state DB to app-server. Absent names serialize as before, preserving old digests.
Choose the most recent named current observation per session. Display whitespace
normalized titles capped at 60 characters plus an ellipsis, and the representative
first question as a separate two-line preview. No new AI call generates a title.
Previously collected records require reviewed recollection/current selection;
never silently rewrite old evidence or reviewed bundles to add names.

Derive the questions/answers reading text at presentation time from structured
messages; do not change the stored search projection or evidence to simplify the
reader. Hide commands/results/diffs from basic reading and retain full ordered
evidence in Work details. Show collection gaps separately. Preserve command-like
text inside an assistant message. Valid legacy payloads work without recollection;
invalid/missing structured evidence uses a warned full-content fallback.

## 2026-10-05: GitHub commit/document historical backfill

Deliver Phase 2.4A commits and selected Markdown documents first; owner verification
precedes Phase 2.4B discussions. Use numeric repository scope with commit SHA and
commit/path document identities. Store typed evidence in existing EntryVersion
JSONB; source observation rules, annotations, AI denies and deletion suppression
remain shared. No migration, queue, worker, AWS service or dependency is added.

Pin selected branch heads, validate name/numeric-repository pagination Links,
cache bounded private REST GETs and pause on quota with a saved retry time. Verify
regular Git tree modes before reading Contents at the commit SHA. Keep changes
from distinct commits even if their document content matches; reuse a reachable
path/blob snapshot for the selected-head baseline mapping. Branch membership stays
in run coverage rather than immutable evidence.

Separate mutable preparation from a sealed sanitized bundle and explicit apply.
Keep provider-specific strict run/item/coverage contracts and preserve old Codex
serialization/checkpoint behavior. Source gaps and lower bounds make finish partial
even when every manifest item has a receipt. Selected invalid records can have
body-free failure receipts. Source renderers display inert text and derive trusted
GitHub locators from repository/SHA/path rather than arbitrary imported URLs.

GitHub authentication remains explicitly selected: reuse `GITHUB_TOKEN` or opt into
`--github-cli-auth` after the user logs in using GitHub CLI. Read the existing token
only into process memory for GETs. Track anonymous/authenticated quota mode in the
private preparation journal so a mode switch does not inherit the other's wait;
never store a token or change source/config identity to bypass a saved deadline.
Actual backfill verification uses a fresh, verified isolated PostgreSQL schema
and real HTTP calls, preserving the original reviewed bundle and personal DB.

## 2026-10-06: Derive GitHub repository browsing from retained Entries

Keep commit and commit/path snapshot identities and all observed versions.
Group browsing by owner/provider/numeric repository scope before pagination;
renamed repositories retain one group. Counts describe current retained Entries,
including source-deleted records; invalid metadata remains accessible separately.
Search retains individual hits and bounded current-version repository references.

Entries stays ordered by most recent registration. Within repositories, order
commits/snapshots by known event date descending, NULL last, then Entry ID.
Group documents by exact path with deterministic C collation for path pagination.
Latest retained snapshot does not assert current GitHub/selected-HEAD content;
branches/run coverage remain in Sources. No AI-generated title or new grouping
entity, schema, infrastructure or dependency is introduced. Deletion/annotations/
permissions remain per Entry. Safe local repository returns preserve independent
path/snapshot pages and the original Entries/Search context.

## 2026-10-06: Preserve independent GitHub discussion records and group their reading

Phase 2.4B uses numeric repository/object IDs for PRs, issues, general comments,
reviews and code-review comments. Issues API PR rows are excluded; PR identity
uses the Pulls API ID. Parents and children remain separate Entries/versions.
Children retain only parent identity/number/kind, not a copy of parent title/body.
Deleting a parent suppresses its reimport and leaves independent children; orphan
reading never reconstructs the removed body. Group before pagination using current
owner-scoped metadata. Orphan dates use the first known retained child date with
an explicit label; all-unknown dates remain separately filterable.

Reuse SourcePolicy, owner locks, receipts, version selection and individual AI
denies. Source-deleted state is not inferred from access/fetch failures. Reviews
have no verified REST edit clock: changed observations remain review candidates.
Submission or observation time never substitutes for an edit date.

B has separate config/parser/preview format while reusing bounded repository GETs,
filtering and explicit apply. Optional discussion coverage omits only its own
absent field, preserving A v1 bytes/digests/replay. Kind counts are verified at
seal/create/finish. Mutable pages describe an observation window, not an atomic
snapshot; interrupted stages revalidate roots and retry once on a changed clock.
Explicit gaps cover failed walks and capped PR commit membership. Related SHA
roles are distinct and link only to the same owner's retained repository commits.
No migration, dependency, external AI, queue/worker or AWS service is added.

Actual selected-source inventory was empty on this date. Verify Empty via real
HTTP and nonempty behavior with labeled synthetic evidence, without creating
GitHub objects. Personal apply/browser confirmation and real nonempty/private
discussion validation remain separate checks.

## 2026-10-07: Freeze private evidence and lexical baselines before semantic retrieval

Phase 3.1 uses local read-only PostgreSQL transactions and existing password
verification; it adds no remote evaluation API or persistent application tables.
Extract only the existing search conditions/ranking so evaluation and browser
keyword search cannot silently diverge. Metadata projections avoid copying full
result bodies. Evaluation never invokes policy helpers that create missing rows.

Store owner/database-bound immutable dataset revisions under ignored private
`.local/evaluation/`. Gold references pin Entry/version/hash and Unicode passage
offsets/hash; source text is resolved in memory. Reports omit question/claim/source
text, titles and annotations. Historical Entry hits do not prove historical passage
retrieval. Missing, stale or failed cases stay visible in denominators/status counts.

Freeze the natural question and up to three auxiliary keyword queries before each
run. Score auxiliaries independently, average within a case then across cases,
and keep primary/auxiliary results separate. Policy eligibility is an observation,
not an AI response test. A synthetic fixture can verify tooling but cannot complete
the real about-20-question set. Actual question/evidence meaning requires owner review.

Local deterministic authoring may connect candidate spans without sending excluded
source text to a model. Candidates remain drafts; `[Candidate]` claim placeholders
are blocked from approval until the owner edits them into verified facts. A literal
match can repeat a question without answering it. Cross-source candidates require
explicit retained SHA overlap; missing matches are scoped candidate gaps. No source
AI policy is changed to author an evaluation set.

Owner-only local authoring previews may contain bounded, escaped pinned passages
and alternative keyword matches. Validate ownership, content/passage hashes and
version availability before display, honor the case filters, and never auto-edit
gold or approvals from search matches. Save these previews privately with no remote
resources/scripts; do not open excluded real passages in agent browser tools.
Regeneration checks current availability, while already exported immutable files
can retain old text. Measurement reports keep their existing body-free contract.

Guided answer registration collects owner-written facts and selected pinned evidence
locally. Each claim references its evidence group; explicit owner confirmation is
required before immutable publication. Run both fixed baselines after registration,
retaining the saved revision if measurement later fails. Do not treat the owner's
confirmation that an answer exists as an identified passage or a fabricated gold claim.

## 2026-10-08: Keep local passages disposable and anchored to source versions

Phase 3.2A adds PostgreSQL simple FTS over bounded current-version passages, retaining
Exact phrase search. Source Unicode ranges/hash identify original title/body text;
Codex canonical order maps primary messages separately from work evidence. Unverified
mapping and input/passage budgets produce visible partial indexes, not fabricated text.

Synchronize current selection and derived rows in one transaction, using existing
owner-before-record locking. Remove previous projections when current changes; restore
rebuilds new passage IDs while immutable source versions remain. Stale/deleted/foreign
passage links return 404. Authenticated owner backfill is resumable and does not mutate
source bodies, annotations, receipt history or AI policy. Migration does not backfill text.

Group only exactly equal GitHub document chunks with verified numeric repository/path
identity. DB grouping precedes representative-Entry quotas and pagination; aliases retain
exact version/offsets and are read in bounded pages. Current retained snapshots do not
assert live GitHub HEAD. API shared owner locks stabilize each read against existing
exclusive writers; statement/lock limits and a shared retrieval deadline bound work.

Passage evaluation reuses ranking/filter conditions and freezes existing gold revisions.
Success requires complete same-version/field gold coverage; rank is the first top-K that
covers the full span. Validated aliases are checked independently of card preview limits.
Reports remain body-free. Local retrieval is available for external-AI-denied records;
future external embeddings/answers still require application policy and budget checks.
The owner's necessary current-Codex development-read authorization is separate from
application AI permission and does not extend to other review providers.

## 2026-10-08: Measure semantic retrieval before persistent vector storage

B1 uses an authenticated, owner/database-bound dry-run manifest and frozen approved
questions to compare lexical/vector/RRF retrieval on the same AI-allowed corpus.
Only current body passages from NOTE/DOCUMENT/CONVERSATION are sent; work evidence,
annotations and complete source versions are excluded. The bounded passage gate
retains the existing owner lock until dispatch completes; query consent is separate.
The provider defaults off. `httpx` moves from development to runtime dependencies;
fixed-origin requests have no redirects, environment proxies or automatic retries.

Record reservations before dispatch using a body-free AiUsageAttempt ledger and
billing-scope advisory locks across users/months. Uncertain attempts retain their
maximum exposure until authenticated reconciliation, preserving the original month.
API success costs survive source/quality failures. B1 vectors live only in bounded
memory and a repeated run may incur repeated cost. Neither current Codex development
reads nor implementation authorization changes application AI policy or initiates
paid experiments. pgvector and background/browser integration await measured benefit
and owner confirmation at the B1 checkpoint.

## 2026-10-10: Bound reranking separately while sharing AI billing and policy locks

The B1 rerank experiment reuses verified section candidates and unchanged gold;
it does not change product search. Model input contains one approved question and
exact current body slices with opaque IDs. Strict model output is candidate grades
only; registered claims and gold never enter the request. No answer or model
reasoning is collected. Rerank defaults off and transmission needs a fresh scoped
manifest and explicit consent, independent of DB permissions and previous grants.

Extend the existing body-free AiUsageAttempt ledger with output reservations,
separate actual input/output usage and pinned per-model prices. Keep old embedding
rows and reconciliation semantics. Both callers share billing scope/month budget
and call-slot/owner locks. Record uncertain before dispatch; release proven
pre-send failures, settle valid usage even when grade parsing fails, and count
only actual cost after settlement so unused output headroom returns to the budget.
Unknown usage stays conservatively reserved. Migration `e37c2d14b953` preserves
existing rows. No separate service, queue, dependency or product vector store is added.

An immutable attempt marker prevents automatic duplicate runs for the same manifest.
Private bounded grade captures enable zero-provider replay. The held-out set remains
unmeasured until a tuning candidate passes and a separate validation grant is given.
Quality, actual cost and added latency must be reviewed before proposing B2 usage.

## 2026-10-11: End B1 tuning and deliver optional Semantic search incrementally

The owner approved moving from repeated experiments to a usable optional Semantic
mode. Preserve the previous failed gates, model settings, captures and unresolved
rerank response failure. Semantic-only 17/18 complete hits on reused tuning cases
justify a limited trial, not independent validation or a replacement for local
search. Hybrid and paid reranking remain deferred. Do not select a new model or
reinterpret old failures to claim success.

Build pgvector storage/lifecycle first, then explicitly activated bounded indexing,
then the Semantic API/UI. Existing keyword and passage search remain default.
Retain the measured `sections-600-v1` exact subranges without rebuilding the local
passage index: each persisted vector references its parent passage, parent hash,
absolute source offsets, slice hash and model/config. This needs multiple vectors
per parent, replacing the earlier one-vector-per-parent schema proposal.
Use exact cosine search initially. pgvector is the PostgreSQL extension; the
pgvector Python adapter supplies SQLAlchemy's vector type and distance operators.
Current owner/source/record permissions and source version must be checked both
when publishing a vector and when reading it. Revocation/current selection/deletion
remove invalid derivatives in the source transaction. Reallow does not restore
old vectors, and an in-flight result cannot cross a policy revision change.

After the product flow works, run one separately authorized fresh ten-case
evaluation. Preserve the result and decide 3.3 scope from quality, usability, cost
and latency. Further tuning requires a new explicit decision. Functional isolation,
prohibited-transmission prevention, deletion correctness and budget bounds remain
delivery requirements. This implementation approval grants no new paid API calls
or changes to record permissions.

## 2026-10-11: Explicit bounded indexing uses PostgreSQL jobs and a separate worker

Keep approved indexing scopes and per-slice jobs in PostgreSQL, alongside the
existing durable AI usage ledger. No Redis, new SQS queue or additional dependency
is required for this local bounded flow. Authenticated preview returns body-free
owner/database/policy-bound anchors and a conservative byte-based cost estimate;
only explicit activation creates jobs. Existing AI permission and configured
OpenAI credentials do not activate indexing. API source writes never call OpenAI.

Activation defaults to the current snapshot. Separately choosing follow changes
permits future eligible content only within that provider/scope or explicit Entry
selector and the same cumulative cost/call limits. Reject overlapping follow
selectors even while paused. Pausing prevents further dispatch checks; a request
already dispatched can finish. Resuming catches up current eligible content without
resetting limits. Record/source permission checks still apply to every send and
publication. A grant to follow changes is distinct from granting AI permission.

Link a durable dispatch token to the shared usage reservation before HTTP. A
60-second work lease exceeds the bounded 10-second provider request. Recover
expired jobs automatically only when no dispatch attempt exists or it was proven
released before sending. Uncertain attempts remain uncertain; settled paid results
lost before publication remain failed. Neither state automatically sends again.
Explicit retry rechecks current policy/anchors and requires unresolved usage to
be settled first. Run budgets/counts span billing-scope configuration changes and
never reset on pause/resume/retry. Stored vectors can be reused only from currently
allowed exact same-owner slices. The embedding worker is separate from the existing
import/purge worker; AWS worker supervision remains a later deployment decision.

## 2026-10-11: Semantic queries require an explicit POST and ephemeral results

Keep local index coverage and slice/location reads as GETs that never send a
question to OpenAI. The Search form first reviews the index; a separate consent
checkbox and action makes one paid question embedding POST. No eligible vectors
means no paid request. Recheck policy revision/current eligible corpus under the
query dispatch owner lock, then again before returning locally ranked evidence.
Query vectors are never stored, source text is not sent by the query route, and
successful provider cost remains settled even when later policy/ranking checks fail.

Hash owner/request ID with a Semantic-query domain before using the ledger run ID,
so requests cannot share indexing caps. The existing cumulative one-call limit
blocks possible paid replay for that ID across processes/billing-scope changes;
proven pre-send releases remain safe. No additional persistent request table is
needed. A new explicit user action creates a new request ID and can incur new cost.

Use exact cosine ordering, grouping identical validated GitHub document slices by
repository/path/hash/length before the top-20 cutoff and without an Entry quota.
Location reads do not depend on lexical question matches and independently apply
owner/current-policy/filter checks. Semantic result bodies are ephemeral in the
screen; navigating back or reloading preserves filters but never resends the paid
query automatically. Local status refresh hides results after a revision change.
Synthetic browser/HTTP demos test behavior only; actual retrieval quality remains
subject to the separately approved fresh validation check.

## 2026-10-13: Begin cited answers from user-selected current passages

The first Phase 3.3 answer action follows the optional Semantic result screen.
The owner selects one to five exact slices and separately consents to sending the
question and those slice bodies to OpenAI. This makes the transmitted evidence
visible before the paid action and avoids a second question embedding request.
The server rechecks current owner/source/record policy, version and exact slice
hash under the owner lock before dispatch and again before returning citations.
Answer output cites only IDs from the submitted set; an insufficient result has
no citation. The output remains a draft for human review, since structural
validation cannot prove that a sentence is supported by its cited text.

Use the existing Responses transport pattern, pinned GPT-4.1 mini snapshot,
structured JSON output and shared usage ledger. One request permits one paid
call with at most USD 0.01 reservation and 512 output tokens; retries are not
automatic. `ANSWER_MODE=off` by default means an embedding configuration or an
older transmission approval does not activate answer generation. The synthetic
demo provides a mock response for browser checks. No new database or dependency
is needed. Historical evidence, automatic context selection, retrospectives and
real answer quality are separate later slices.

## 2026-10-14: Allow local Passages as selected answer evidence

Use the same consented answer endpoint and policy/cost boundary for either
Semantic slice IDs or local Passage IDs. A request must choose exactly one kind;
the response identifies its citation kind and source ID. This lets the owner
answer from records that have a local passage but no Semantic vector, without a
paid question-embedding call. Passage text remains bounded at the existing
2,000-character projection limit, with a 14 KiB total answer request cap.
Current-version, source/record AI permission, work-only and deleted-source checks
run under the owner lock before sending and again before returning citations.
The answer model stays off by default; no personal records are transmitted by
this implementation check.

## 2026-10-17: Move selected-passage answers to GPT-6 Luna

Use `gpt-6-luna` for answers through the existing Responses transport. Preserve
the prior model's nonreasoning role with explicit `reasoning.effort=none`,
temperature zero, 512 output tokens and the same nested structured-output
contract. Use `prompt_cache_options.mode=explicit` without breakpoints so no
cache reads/writes occur and the existing simple input/output ledger remains
accurate. Treat unexpected cache usage as unresolved rather than silently
undercharging. Model, reasoning/caching settings and published prices contribute
to the configuration hash; completed old protocols cannot authorize new calls.

Standard short-context input/output prices are USD 0.10/USD 0.50 per million
tokens. Preserve per-attempt historical prices and all prior uncertain usage.
Keep the one-call/USD 0.01 request cap, source/owner/version/policy rechecks,
off-by-default activation and separate transmission consent. The user requested
one migration check: three previously reviewed cases passed with known selected
context, at USD 0.000205 total. This does not establish independent quality or
speed superiority; stop repeated paid tuning and proceed to evidence selection.

Embedding remains `text-embedding-3-small` at 1,536 dimensions. A change to
`text-embedding-3-large` would require compatible document/query vectors, explicit
reindex scope and separately measured benefit; a new answer model does not require
replacing the embedding space. The deferred reranking experiment remains unchanged.
Sources: [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[migration](https://developers.openai.com/api/docs/guides/latest-model),
[cache behavior](https://developers.openai.com/api/docs/guides/prompt-caching),
[embeddings](https://developers.openai.com/api/docs/guides/embeddings).

## 2026-10-17: Recommend complete parent passages locally before answering

Keep Semantic ranking and its embedding space unchanged. Expand at most twenty
ordered eligible hits to their current parent Passages, deduplicate validated
document parents, then propose at most five complete parents within the actual
serialized answer-request limit. Report skipped duplicates/count/byte limits;
never silently truncate source text. This recommendation holds the existing
shared owner read lock, checks the observed policy revision and current filters,
and creates no provider call, usage reservation or persistent recommendation.

The owner reviews/adjusts exact text before a separate consented answer action
using the existing Passage-ID path. Recommendations assert neither factual
sufficiency nor transmission authorization. Ephemeral selections and consent
reset across evidence-kind/account/filter/policy changes. Local known-case
coverage (3/8 to 6/8, no group losses) justified implementation; further paid
tuning, a reranker and a new embedding space remain out of scope.

The owner confirmed that individual search/recommendation/answer steps should
not be mandatory in the final product. Next plan one question action that runs
these stages within explicit source-transmission consent and cost limits; keep
manual evidence review as an optional advanced flow. The current implementation
retains separate actions until that integrated flow is implemented and verified.

## 2026-10-17: Orchestrate one consented question through existing bounded APIs

The integrated answer mode freezes the question/filters/session/revision and
sequentially awaits the existing Semantic, local recommendation and answer APIs
in the browser. No new server workflow, queue or persistent answer table is
needed. One action's consent explicitly includes the question for search/answer
and up to five automatically selected eligible parent Passages. The combined
maximum is the sum of existing per-stage guards: one query/USD 0.001 and one
answer/USD 0.01. Shared monthly accounting continues to apply to each dispatch.

Reuse one action UUID in the existing distinct query/answer ledger domains so
each stage retains its durable one-call limit. A spent/uncertain stage cannot
replay automatically; a new explicit action can incur new cost. Stop/navigation/
draft/filter/account/revision changes and a 60-second browser deadline prevent
later stages, while already sent requests may still finish/be charged. Query
cost survives an answer-stage failure. Add an optional observed policy revision
to the answer request; integrated calls supply it, and mismatch blocks before
reservation. Existing exact source/policy checks and conservative uncertain
reservations remain. Manual evidence review is optional advanced UI; ordinary
answers show citations and expandable original context. Models/indexing and
off-by-default activation are unchanged. This implementation authorizes no new
paid provider experiment or personal-data transmission.

## 2026-10-17: Start period retrospectives with bounded local temporal sampling

Use a local, owner-scoped date preview rather than a similarity query for the
first period summary. Source/event dates are the default; Added dates explicitly
mean collection time. Require a range of at most 92 days in Asia/Seoul. Keep one
first eligible body Passage per record, group verified identical document parents,
sample at most twenty positions across chronological rank and select at most five
complete parents within the existing serialized answer limit. Display counts and
all scope/coverage limitations; never describe this sample as the whole period.
Current retained versions are used initially; historical reconstruction is deferred.

Bind the reviewed scope, counts, owner/revision, exact source versions/ranges/
hashes/date metadata and configuration in a body-free preview digest; recompute
under the existing shared read lock/search deadline before dispatch. Reuse one
existing answer call/USD 0.01 and its conservative ledger; no query embedding,
new purpose, table, dependency or worker is needed. Add retrospective instructions
and per-item source/category validation to the common transport, with date/source
metadata rechecked under the dispatch lock. Include the task contract in the
configuration hash, preserving historical attempt prices and closed protocols.
Every supported line must cite an allowed source and use a fixed category. Format
validation does not establish factual grounding or prove a Completed work label.
Stop/scope/account/revision changes reject stale output, and no automatic retry
repairs an invalid paid response. Synthetic verification grants no new real-provider
transmission or change to application AI permissions.


## 2026-10-17: Keep citation identity independent of disposable search indexes

New cited-answer and retrospective links include the retained version ID, field,
character bounds and SHA-256 of the exact excerpt. A local owner-scoped reader
checks these anchors against a bounded PostgreSQL substring (maximum 2,000
characters) under the existing shared owner lock and search timeout. It does not
rebuild historical indexes, retain additional bodies or dispatch a provider.
The hash checks excerpt identity; it is not proof that an answer is correct or
that a particular model previously cited this range.

Compare the anchored version with the current selection, retaining the original
version's title/event date and observation time. Show source deletion/unavailability
separately from local retention and offer an explicit current-record link. A
locally deleted record, missing version, invalid hash or another owner's version
returns a generic unavailable response; do not infer deletion versus access loss
or reveal replacement content. External-AI exclusion controls transmission,
not the owner's existing local version-history access. This does not grant any
new transmission consent or change current-only answer eligibility. On failed
rechecks, hide earlier reader data; use account/anchor-specific ephemeral query
keys and uncached HTTP requests. Existing unanchored links cannot recover their
original evidence after disposable IDs disappear. Historical question retrieval,
answer persistence and real-time push invalidation remain separate work.

## 2026-10-18: Use observed version cutoffs for the first historical question flow

Keep ordinary questions and retrospectives on current versions. Add an explicit
historical-question mode whose cutoff means the end of a day in Asia/Seoul.
Choose each record's latest retained observation by that cutoff, with version-ID
tie-breaking, before keyword matching. Do not infer an external past state from
event dates, provider timestamps or restored current selections. Late imports
are excluded rather than backdated. Surface the resulting observation gaps.

Use bounded local body matching and normalization (twenty candidates, five full
excerpts), without historical vectors or schema changes. Reuse the existing
answer caller, usage ledger/domain and one-call/USD 0.01 limit, adding a separate
historical eligibility check before reservation, at dispatch under the owner
lock and before exposing output. Current record/source AI permissions, allowed
record/version types and source-deletion exclusion also apply to old versions.
The reviewed digest and serialized request bind exact versions, ranges, hashes,
cutoff and observation/event metadata. Historical instructions join the answer
configuration hash; they do not reopen prior paid protocols or establish factual
quality. Retained citation anchors open the original version independently of
current search projections. Future historical semantic retrieval must be scoped
separately if actual usage shows keyword recall is insufficient.


## 2026-10-18: Organize Search by user intent, keeping AI requests explicit

Expose Search & ask and Review a period, with one question input and source/date
filters. Use existing local Passage retrieval for ordinary text searches and
keep records excluded from external AI visible locally. Only an expanded answer
action checks AI availability; one subsequent explicit consent/action runs the
existing integrated question flow. Hide algorithm selection and manual evidence
selection from the normal screen, retaining legacy URLs for compatibility.

Place exact phrase matching and an observed-version cutoff under Advanced
options. Exact phrase uses the existing record search and remains local only;
do not show a semantic answer action that could falsely imply respect for an
exact-match constraint. Historical cutoffs reuse the bounded keyword/history
flow with reviewed originals and separate consent. Period review reuses the
existing date preview and summary. No new ranking, vectors, provider settings,
backend API, dependency or database state is required.

Keep user-purpose/filter/page context in URLs, strip UI-only fields before API
requests and reset ephemeral paid work on changes or navigation. Create abort
controllers on click, isolate caches by account, and hide cached search bodies
when rechecks fail. A changed question, purpose or version must prevent later
paid stages; returning to the same search must not replay a call.


## 2026-10-18: Admit validated primary event text without widening old AI approvals

Keep Codex sessions and GitHub commits/discussions as PROJECT_EVENT. Share a
provider/payload-kind type gate across indexing, vector selection, current answer
egress, period review and historical answers. Reconstruct exact canonical source
ranges: Codex user/explicit final-answer messages, commit messages, discussion
titles/bodies. Exclude assistant unknown phases/commentary, commands/results,
patches, code-location/status metadata and missing-body placeholders from primary
evidence. Validate GitHub repository/object identity and complete canonical body
equality; revalidate bounded event ranges at egress under the owner policy lock.
The whole-version legacy AI helper rejects events. Full retained source text and
version citations remain available locally; logs/arbitrary events stay excluded.

Bump the disposable Passage projection and bind it into embedding storage config.
Old parents/vectors must not be treated as safe primary context. Existing accounts
need authenticated local backfill and separately approved new indexing estimates.
Old follow-change approvals cannot enroll work in the new configuration; old-config
queued runs pause on claim. Do not modify source/record permission or turn old
experimental approval into event indexing approval. No schema/model/dependency
change is needed. Period sampling prefers Codex final answers over questions.
Synthetic contract checks cannot establish actual model grounding; complete one
bounded cross-source acceptance pass before closing Phase 3.3.


## 2026-10-19: Recover recorded progress without requiring an unrecorded outcome

The owner clarified that a decision may happen outside the AI conversation.
Evaluate answers by what the retained evidence can establish: a recommendation,
comparison, request, explicit adoption, implementation or actual use are distinct
observations. Recover useful recorded facts and name the limits of the reviewed
scope. A missing final outcome does not invalidate an otherwise useful source
case or require endless discovery. This is an explicit owner clarification of
Phase 3.3 acceptance, not a claim that an actual choice or its reason was found.

Every returned factual claim still needs matching returned citations. Attribute
assistant advice/diagnosis to the recorded assistant; do not invent the owner's
personal motivation. A valid partial answer identifies the missing outcome;
unsupported details and omitted necessary citations remain failures. Preserve
earlier protocols, raw answers and the original grading of citation defects.

Implementation is pending: the current common answer contract has only supported
(complete answer with citations) and insufficient (empty citations). A reviewed
proposal is to add an explicit partial branch with citations and scoped unknowns,
retaining refusal for no useful direct evidence. API/parser/schema, current and
historical/period flows, UI labels and local regressions must be reconciled before
one separately approved real-model pass. This note changes no runtime behavior,
model, AI permission, ledger reservation or embedding space.

Implementation follow-up, 2026-10-19: the proposed `partial` status is now
implemented in the common strict output schema/parser, current/historical public
schemas and all answer displays. It requires the same 1–5 distinct allowed IDs
as `supported`; retrospective item format validation applies to both. Unknowns
remain bounded to selected evidence and advice is attributed to its author.
Natural-language grounding is still a real-model verification requirement, not
something the structural parser proves. Closed evaluation artifacts and existing
two-outcome preflight protocols are unchanged; a new partial-capable evaluation
scope is needed before any fresh paid run.

Preparation follow-up, 2026-10-19: `evidence-drafts-v3-partial` requires explicit
bounded `unconfirmed_aspects` for a partial expectation; non-partial cases cannot
carry that field's content. Their digest is checked with the spec/checklist and
answer configuration before execution. Expectations remain review-only and are
not model input. Old preparations require a new review; files, prior grading and
reservations remain untouched. Useful partial evidence is a prepared candidate,
not a waiver of missing-source, policy, grounding or automatic-retrieval checks.

## 2026-10-19: Select existing parents for one-shot indexing of reviewed evidence

An Entry-wide indexing selector would exceed the bounded source review of long
ChatGPT conversations. Add an optional exact existing Passage allowlist within
explicit Entry IDs, retaining the ordinary whole-record path. Reject follow-change
enrollment for this selector: future versions and other parents need a fresh
review rather than a persistent range policy or a schema migration. Reuse existing
per-slice durable jobs and dispatch checks. Omit the added selector for legacy
manifests to preserve hashes/replay; bind it into new manifest digests when used.

Source/record AI flags remain Entry-level. This feature narrows a particular
indexing run, not every possible egress from an enabled Entry. It grants no
permission, and complete selected parent text must be reviewed before a fresh
transmission approval. Rewriting excerpts as fake originals or indexing an entire
long record under an excerpt-only grant would lose provenance or expand scope.

## 2026-10-19: Prefer an explicitly requested commit within retrieved evidence

The rank-only five-parent recommendation dropped an actual implementation commit
already present at rank nine. For an explicit Korean/English commit request,
consider the first validated commit candidate immediately after the leading
parent, then keep the relative order of all other retrieved candidates. Recognize
common explicit exclusions. This is a narrow question-kind preference, not a
provider-diversity quota, model reranker or hidden reference answer. It uses no
project/source/Entry IDs or gold labels and does not change Semantic ranking.
Complete-text, deduplication, owner/current-policy/filter and byte/count limits
still apply; a preferred commit can be too large or irrelevant. Other evidence
kinds and general question decomposition remain unimplemented.

The common internal provider result also declares bounded unconfirmed requested
aspects before its status. Couple supported/insufficient to empty declarations
and partial to a nonempty list; reject disagreement without rewriting/retrying.
Keep the public answer shape unchanged. This catches declared contradictions,
not omitted unknowns or every conflict in free text. Semantic citation/completeness
review remains necessary. New schema/instructions invalidate old answer protocols;
existing embeddings and closed raw results remain unchanged.

## 2026-10-19: Preserve descriptive identity in bounded answer context

Ordinary answer inputs retain the exact approved text and add a small allowlist
of title, provider/source kind and GitHub repository/path already exposed by the
validated passage reader. Never forward the full imported payload or infer a
missing commit SHA. These fields identify a cited source; they are untrusted data
and do not prove adoption, testing, deployment or actual use. Source-kind plus a
matching commit message and original citation can identify an implementation
record without demanding a hash absent from the supplied evidence.

Recommendation byte accounting and dispatch share one representation; source
changes are rechecked before dispatch. Preparation hashes and review pages include
the added metadata. Embedding bodies/configuration are unchanged. The answer
configuration hash changes, so old closed approvals cannot authorize this input.
Evidence status follows the question's requested level: a reported adoption is
evidence of that report; independent code verification is a separate question.
Structural output validation still cannot establish semantic grounding or recall
completeness. The prepared model comparison is diagnostic, not a product model
selection or a completed Phase 3.3 acceptance result.


## 2026-10-19: Assemble ordinary answers from bounded claims and supplied-body quotes

Ordinary generation uses a single internal claim/evidence contract instead of a
separate free narrative and citation list. Validate every claimed source quote
against the exact body actually supplied; source metadata is identity, not proof.
Render only answer/progress claims plus declared unknowns, deriving status and
the distinct citations from that validated representation. Background alone cannot
produce a partial answer. Contradictions and malformed evidence fail closed after
usage settlement, without repairing the output or retrying. This establishes
structural consistency, not semantic entailment, correct evidence classification
or completeness; the unchanged v1 quality checklist still requires actual review.

The owner explicitly selected ordinary output 4096 as the local candidate after
the initial 512 capacity stop. Period/historical retain their narrative contract
and 512 cap, selected by explicit mode. Public answer fields stay unchanged;
per-request output limits govern reservations/usage, and a new config hash binds
all contracts/renderer versions. Old ledger entries and closed approvals are not
repriced or reused. The fixed insufficient notice supports Korean (Hangul question)
and English fallback only. No new locale system or model-quality guarantee added.
ANSWER_MODE stays off until separately authorized; actual schema/output-capacity
and semantic acceptance remain unverified. This local instruction authorizes no
paid provider calls and does not complete Phase 3.3.
