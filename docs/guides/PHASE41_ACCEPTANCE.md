# Phase4.1 S5 — Integrated verification and deferred acceptance

S4 was committed as `233ae60` before owner-authorized S5 work on2026-10-22.
The integrated checks use fictional sources and disposable PostgreSQL schemas.
They do not close owner browser checks, real-provider compatibility/completeness
or actual Mac sleep/wake acceptance. Overall Phase4.1 remains open.

## Automated evidence

The matrix describes synthetic evidence, not live-source acceptance. Existing
provider tests are rerun with the full backend suite; the Sources test mounts the
real page/components against synthetic HTTP responses, without a real browser.

Executed on2026-10-22: integrated backend **3 passed**; final full backend
**1020 passed** (94.52s); relevant frontend **17 passed**; full frontend
**216 passed**. ESLint, TypeScript/Vite build, Python AST, local-document links
and diff checks passed. Vite retains its existing about515KiB chunk warning.
Initial integration fixtures omitted a worker ID/due time/incremental metadata;
these and the obsolete manual-only UI assertion were corrected before the final
passing runs. Application database migration and actual browser checks were not
performed. No live provider, personal source, paid AI or AWS request was made.

| Gate | Evidence in the repository | Still unverified |
| --- | --- | --- |
| A1 Selected scope, collect-now/schedules, unchanged replay | `tests/test_collection_integration.py` tests both providers under one owner, scheduled catch-up, unchanged Entry/version counts and AI policy; `test_collection_jobs.py` and `test_codex_agent.py` cover selection | Owner UI walkthrough and selected live-source results |
| A2 Durable replay, overlap and stale-worker fencing | `test_collection_jobs.py` frozen-batch crash/restart; `test_github_incremental.py` atomic cursor promotion; `test_codex_agent.py` lost batch/item/finish ACK and lease takeover | Actual machine/network interruption and capacity |
| A3 Old GitHub graph/documents/discussions | `test_github_incremental.py` old merge parents, changed head documents, old comment/review edits, pagination and reconciliation fairness | Live permissions, mutable provider snapshots and full corpus coverage |
| A4 Codex offline/reconnect and old threads | `test_codex_agent.py` unchanged-mtime append, thread rotation, active deferral then complete candidate; integrated test resumes the original pending job | Actual Mac sleep/wake, real Codex formats and long histories |
| A5 Pause, revoke, policy, ownership and deletion | Provider suites cover scoped credentials/owners, pause and deletion races; integrated tests revoke Codex during GitHub reading, and disable failed GitHub while Codex continues | Live credentials/policy changes; abrupt-death snapshot cleanup |
| A6 Source status, coverage and separate AI state | `frontend/src/pages/SourcesCollection.test.tsx` renders GitHub failure alongside offline/pending Codex, deferred counts, independent disconnect and provider-selected batches; component tests cover retry/schedule/progress | Owner browser/layout/accessibility walkthrough; full Phase4.2 indexing/failure presentation remains later work |
| A7 GitHub independence from Mac | `test_github_process_progresses_while_codex_is_stopped_then_reconnects`: two separate GitHub worker processes advance revision1→2 with no Codex agent process; pending Codex job survives and later resumes | Owner-observed actual Mac sleep/wake and separately approved finite live-source scope; **gate remains open** |

An offline source retains archived records. An unchanged check may advance freshness
without adding versions. A completed batch describes its bounded snapshot, not
all-source coverage, embedding completion or answer quality. Coverage gaps and
retained candidates requiring current-version review stay visible.

## Later owner walkthrough — both fictional sources together

Direct verification is deferred at the owner's request. When the environment is
available, follow the [GitHub setup](PHASE41_COLLECTION.md) and
[Codex setup](CODEX_AGENT.md) first: local PostgreSQL/API/frontend, migration through
`l04d9e81c620`, fictional `example/repo` repository ID123, and a new fictional
device selecting `/synthetic/project`. Set up its private agent config/token with
the hidden prompt. Keep AI disabled. Open <http://localhost:5173/sources>.

1. Leave the Codex agent stopped. Click **Collect device now**: its job remains
   pending. Click **Collect now** for the fictional GitHub source, then run:

   ```bash
   .venv/bin/python -m app.workers.collection_worker \
     --subscription-id GITHUB_SUBSCRIPTION_ID \
     --spool .local/github-demo-spool --synthetic \
     --synthetic-revision 1 --max-cycles 1
   ```

   GitHub completes and adds fictional records; Codex remains pending. Queue
   GitHub once more and repeat with revision2. Expect a new commit/document
   snapshot while the same Codex job remains pending. This demonstrates separate
   processes on the same awake computer; it does not simulate actual Mac sleep.
2. Reconnect the fictional Mac agent with a single finite cycle:

   ```bash
   .venv/bin/python -m app.collectors.codex_agent run \
     --config .local/codex-agent-demo.json \
     --spool .local/codex-agent-demo-spool \
     --synthetic --synthetic-revision 2 --max-cycles 1
   ```

   The pending job completes with two fictional turns on one thread. Queue/repeat
   revision2 for each provider; neither adds an Entry/version. Follow each setup
   guide's schedule walkthrough to check due-time catch-up and explicit pause.
3. Inspect **Collection source** and the corresponding **collection batches**.
   Check partial/deferred coverage separately from last success and AI policy.
   These receipts include manual history and incremental cycles; they do not
   identify every batch as a historical backfill.
4. Disconnect the fictional Codex device: its pending/running job is cancelled,
   tokens are revoked and its schedule pauses. GitHub controls and archived
   records remain available. Disable GitHub collection and confirm the selected
   Codex source remains independently controllable. Complete each provider guide's
   cancellation, deletion protection and token replacement checks separately.

Record each observed result/failure rather than marking all A1–A7 passed together.
Do not read personal Codex history, use live GitHub credentials, install startup
services or perform paid AI/AWS work as part of this fictional walkthrough.
Actual Mac sleep/wake and live sources need their own finite scope and evidence.

## Next boundary

Owner/browser and live/A7 acceptance are pending. Phase4.2 recovery/deployment work
is a separate slice; no queue, daemon, infrastructure or new dependency was added
by S5. Revisit the existing D01–D09 carryovers at Phase4 exit. This record does not
reopen paid trials or approve personal-data collection.
