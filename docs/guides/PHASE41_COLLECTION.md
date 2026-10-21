# Phase 4.1 collection — S1 GitHub collect-now

Implemented boundary: source registration, explicit collect-now jobs, one-shot
server worker, Sources controls and durable batch receipts. No scheduler, Codex
agent, incremental graph cursor or discussion reconciliation yet. This does not
complete Phase4.1. The accepted Phase3.3 D01–D09 carryovers remain unchanged.

## Local setup and synthetic owner verification

Use the existing local database/API/frontend setup in [frontend/README.md](../../frontend/README.md).
Apply migration `i71a6b58f397` before starting the updated API:

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm run dev
```

1. Log in at <http://localhost:5173> and open
   <http://localhost:5173/sources>.
2. Under **GitHub collect now**, enter repository `example/repo`, ID `123`,
   branch `main`, and keep the default document patterns. Register the source.
   Registration makes no provider request, creates no Entries, and leaves AI
   disabled. If this ID already has a different configuration, use an isolated
   local demo database rather than changing an existing source.
3. Click **Collect now**. One pending job appears. The subscription ID is shown
   in the source card; it is distinct from the repository ID and job ID.
4. From the repository root, substitute that subscription ID below:

   ```bash
   .venv/bin/python -m app.workers.collection_worker \
     --subscription-id SUBSCRIPTION_ID \
     --spool .local/phase41-synthetic-spool --synthetic
   ```

   This command uses only a fixed fictional fixture. It makes no GitHub, AWS or
   AI request and ignores any provider token. It creates a synthetic commit and
   README snapshot in the authenticated subscription owner's archive. It exits
   after processing the current job; it does not install a background process.
5. Sources refreshes every five seconds. Expect `completed`, a batch ID, last
   check/success times, and two `new` receipts. Choose **GitHub** in the historical
   batch selector below to inspect the corresponding coverage/counts. Open
   <http://localhost:5173/repositories/github?scope=repo:123> to inspect the commit
   and document. Source links are fictional; do not use them as live evidence.
6. Click Collect now again and rerun the command. Expect two `unchanged` receipts
   with the same two Entries/versions. Registration alone and refreshing the page
   must never create another job.
7. Queue another job, then **Cancel collection** before running the worker.
   Expect `cancelled` and no new collection. Disable **Allow collection** for
   this source to disable Collect now and fence any in-flight job; re-enabling
   collection does not revive that job or grant AI permission.
8. Delete the synthetic commit from its Entry detail, then collect again.
   Expect a `partial` job with a `REIMPORT_BLOCKED` receipt. The deleted record
   stays absent unless reimport is explicitly allowed in Sources.

Agent checks use isolated disposable `_test` schemas. The owner walkthrough above
writes only the explicitly selected synthetic source into the configured local
application database. Owner browser confirmation remains pending.

## Runtime, recovery and limits

- S1 supports commit/diff and selected Markdown documents using the existing
  bounded backfill preparation. Every new job has a fresh preparation/cache;
  it currently traverses selected reachable history again. This is **not** the
  bounded incremental/reconciliation algorithm planned for S3.
- Registration is idempotent for identical configuration. Changing an existing
  configuration is rejected; revision editing and scheduling land in later
  slices. No provider resolution runs during registration.
- Request UUIDs, including requests coalesced into an active job, remain bound
  to that job after completion. At most one pending/running job exists per source.
- A 90-second lease is renewed before/after each bounded provider GET and at
  every ingestion transaction. Owner locks are released before provider I/O.
  Takeover increments a generation; cancellation and collection disable fence
  old work even after collection is enabled again.
- Restart the same worker with the **same spool** after an interrupted process.
  Before lease expiry another process cannot claim the job. Afterwards it resumes
  the frozen manifest/run UUID and replays durable receipts without duplicate
  Entries. Do not move the spool between databases/sources.
- Manual backfills and active incremental jobs conflict with HTTP409 rather than
  overwriting each other. Finish the active manual run, or cancel the incremental
  job before resuming manual work. Job-bound batches cannot be mutated through
  the manual HTTP endpoints, including after cancellation/completion.
- Failed jobs remain visible with body-free error codes. Collect now with a new
  request starts a fresh job; automatic retries/backoff and same-job explicit
  retry controls are S2. Failed/partial jobs never advance last success.
- Spool directories are private (0700; files0600), identity/config bound, with a
  512MiB aggregate guard and a single process lock per spool root. Existing
  per-bundle/page/request/time/response limits remain. No automatic cleanup runs:
  retain interrupted jobs for recovery. After a terminal job and all worker
  processes exit, the operator may remove its `job-ID` directory explicitly.
  Cleanup deletes local cache/bundles, not archived Entries/receipts. Do not remove
  active/interrupted spools or unrelated directories. Long-term expiry/cleanup
  automation and quota behavior across different spool roots remain S2 work;
  unattended operation is not enabled.
- A real provider run omits `--synthetic`; an optional narrow GitHub read token
  comes only from runtime `LIFHOP_GITHUB_TOKEN`, separate from lifhop login.
  No provider token is accepted by API/config/CLI arguments or stored in the DB.
  Do **not** run against personal repositories until the exact source, filters,
  destination, retention and finite request/storage budget are approved.
- The server worker has direct database access. No unattended upload endpoint or
  collector credential is exposed by S1. Source-scoped upload credentials and the
  Mac agent are still S4 work. Hosting is Phase5.

## Executed verification and remaining gates

The isolated PostgreSQL test fixture upgrades the full Alembic chain into a fresh
schema. New HTTP/worker tests cover owner isolation, exact selection, repeated and
coalesced requests, unchanged replay, changed observation history, suppression,
manual conflicts, concurrent claims across independent DB sessions, injected-clock
lease takeover, cancellation during a provider read, disable/re-enable fencing,
auth failure visibility and crash after a committed receipt with frozen replay.
Frontend tests cover registration without collection, explicit collect/cancel,
disabled-source controls and recoverable errors. These establish application
behavior with synthetic records, not live GitHub completeness or AI quality.

Validation on2026-10-21: backend `pytest -q --tb=short` **962 passed**;
frontend Vitest **207 passed**; ESLint and production build passed. Vite reports
the existing main-chunk size warning (about504KiB minified). No live GitHub,
AI/embedding or AWS request was made.

Owner browser verification, live selected-source collection and separate-process
runtime acceptance remain open. S2 adds scheduling/retry/recovery controls; S3
adds bounded graph/mutable-record reconciliation; S4 adds the Codex agent and
credentials. A7 Mac sleep/wake/live acceptance remains open for overall4.1.
