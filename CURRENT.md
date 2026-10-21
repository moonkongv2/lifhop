# lifhop Current Status

Last updated: 2026-10-22

## Current product slice

**Phase4.1 S1 collect-now and S2 GitHub scheduling/retry are implemented;
remaining owner verification is deferred.**
The owner confirmed the initial synthetic GitHub collection result in Sources
on2026-10-22. Repeat/unchanged, cancel and deletion-protection browser checks
remain pending; this confirmation does not close all S1 checks. The owner requested
continuing development while deferring those checks on2026-10-22.
Source registration, durable request/job tracking, an explicit one-shot worker,
collect/cancel controls and immutable batch receipts are available. S2 adds
paused-by-default schedule controls, explicit source-selected polling, bounded
retry/backoff and same-job manual retry. Pause/collection disable fences active
work; auth/permanent failures, partial batches and retry exhaustion pause schedules.
Collection still repeats bounded historical traversal; incremental reconciliation
and the Codex agent are not implemented. Overall Phase4.1 and live/A7 remain open.
See [S1/S2 setup and owner walkthrough](docs/guides/PHASE41_COLLECTION.md) and
[the remaining collection plan](docs/plans/PHASE41_COLLECTION_PLAN.md).

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
- Manual Codex/GitHub collectors and bounded GitHub S1/S2 collect-now and schedules.
  Apply migrations through `j82b7c69a408`; use the documented setup before use.
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
2. When the owner has the environment available, perform remaining S1 and S2
   browser checks using fictional sources in the
   [walkthrough](docs/guides/PHASE41_COLLECTION.md). They are deferred, not passed.
   Live selected-source acceptance remains open.
3. Present S2 for feedback before starting S3 bounded graph
   and mutable-record reconciliation, then S4 Codex agent/credentials and remaining
   acceptance. Keep GitHub and Codex in scope, including Mac offline/wake behavior.
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
