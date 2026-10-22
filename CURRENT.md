# lifhop Current Status

Last updated: 2026-10-22

## Current product slice

**Phase4.2: Sources lease-expiry visibility, recovery/indexing status and durable
import reconciliation. Phase4 exit review preserves owner/browser/live/A7 gates.**
The owner confirmed the initial synthetic GitHub collection result in Sources
on2026-10-22. Repeat/unchanged, cancel and deletion-protection browser checks
remain pending; this confirmation does not close all S1 checks. The owner requested
continuing development while deferring those checks on2026-10-22.
Source registration, durable request/job tracking, an explicit one-shot worker,
collect/cancel controls and immutable batch receipts are available. S2 adds
paused-by-default schedule controls, explicit source-selected polling, bounded
retry/backoff and same-job manual retry. Pause/collection disable fences active
work; auth/permanent failures, partial batches and retry exhaustion pause schedules.
S3 now walks persisted parent-SHA frontiers, refreshes changed head documents and
optionally rotates through PR/issue/comment/review pages. Sources shows observed/
completed/document SHA, pending graph/thread work and reconciliation age. Existing
sources keep discussions disabled until explicitly selected. Selection changes
fence work, pause scheduling and start a new revision with cleared coverage/times.
Legacy pre-S3 jobs retain their original frozen backfill path. After S3 commit
`4fad0e6`, the owner authorized S4 while deferring direct checks. S4 adds exact
Mac/CWD/thread selection, paused schedules/collect-now, source-scoped opaque
credentials and a private local agent using leased HTTP receipts. The agent
revisits old threads and catches up after reconnect without an owner JWT/DB/AWS
secret. Revocation/expiry/selection changes fence uploads. No daemon is installed.
S4 was committed as `233ae60` before owner-authorized S5. Integrated tests verify
GitHub process progress with the Codex agent stopped, reconnect/replay and source
failure/revocation isolation. Sources now labels shared receipts as collection
batches instead of describing scheduled work as manual-only historical backfills.
Overall Phase4.1 and owner/live acceptance remain open.
S5 was committed as `01e7361`. The owner authorized the first Phase4.2 slice:
Sources now distinguishes queued/retrying/failed/partial work, offline contact,
paused schedules and unavailable/disabled collection policy, with next actions.
AI indexing runs/counts are shown separately through an existing read-only API;
viewing/reloading this status starts no AI work. That UI slice is committed as
`0d114ad`. The next authorized slice now reconciles durable pending/stale import
jobs when SQS notification is missing, empty or unavailable, retaining live owner
locks and bounded attempts. Send-response loss cannot overwrite progressed work;
ACK loss leaves the worker alive and later terminal delivery is a no-op. Existing
workers only; no new schema/queue/service or real AWS request.
Import recovery is committed as `72992fb`. The next slice exposes the existing
collection lease deadline in owner-scoped job responses and Sources. Expired
reported RUNNING leases show check/restart guidance, clear on renewal and never
auto-cancel or declare process death. The server still decides takeover. The
[Phase4 exit review](docs/plans/PHASE4_EXIT_REVIEW.md) records evidence and unchanged
D01–D09/open owner/live gates; Phase4 is not closed and Phase5 has not started.
See [S1–S3 setup and owner walkthrough](docs/guides/PHASE41_COLLECTION.md) and
[S4 agent setup](docs/guides/CODEX_AGENT.md),
[S5 evidence and deferred walkthrough](docs/guides/PHASE41_ACCEPTANCE.md), plus
[the remaining collection plan](docs/plans/PHASE41_COLLECTION_PLAN.md).
Current setup/state meanings: [collection recovery](docs/guides/COLLECTION_RECOVERY.md).
Import fault behavior and local verification: [import recovery](docs/guides/IMPORT_RECOVERY.md).

Maintenance scope: [efficiency/cleanup plan](docs/plans/EFFICIENCY_CLEANUP_PLAN.md), authorized
on 2026-10-21. Work A separates active guidance from history and removes unused
starter files. Root documentation classification is complete; see the
[documentation map](docs/README.md). B–E are not implemented; this does not change product gates.

Phase3.3 is **conditionally closed by the owner on 2026-10-21** for the personal
alpha. CE1–CE4 are complete; C3/C4 full acceptance remains unmet and C5/C6 record
conditional scope acceptance. [D01–D09](docs/evaluation/phase33/PHASE33_CONDITIONAL_EXIT_PLAN.md) retain
citation errors, retrieval/answer omissions, follow-up/integration/restore/performance
and evaluation gaps, unresolved accounting and error usability work.
Existing failed/unverified judgments and closed paid approvals remain unchanged.

## What works now

- Authenticated owner-scoped manual records, Markdown/ChatGPT ZIP import, original
  artifacts, import progress/retry and local PostgreSQL queue/SeaweedFS storage.
  Identical Markdown identities upsert; prior duplicate rows are not merged.
- Exact phrase and local Passage search, source/date filters, paginated archive,
  Codex session and GitHub repository/discussion readers, annotations and history.
- Canonical source ingestion with retained observations, freshness/completeness
  guards, current versions, deletion suppression and separate collection/AI policy.
  Missing/equal source clocks still require explicit current-version review.
- Manual collectors, bounded GitHub S1–S3 collection/reconciliation and explicit
  source-scoped S4 Codex agent. Apply migrations through `l04d9e81c620` before use.
  Collection does not enroll sources in external AI.
- Private evaluation tooling; policy-bound pgvector storage, bounded indexing jobs
  and optional Semantic search. Old projection configurations require explicit local
  backfill and separately authorized embedding work; old grants do not expand scope.
- Cited selected-evidence answers, period/historical views, and owner-scoped saved
  conversations with bounded contextual follow-ups. Reopening is local and makes no
  AI call. Stable version/range/hash citations and source deletion gates remain.

## Next

1. Review maintenance A's document/file changes; then continue B search and C saved
   conversation read improvements in independently verified slices. D/E are related
   follow-ups, not new prerequisites for all Phase4 development.
2. When the owner has the environment available, perform remaining S1–S4
   browser checks using fictional sources in the
   [GitHub](docs/guides/PHASE41_COLLECTION.md) and [Codex](docs/guides/CODEX_AGENT.md)
   walkthroughs. They are deferred, not passed; live-source acceptance remains open.
3. Review Sources/import recovery and the Phase4 exit matrix, then select a finite
   remaining verification/operational slice. D01–D09 remain open; no AI-use or
   deployment transition is implied. Real queue/IAM/network/DLQ, worker supervision
   and persistent live-lock recovery remain unverified. Owner Mac sleep/wake/live
   acceptance stays pending; no personal collection or background installation.
4. Revisit D01–D09 at Phase4 exit and explicitly agree remaining Phase5 use scope.
   Private deployment, backup/restore and daily-use acceptance remain later work.

## Verification and execution boundaries

- Prior S1 implementation record: backend **962 passed**, frontend **207 passed**,
  lint/build passed with a bundle-size warning. These are earlier checks, not tests
  rerun by the efficiency audit. Details: [S1 verification](docs/guides/PHASE41_COLLECTION.md).
- The2026-10-22 worker startup fix loads the repository-root `.env` independently
  of the working directory. Backend **963 passed**, including its regression test;
  worker `--help` also succeeded from outside the repository.
- S2 targeted PostgreSQL/HTTP/worker tests: **23 passed**; migration upgrade is
  exercised in a fresh disposable schema. Includes a separate synthetic worker
  process and restarted process, concurrent schedule ticks and lease claims,
  rate-limit/backoff/exhaustion, pause/auth recovery, deletion races and spool bounds.
  Full backend **978 passed** (81.73s), full frontend **209 passed**;
  collection tests **4 passed**; ESLint/build and diff checks passed (existing
  about505KiB chunk warning). Initial sandboxed DB access was blocked; rerunning
  with local DB access succeeded. One new test initially omitted a required
  source-policy field; corrected before these final passing runs. The application
  database was not migrated; apply the documented upgrade before running this UI.
- S1/S2 were committed as `a2db2bc` before the owner-authorized S3 implementation.
  S3 final full backend **995 passed** (84.56s), GitHub-focused **82 passed**,
  frontend **210 passed**; collection UI
  **5 passed**, ESLint/build passed (existing about507KiB chunk warning).
  Synthetic checks cover old newly reachable commits, cross-job/multi-branch
  graph traversal, changed documents/refs, old-thread/comment/review edits,
  child pagination/rate-limit resume, partial/cancelled cursor protection,
  per-family receipt counts and frozen replay. Old-thread reconciliation keeps
  a slot while discovery has a backlog. Migration upgrade/downgrade preserves legacy jobs.
  The two-revision fictional owner walkthrough is tested. Initial GitHub-focused
  checks exposed five old full-traversal expectations (updated for S3/legacy
  compatibility) and three mixed-batch receipt errors (fixed). No live source,
  inference/embedding or AWS request, application DB migration or owner browser
  acceptance was performed. Diff checks passed.
- S4 source/agent tests **22 passed**, including independent local API/agent
  processes, frozen replay/uncertain ACK, unchanged-mtime appends, active-session
  deferral/complete candidates, token scope/expiry/rotation, private init and slow
  snapshot pause fencing. Full frontend **215 passed**, ESLint/build passed
  (existing about515KiB chunk warning). One UI test initially stringified an
  absent GET body; its assertion was corrected. Final full backend **1017 passed**
  (90.33s). Fresh-schema Alembic upgrade, AST/diff and local-link checks passed.
  The application DB, real Codex home and startup services were not changed.
- S5 integrated backend **3 passed**; final full backend **1020 passed** (94.52s).
  Relevant frontend **17 passed**, full frontend **216 passed**; ESLint/build,
  Python AST, documentation-link and diff checks passed (existing about515KiB
  chunk warning). Initial new fixtures omitted a lease worker ID/due time and
  GitHub incremental metadata; corrected before the final passing runs. The old
  manual-only UI assertion was updated with the corrected product text. No
  application DB migration, live provider, real browser, Mac sleep/wake or
  startup service was exercised. Evidence/remaining gates are in the
  [S5 acceptance guide](docs/guides/PHASE41_ACCEPTANCE.md).
- Phase4.2 first slice: related backend collection/indexing suites **48 passed**
  (8.07s); focused frontend **25 passed**, full frontend **225 passed**. ESLint
  and TypeScript/Vite build passed (existing chunk warning, now about521KiB).
  Initial build found a union-type property access, corrected with a property
  guard before the final passing checks. Diff/local-document links passed.
  Checks and remaining limits are recorded in the
  [recovery guide](docs/guides/COLLECTION_RECOVERY.md). The backend is unchanged;
  the earlier full-backend result above was not rerun for this frontend slice.
- Phase4.2 import recovery: focused queue/import suites **36 passed** before the
  final infrastructure-retry regression was added. Final full backend **1032
  passed** (95.82s), including all12 new recovery cases; full frontend **225
  passed**. AST/local-link/diff checks passed. All SQS/storage faults are mocked;
  no application DB migration, real AWS/personal source or browser verification.
  The prior UI lint/build result is unchanged; frontend code was not edited here.
- Phase4.2 lease visibility/exit review: related backend **50 passed**, full
  backend **1034 passed** (94.46s); full frontend **227 passed**, final recovery
  component **9 passed**. ESLint/build passed (existing about522KiB chunk warning).
  Generated API types, AST/local-link/diff checks passed. No migration, owner
  browser, live source, paid call or AWS request. The exit review leaves Phase4
  open; lease expiry is a last-response/browser-clock observation, not death proof.
- The independent audit passed frontend ESLint/type checks, Python AST parsing of
  287 files and diff checks. It did not run tests, migrations, live providers or
  performance measurements. Maintenance results belong in the
  [maintenance plan](docs/plans/EFFICIENCY_CLEANUP_PLAN.md).
- AI answers remain off by default. Collection/AI permissions, consent, current
  owner/version/deletion checks, Stop/replay and shared-budget protections remain.
  Three prior uncertain reservations totaling USD 0.006801 remain conservative;
  do not manually settle them without evidence or reopen closed paid approvals.
- No new personal ingestion, external transmission, paid inference/embedding,
  permission expansion or AWS resources follow from this status update.
  Isolated synthetic verification is distinct from source/provider acceptance.

## Known limitations

- Sources indexing status shows at most the latest50 owner runs, matched by exact
  provider/scope; it is not a full index-coverage audit. Completed runs may contain
  failed/blocked jobs. Sources shows the last reported lease deadline with a
  browser-clock warning, not a process-liveness guarantee; cached data and clock
  skew can mislead. Detailed indexing recovery and queue/stuck
  job supervision remain later Phase4.2 work; direct browser checks are deferred.
- Import reconciliation probes up to50 owners, one oldest eligible row per owner.
  AWS pending grace is60s before receive; empty/failed receive has no grace.
  RUNNING eligibility is start older than `import_max_seconds + 60` (default180s)
  or absent start; a live import lock is never stolen. The existing worker and DB
  must be healthy. More than50 blocked owners, real SQS/DLQ/IAM and a permanently
  hung live process require further deployment/capacity work. Terminal jobs remain
  explicit owner retry; this does not implement worker supervision.

- Real answer quality is bounded and imperfect: exact quotes do not prove semantic
  support or complete coverage. Preserve rejected output and failed retrieval.
  Broader source/language/life-record evaluation and personal follow-up acceptance
  remain incomplete; the original diverse evaluation-set scope is not fully met.
- Exact phrase is literal case-insensitive substring matching; Passages is local
  lexical retrieval. Neither translates queries or extracts attachments. Semantic
  and generated answers are separate opt-in flows. Passage projection has 8 MiB
  input/512-passage bounds and reports partial/unverifiable mappings.
- Corpus-scale SQL/vector performance, long conversation reads, pool/lock behavior
  and deployment capacity/cost remain unmeasured. Offset pages can shift during
  collection/deletion; dates use fixed Asia/Seoul initially.
- Retained repository/session counts are not complete source coverage. Document
  snapshots need not be current GitHub HEAD; unknown dates/order/phases remain
  explicit. Live nonempty/private/org discussion access, token expiry and broader
  source compatibility remain unverified. Session/discussion-wide controls are absent.
- Earlier source/account/apply checkpoints still need reconciliation. Owner Codex
  reading screens and synthetic discussion browsing were confirmed; that does not
  establish all-source backfill or live collection acceptance. Phase1.2 initial and
  large-ZIP owner checks were confirmed; other old UI/preview checks retain their
  individual scope in the [historical record](docs/history/CURRENT_HISTORY_20261021.md).
- Remote CI, Safari/Firefox and actual mobile-device validation remain unverified.
  Frontend automated checks use synthetic responses; UI is light theme. Browser
  access tokens remain in localStorage for development; internet authentication
  needs the later deployment review.
- ChatGPT Web extension remains experimental/unreliable. Attachments have no PDF/OCR
  extraction. Textless ChatGPT branches can produce partial imports; progress is
  committed in batches and there is no hard wall-clock process watchdog.
- Earlier artifact/result links cannot be reconstructed without evidence. Original
  purge needs the worker; issued download URLs may last up to 10 minutes, and
  attachment purge waits 11 minutes. Unattributed old uploads cannot be safely purged.
- Source deletion confirmation is manual until reconciliation. SQS enqueue/commit
  recovery, redrive/DLQ, worker supervision, AWS version deletion/IAM, policy/deletion
  journaling, backup expiry and restore remain deployment follow-up. Restore must
  reapply current denials and the deletion ledger.
- S2 polling requires an explicitly started worker and one stable private spool
  per source/database. Four attempts per job; failed caches remain for explicit
  retry and may require manual cleanup. Nonrecoverable terminal caches expire
  after seven days on a later claimed job. Quota is local to that spool root;
  no hosted supervision or global disk quota is implemented.
- S3 successful cycles may leave graph/thread work pending. Mutable snapshots
  are not atomic and reconciliation lag grows with corpus size. A missing ref/
  record is not proof of deletion. Large diffs/document trees retain existing
  per-run bounds; PR membership is limited to250 commits. Resource/partial/auth
  failures pause rather than falsely closing coverage. Old revision cursor
  metadata and archive versions remain; live completeness/capacity are unverified.
- S4 uses explicit foreground operation and one private spool per source revision.
  Inventory is limited to10000 files/30s; cycles rotate1–10 threads (default5).
  Offsets are reconciliation positions, not completeness proof. Deferred-only
  work stays eligible for later cycles; permanent/blocked failures pause. Equal/
  missing source clocks retain complete candidates for explicit version review.
  CWD selection/sanitization is enforced by the trusted local agent, not attested
  by the server. Live sleep/wake, startup packaging/installation, corpus capacity
  and abrupt-death temporary snapshot cleanup remain unverified/later work.
- Prior local validation misdirected cleanup; restored originals and the remaining
  two unverified September artifact originals are documented in the preserved
  [incident](docs/history/CURRENT_HISTORY_20261021.md#local-validation-incident).

## Evidence and history

- [Conditional acceptance and carryovers](docs/evaluation/phase33/PHASE33_CONDITIONAL_EXIT_PLAN.md),
  [protection/accounting evidence](docs/evaluation/phase33/PHASE33_OPERATIONAL_EVIDENCE.md),
  [completion record](docs/evaluation/phase33/PHASE33_COMPLETION_PLAN.md).
- [Usage and saved conversations](docs/guides/UNIFIED_ANSWER.md), [history/purge policy](docs/guides/HISTORY.md),
  [evaluation](docs/guides/EVALUATION.md), [architecture decisions](DECISIONS.md).
- [Complete pre-cleanup status snapshot](docs/history/CURRENT_HISTORY_20261021.md): retains past tests, incidents, approvals and failed results with updated links.
  The [immutable original](docs/history/CURRENT_20261021.original.txt) preserves the pre-move snapshot bytes.
  Historical “next” instructions are not current execution authorization.
- The private release targets external-device access, both scheduled collectors and
  a combined USD 20/month budget. See [ROADMAP.md](ROADMAP.md) for acceptance, not the
  historical learning sequence at tag `learning-complete-f3`.
