# Phase4.2 first slice — Collection status and recovery guidance

Sources now shows a collection status and next action for each registered GitHub
repository/Codex device. This first slice reuses existing jobs, source policy and
indexing APIs. It does not change retry, queue, lease or credential behavior.
Phase4.1 owner/browser and live/A7 checks remain deferred after S5 commit `01e7361`.

## What the states mean

| Display | Meaning and next step |
| --- | --- |
| Collection permission unavailable | Policies have not loaded or the source is absent from the returned policy list. Wait/retry the policy read; this is not an explicit denial. |
| Collection disabled | Allow collection is off. Enable it before new collection; AI permission remains separate. |
| Queued | A manual or scheduled job awaits the selected worker/agent. A queued manual job can run while its schedule is paused. |
| Retry scheduled | The pending job has a retry time. Keep its worker/agent running; this is an eligibility time, not a guarantee the process is alive. |
| Collecting | The latest job is marked running. A stale process is not diagnosed from this response alone. |
| Partially collected | Inspect batch gaps, blocked/failed receipts and the reason. Deferred active/changing threads may be revisited by later enabled cycles. |
| Collection failed / Needs attention | Read the reason and next action. Expired/revoked tokens, unsupported formats, spool bounds and exhausted retries require different recovery. |
| Scheduled / Schedule paused | No active job is shown. Scheduled work needs its explicitly running process. A cancelled job is never revived by enabling a schedule. |

The Codex offline label means no agent contact within the server's current
120-second freshness window. Offline can coexist with queued/failed/paused work;
it does not prove a collection failure. GitHub has no process-heartbeat field in
this API, so the UI does not claim its worker is online or offline.

Automatic attempts are bounded. A terminal timeout/read/rate-limit failure directs
the owner to check the cause before retrying; it never promises another automatic
attempt. A current pending retry takes precedence over an earlier schedule error.
Retrying one job does not enable its schedule. Partial batches need a fresh
collection after reviewing gaps rather than an unsupported failed-job retry.

## Separate AI indexing view

The read-only **AI indexing status** section uses `GET /indexing/runs` and matches
each run to the exact source provider/scope. It refreshes every30 seconds and
shows returned run status, per-state job counts and error/uncertain outcomes.
The API returns at most the latest50 owner runs across all sources. Absence here
does not establish that a source has never been indexed. A completed run may
contain failed/blocked jobs and covers its own selection, not all source records.
Current source AI permission is displayed separately from these historical runs.

Opening Sources or retrying a failed status read does not create an indexing
preview/run, approve spending, change permissions or retry an AI job. Collection
retry is also independent of indexing. Uncertain indexing outcomes retain their
accounting and require separate review before any newly approved attempt.

## Deferred owner verification

Use [local setup](../../frontend/README.md) and existing fictional sources from
the [GitHub](PHASE41_COLLECTION.md) and [Codex](CODEX_AGENT.md) guides. This slice
adds no migration; the application must already be upgraded through
`l04d9e81c620`. If needed, start the API with
`.venv/bin/uvicorn app.main:app --reload` and the frontend with `cd frontend` then
`npm run dev`. Open <http://localhost:5173/sources> after logging in.

1. Leave the fictional Mac agent stopped and click **Collect device now**. Expect
   **Queued**, a separate offline indicator after the freshness window, and an
   instruction to start the selected agent. Paused scheduling alone must not
   hide this manual job. Cancel it if you do not want the later agent to claim it.
2. Inspect a paused fictional source: expect the collect-now/schedule next action.
   Disable its **Allow collection** policy and expect **Collection disabled**;
   enabling collection alone must not enable AI or resume cancelled work.
3. For any existing partial/failed/retry state, check its reason, retry eligibility
   time and next action. Synthetic component tests cover timeout/exhaustion/token
   expiry; no real credential failure or personal data is required to verify them.
4. Inspect **AI indexing status**. Existing runs must match the exact source scope.
   An empty history is labelled as returned recent history, not full index coverage.
   A failed status request offers only **Retry loading indexing status**; collection
   controls remain independently available. Do not start paid indexing for this check.

## Remaining work

Executed on2026-10-22: focused frontend **25 passed**; final full frontend
**225 passed**; ESLint and TypeScript/Vite build passed. The existing Vite chunk
warning remains (about521KiB). Related backend collection/incremental integration
and indexing tests **48 passed** (8.07s) in isolated PostgreSQL schemas; the full
backend suite was not rerun because backend code is unchanged. An initial build
found a union-type property access; a property guard fixed it before the final
passing checks. Diff and local-document link checks passed. No actual browser,
live source, paid AI request, application DB migration or startup installation
was exercised.

This slice changes frontend presentation only. Stuck-task detection and
DB-commit/queue-send reconciliation still need fault-injection review and a
separate implementation slice. Full index coverage and detailed indexing job
management, process supervision, real browser/layout checks, live sources and
actual Mac sleep/wake remain unverified. No daemon, queue system, dependency,
paid AI or AWS resource is introduced.
