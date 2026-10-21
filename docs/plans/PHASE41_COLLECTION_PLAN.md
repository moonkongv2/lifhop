# Phase 4.1 — Incremental Codex and GitHub collection

Status: implementation authorized by the owner on2026-10-21. S1 collect-now and
S2 scheduling/retry and S3 incremental reconciliation are implemented with synthetic
verification. On2026-10-22
the owner deferred remaining S1 browser checks and requested S2 development;
initial synthetic collection was confirmed, other owner checks remain pending.
The owner then authorized committing S1/S2 (`a2db2bc`) and proceeding with S3.
See [implementation/setup and remaining limits](../guides/PHASE41_COLLECTION.md). S4–S5
and live-source acceptance remain unimplemented/unverified;
this is not overall Phase4.1 completion.

## Goal and boundaries

Implement [ROADMAP.md §4.1](../../ROADMAP.md): selected GitHub/Codex sources arrive
through collect-now and configurable schedules without duplicate records or
lost progress. Start with GitHub, then complete Codex; GitHub alone does not
complete 4.1. Phase3.3 remains conditionally closed with
[D01–D09](../evaluation/phase33/PHASE33_CONDITIONAL_EXIT_PLAN.md) carried forward.

This plan does not authorize personal-source reads/uploads, provider requests,
paid inference/embedding, enabling AI, installing background agents, or AWS
provisioning. Develop and verify first with synthetic sources and local HTTP
fixtures. Before live verification, document the exact repository/device,
selected content, destination, retention and finite request/storage budget for
owner approval. Existing expired execution grants remain closed.

Keep AI off and external-AI permission independent of collection. Reuse existing
projection, suppression, history and ownership checks. Do not start Phase3 quality
tuning, introduce queues/services speculatively, or provision Phase5 hosting.

## Existing implementation and gaps

| Existing code | Reuse | Missing capability |
| --- | --- | --- |
| `app/collectors/github.py`, `github_discussions.py`, `github_reader.py` | Selected source filters, pinned heads, bounded reads, private previews, rate-limit handling | Persistent incremental discovery and unattended execution |
| `app/collectors/codex.py`, `reader.py` | Stable device/turn IDs, read-only snapshots, compatibility guards, partial/deferred outcomes | Scheduled Mac agent, reconnect/catch-up and source-bound credentials |
| `app/collectors/client.py` | Manifest validation, checkpoint binding, replay of durable receipts | Interactive password login currently prevents unattended use |
| `app/api/collection_runs.py`, `app/services/collection_runs.py` | Immutable per-batch manifests, transactional upsert/receipt, source policy and suppression checks | Scheduler jobs, durable leases and scoped collector authentication |
| `app/models/history.py`, Sources UI | Source policy, versions, deletion protection, history coverage | Schedule/configuration and current incremental status |

`CollectionRun` is a sealed batch, not a continuously mutable scheduler job.
Its derived five-minute disconnected status and the local directory lock are
not cross-worker leases. Existing import/embedding workers do not collect sources.

## Proposed smallest architecture

Use the existing PostgreSQL database and a bounded polling worker. No new broker,
Redis, cloud scheduler or generic plugin framework. Schema names below are
provisional; implementation requires Alembic migrations and upgrade tests.

1. A source-bound subscription stores owner, provider, exact scope (`repo:<id>`
   or `mac:<device UUID>`), selected filters, configuration revision, schedule
   enabled flag, interval, next due time, committed cursor and reconciliation
   progress. Configuration changes create a new revision; old work cannot
   advance the new revision's cursor. New subscriptions start paused.
2. A durable job stores subscription/revision, manual request ID or scheduled
   slot, preparation/batch references, attempt count, retry time, lease owner,
   lease expiry and fencing generation. Database uniqueness deduplicates manual
   request IDs and scheduled slots. Concurrent manual/scheduled requests coalesce
   into the current source job and return its ID; do not build a catch-up queue
   for every missed interval.
3. A scoped collector credential stores a hash, owner/source/device binding,
   expiry and revocation state. Display the secret once; keep it in private
   local storage, never in command arguments, bundles, logs or repository files.
   Separate this lifhop upload credential from the GitHub provider credential.
   GitHub workers receive a narrowly scoped read credential through runtime
   secret configuration; do not store provider secrets as plaintext in the DB.

Claim jobs in short DB transactions, using row locking and at most one active
lease per owner/provider/scope. Never hold a DB lock during provider calls.
Every write, receipt, cursor promotion and finish verifies the current lease
generation, configuration revision and source policy transactionally. A timed-out
worker may still finish a network request, but cannot commit after takeover.
Persist a batch/checkpoint before acknowledging work. Resume the same frozen
batch and manifest UUID after an uncertain response; changed payloads require a
new batch. Reuse the existing upsert/receipt transaction through a shared service
rather than duplicating ingestion rules.

Include existing manual backfill uploads in the source concurrency boundary:
reject conflicting writes with a recoverable conflict response, and do not let
an older prepared snapshot replace a newer incremental version. Preserve
historical versions; resume/reprepare explicitly after a revision conflict.

### Authentication and lifecycle

Owner JWTs manage subscription configuration, collect-now and credential
issuance/revocation. Collector credentials may claim/read/heartbeat/ingest only
their exact source's jobs/runs; they cannot access account management, arbitrary
Entries, another source, or AI routes. Bind runs server-side to the authenticated
principal and job, never accept an owner override in the payload. Preserve the
existing owner-authenticated manual collector flow.

Pause stops future claims and invalidates the current lease. Disabling collection
also blocks writes through the existing source policy. Disconnect revokes the
credential, cancels pending work and fences in-flight uploads; it retains archive
data. Deletion uses existing suppression/purge rules and cannot be reversed by a
late upload. Resuming collection is explicit and does not restore revoked tokens
or enable external AI. Rotation invalidates the old credential.

### Runtime and bounded defaults

GitHub collection runs in a server-side worker independently of the Mac agent.
Initially demonstrate separate processes against synthetic sources; this proves
the runtime boundary, not deployed cloud availability. Hosting remains Phase5.
Codex reads run only on the selected Mac, then upload over authenticated HTTPS
(loopback HTTP allowed for local tests). Collect-now for an offline Mac becomes
one pending request; the server never reads its local files.

Proposed configurable defaults: GitHub every 15 minutes, Codex every 5 minutes,
minimum interval 60 seconds. Reuse existing request/page/byte/time limits; do not
raise them silently. Lease heartbeats and expiry must tolerate bounded requests;
validate takeover with an injected clock. Respect provider retry times and use
bounded exponential backoff with jitter, at most three automatic transient
retries per job. Authorization/configuration failures pause for owner action;
retry exhaustion remains visible and requires explicit retry. Catch-up is one
resumable bounded job, never an unbounded burst after sleep. Define private spool
quota/cleanup before unattended operation; retain failed batches until expiry
or explicit cleanup and report quota exhaustion without dropping progress.

## Incremental discovery and cursor rules

### GitHub

- Resolve configured repository identity and selected branch heads afresh per
  discovery cycle. Pin those heads for the cycle. Traverse reachable commits
  against known graph/frontiers, not commit dates: a newly reachable old commit
  must be discovered. Persist bounded unfinished traversal across jobs; a known
  SHA is a stopping frontier only when its ancestry coverage is established.
- Read selected documents at changed pinned heads and retain existing SHA/path
  identities. Track the currently observed head separately from historical
  documents. Force pushes, renamed/deleted refs and unavailable objects must
  not erase archived records or falsely advance completed coverage.
- Treat PRs/issues/comments/reviews as mutable records using their stable IDs
  and payload digests. Combine overlapping updated-item discovery where the
  existing reader supports it with a persisted rotating reconciliation of older
  selected records. New comments on old threads must be discoverable. Bound each
  cycle and expose reconciliation coverage/age; do not scan all history on every
  poll or claim that a timestamp watermark guarantees completeness.
- Keep provider transport caches cycle-aware: a prior preparation's cached head
  or list response cannot establish freshness for a new cycle.
- Store progress per branch/content family. Advance the completed cursor only
  after its traversal and durable receipts are complete. Preserve partial work
  separately; blocked/failed items and request limits cannot silently close a
  coverage gap. History backfill and current incremental success remain separate.

### Codex

- Preserve stable device UUID and explicit CWD/thread selection. Do not broaden
  to all accessible sessions automatically. Persist inventory/reconciliation
  state and revisit selected old threads: new turns and partial-to-complete
  upgrades cannot depend solely on a last-modified timestamp.
- Reuse disposable read-only snapshots and supported CLI/parser guards. Active,
  changing, unsupported or timed-out sessions remain deferred with a reason;
  a later bounded cycle revisits them. Never invoke resume/start/model-generation
  operations to read history or copy auth/configuration secrets into snapshots.
- Persist local job/bundle/checkpoint state before upload. After sleep, restart
  or network loss, reconcile server receipts before resending; then discover
  new work. Fence stale local attempts and preserve newer stored versions.
- Add an explicit start/stop local agent first. Package Mac startup integration
  only after its lifecycle tests pass, with owner-controlled installation and
  uninstall instructions. Source/device selection and token remain private.

For both providers, missing permission, timeout, rate limit and unavailable
records are availability/error states, never proof of deletion. An unchanged
successful check may update last checked/success without creating empty records.

## Delivery sequence and reviewable checkpoints

| Slice | Observable result | Required checks before the next slice |
| --- | --- | --- |
| S1 GitHub collect-now | Owner selects a synthetic repository, starts collection in Sources and sees resulting Entries and batch receipts | Migration upgrade; owner isolation; unchanged repeat adds no Entry/version; changed content preserves history; concurrent backfill protection |
| S2 GitHub schedule and recovery | Enable a schedule, observe new synthetic content without clicking, pause/resume, and recover from worker restart | Unique job claims, duplicate delivery, uncertain ACK, stale lease, config change, rate limit, auth failure, retry exhaustion and suppression races |
| S3 GitHub reconciliation | Old newly reachable commits, updated documents and comments on old discussions appear over bounded cycles | Force push/ref change; mutable edits; pagination interruption; fresh-cache behavior; visible pending coverage and no false deletion |
| S4 Codex agent and credentials | Selected synthetic device uploads on schedule/collect-now and catches up after offline/restart | Credential isolation/expiry/revoke/rotation; local spool resume/quota; old thread append; partial upgrade; parser mismatch; read-only RPC guard |
| S5 Integrated acceptance | Both sources show controls/status and satisfy the acceptance matrix below | Browser checks, relevant backend suites, frontend lint/test/build, documented owner verification and remaining limitations |

Each slice includes its minimal UI, API schemas, migrations and behavior tests;
do not defer all visible behavior to S5. Scope credentials and fencing must land
before enabling unattended uploads. Commit at each passing, reviewable boundary,
for example `feat: add GitHub collect-now jobs`, then
`feat: schedule and resume GitHub collection`. Do not combine unrelated tuning.

The2026-10-22 owner deferral permits S2 development before the remaining S1
walkthrough. It preserves all open owner/live acceptance items; synthetic passes
do not close them. S2 uses explicitly started source-selected polling (no daemon
installation), paused-by-default schedules, four total attempts per job and
seven-day expiry for nonrecoverable terminal caches. Failed/recoverable caches
remain until operator action, bounded by the source-local spool quota.

S3 keeps legacy jobs on their frozen backfill path; new jobs use persisted
parent-SHA enter/exit frames and stop only at covered ancestry. Per cycle:50 graph
steps with branch rotation, one rotating inventory page plus one recent page,
at most three oldest/unchecked threads and three stream pages per thread. Reserve
one slot for old-thread reconciliation even when new roots remain pending.
Progress promotes only after successful durable receipts under the current lease.
Discussion selection is separate and disabled by default; changes fence active
work, pause scheduling and reset coverage/times under a new revision. Source
identity and branch/document configuration remain immutable in this UI.
Pending coverage/age is visible separately from a successful bounded cycle.

## Acceptance and verification

Automated tests use deterministic clocks, synthetic provider fixtures and two
worker processes/DB sessions for races. HTTP mocks alone cannot prove DB locking.
Run migrations on a disposable DB and preserve current collector/run/source
policy/history/suppression tests. Frontend changes require relevant tests, lint
and build. No test should call a live provider or inference API by default.

- A1: Both sources support collect-now and enabled schedules with exact selected
  scope; repeated unchanged runs add no duplicate Entries or versions.
- A2: Restart/timeout after DB commit but before ACK recovers via receipts without
  loss; overlapping jobs and stale workers cannot regress current content.
- A3: GitHub discovery includes old newly reachable commits, mutable documents
  and old-thread discussion updates over bounded resumable cycles.
- A4: Codex offline requests, wake/reconnect, active-session deferral and later
  completed turns recover without resetting device identity or broadening scope.
- A5: Pause, disabled collection, disconnect/revoke, owner isolation and deletion
  hold during in-flight work. Secrets and personal bodies never enter logs.
- A6: Sources shows enabled/paused/offline/error, current job, last check/success,
  next attempt, pending/partial counts and history versus incremental coverage.
  Existing indexing state remains separately represented; ingestion success
  cannot imply embeddings or answer-quality success.
- A7: Demonstrate GitHub progress while the Mac agent is stopped. Separately
  perform owner-observed Mac sleep/wake and selected live-source acceptance
  within a newly approved finite scope; record what remains unverified.

Synthetic success proves application behavior, not real-provider completeness
or Mac sleep behavior. Do not mark 4.1 fully accepted if A7 remains unverified;
report implementation/automated verification separately and leave that gate open.
Review D01–D09 at the overall Phase4 exit, without reopening paid Phase3 trials.

## Risks, follow-up and completion boundary

The main risks are stale-worker writes, incompatible immutable manifests,
late-discovered historical changes, credential scope escape, and spool growth.
The fencing/revision rules, separate batch/job state, bounded reconciliation,
negative authorization tests and quotas above address them before unattended use.
Freeze concrete request/retention/lease defaults in the corresponding slice after
fixture measurements rather than inventing performance claims in this plan.

Basic retries, ownership, durable resume, coverage visibility and fencing are
4.1 requirements. Phase4.2 expands operational diagnostics, failure isolation and
verified recovery gaps across import/index queues; introduce an outbox/redrive
only if the actual DB/queue failure path requires it. No collection queue is
introduced by this proposal. Phase5 owns deployment/budget/backup verification.

Before 4.1 closure, update CURRENT/README with actual capabilities and unmet
checks, record accepted durable architecture decisions in DECISIONS, and provide
URLs/commands for owner verification without embedding credentials. This plan
alone changes no completion checkboxes or architecture implementation status.
