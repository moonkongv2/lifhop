# Phase4 exit review — implementation evidence and open gates

Reviewed on2026-10-22 after import recovery commit `72992fb`.
Lease visibility is committed as `8287085`; a subsequent
[worker reconnect slice](../guides/WORKER_RECOVERY.md) adds bounded DB reconnects
to the existing import/GitHub loops without installing a process supervisor.
**Phase4 is not accepted/closed.** The owner authorized continued implementation
while direct checks are deferred. This review is repository evidence, not owner
acceptance, live-provider validation, startup installation or approval to deploy.

## Recovery gap addressed in this slice

The collection API did not expose its already persisted lease expiry, so Sources
could label an abandoned RUNNING job as Collecting without recovery context.
`JobResponse.lease_until` now exposes only the deadline, without worker identity
or collector credential IDs. Both GitHub and Codex use it in Sources.

While a running job's last reported deadline is past the browser clock, Sources
shows **Reported lease expired — check worker**, the deadline and advice to check/
restart the selected worker or agent with its existing private settings/spool.
The local clock refreshes every5 seconds while a running lease is shown. A later
deadline clears the warning. Expired timestamps on cancelled/terminal jobs do not
trigger it. Unknown/disabled source permissions retain priority.

This is a report based on the latest response, not proof a process died: cached
responses and browser clock skew can mislead. Refresh status; server lease, policy,
revision and attempt checks decide takeover. Reading status never cancels work,
creates another job, claims a lease or enables AI. No schema migration is needed.

Regression evidence: `tests/test_collection_integration.py` checks queued/null,
live and expired deadlines for both providers, read-only status, rejection of
old-worker writes and same-job/new-generation takeover. The frontend recovery
test advances time on an open page, then supplies renewal and cancellation.

Executed on2026-10-22: related backend **50 passed** (8.45s); final full backend
**1034 passed** (94.46s); focused frontend **10 passed**, full frontend **227
passed**. After final warning wording, the recovery component's **9 tests passed**
again. ESLint and TypeScript/Vite build passed (existing about522KiB chunk warning).
API types were regenerated from local OpenAPI. AST, diff and local-link checks
passed. No test failed. There was no real browser/live source/AWS/paid AI call,
application DB migration or startup installation.

## Phase4 requirements against repository evidence

| Requirement | Automated evidence | Remaining acceptance |
| --- | --- | --- |
| Both selected providers, collect-now and schedules | S1–S5 provider/integration suites; scoped devices/repos, paused defaults and duplicate-free replay | Deferred owner browser checks and selected live sources |
| GitHub progresses while Codex is stopped | Separate synthetic GitHub worker processes, offline Codex pending job, later catch-up | Actual Mac sleep/wake and independent deployed GitHub runtime; A7 stays open |
| Old history and mutable records | Parent graph/frontiers, head documents, old comments/reviews and old Codex turns with unchanged mtime | Live corpus completeness, permissions and format compatibility |
| Interrupted/overlapping/stale work | Frozen receipt replay, takeover/generation fences, bounded attempts, lease visibility and fault-tested worker DB reconnects | Real network/driver behavior, process supervision and persistent live-lock hangs; no automatic forced termination |
| Expired/revoked authorization, pause and deletion | Credential expiry/rotation/revoke, in-flight policy/deletion tests and provider isolation | Owner/live walkthrough; no permission expansion follows from tests |
| DB commit before queue send, duplicate delivery | Import notification reconciliation, send-race guard and lost ACK replay with fake SQS/storage | Real SQS/IAM/network, retention/DLQ/redrive and deployed failure injection |
| Status, coverage, indexing and next action | Sources status/recovery components, read-only exact-scope indexing runs, bounded progress/batch receipts | Browser/layout review; indexing list is latest50 runs, not full coverage |

References: [S5 matrix](../guides/PHASE41_ACCEPTANCE.md),
[Sources recovery](../guides/COLLECTION_RECOVERY.md),
[import recovery](../guides/IMPORT_RECOVERY.md).

## D01–D09 recheck

The [accepted conditional carryovers](../evaluation/phase33/PHASE33_CONDITIONAL_EXIT_PLAN.md)
retain their original failures and acceptance targets. This review resolves none
of them and reopens no paid protocol.

| Carryover | Current disposition |
| --- | --- |
| D01 citation generation; D02 evidence selection; D03 omissions/classification | Existing known failures retained. Collection/recovery tests do not establish answer quality. Review before increasing AI-answer use. |
| D04 personal follow-ups; D05 remaining integrated answer paths | Remain unmeasured. Any new live/personal/paid trial requires its own finite approved scope. |
| D06 personal answer restore/performance | Synthetic recovery is separate from personal DB restart, long histories and end-to-end latency; those remain open. |
| D07 evaluation set/seed gaps | Draft/expected evidence review and original diverse evaluation scope remain incomplete. |
| D08 accounting | Three old uncertain reservations totaling USD0.006801 remain conservatively reserved. No ledger settlement or provider request was performed. |
| D09 error usability | Sources collection recovery guidance improved. This is not full AI-error usability acceptance or permission to enable AI. |

## Deferred owner check and next boundary

Use the [local synthetic setup](../guides/COLLECTION_RECOVERY.md) and open
<http://localhost:5173/sources>. For a known synthetic worker interruption, keep
the page open past the displayed lease deadline: expect the reported-expiry
warning after the next5-second local tick, then ordinary status after recovery.
Reuse the original scope and spool. Do not delete recovery files or alter real
application rows to manufacture a stale lease; the automated tests cover that
case without personal sources. A cancelled job must never be labelled expired.

For deterministic synthetic verification without timing a process interruption:

```bash
.venv/bin/pytest tests/test_collection_integration.py -q
```

Then from `frontend`, run
`npm test -- --run src/components/CollectionRecovery.test.tsx`. Expect five backend
integration cases and nine frontend recovery cases to pass; neither uses personal
sources, real providers or paid AI. Follow the linked setup for test PostgreSQL
and installed dependencies before running these commands.

Owner/browser/live/A7 gates remain deferred. Next select a finite remaining
recovery/operational slice against this matrix, or perform these walkthroughs
when possible. Phase5 deployment/budget work and its allowed AI-use scope require
a separate transition decision with these open gates and carryovers preserved.
No AWS provisioning, daemon installation or new AI approval follows from review.
