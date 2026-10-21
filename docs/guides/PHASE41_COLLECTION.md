# Phase 4.1 collection — S1–S3 GitHub collection

Implemented boundary: source registration, collect-now/scheduled jobs, explicitly
started polling worker, pause/retry controls, bounded graph walks and optional
rotating PR/issue/comment/review reconciliation. No Codex agent yet. This does not
complete Phase4.1. The accepted Phase3.3 D01–D09 carryovers remain unchanged.

## Local setup and synthetic owner verification

Use the existing local database/API/frontend setup in [frontend/README.md](../../frontend/README.md).
The API and worker load the repository-root `.env` regardless of the working
directory; explicitly exported environment variables still take precedence.
The file must contain `DATABASE_URL`, `JWT_SECRET_KEY` and `AWS_REGION`.
Use the same configuration as the local API rather than creating a separate
worker database or secret. Run the commands below from the repository root so
the relative spool path also stays consistent across restarts.
Apply migrations through `k93c8d70b519` before starting the updated API:

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
6. Click Collect now again and rerun the command. New S3 jobs finish `empty` with
   no receipts when HEAD/history are covered and discussions are disabled. The
   same two Entries/versions remain. Legacy jobs created before S3 still use
   unchanged receipts. Registration/refreshing must never create another job.
7. Queue another job, then **Cancel collection** before running the worker.
   Expect `cancelled` and no new collection. Disable **Allow collection** for
   this source to disable Collect now and fence any in-flight job; re-enabling
   collection does not revive that job or grant AI permission.
8. Delete the synthetic commit from its Entry detail, then collect again.
   With a covered S3 graph, expect `empty` and the deleted record to stay absent.
   A later rediscovery (for example after a selection revision) returns a
   `REIMPORT_BLOCKED` receipt and a partial batch; it still cannot restore that
   record unless reimport is explicitly allowed in Sources.

Agent checks use isolated disposable `_test` schemas. The owner walkthrough above
writes only the explicitly selected synthetic source into the configured local
application database. The owner confirmed the initial synthetic GitHub result
in Sources on2026-10-22. Repeat/unchanged, cancel and deletion-protection browser
checks remain pending.

## S2 schedule walkthrough — may be performed later

On2026-10-22 the owner deferred the remaining S1 browser checks and authorized
S2 development. Deferral is not a pass.

1. Apply `alembic upgrade head` as above and restart the API/frontend. Open
   <http://localhost:5173/sources> and use only the fictional `example/repo` source.
2. In that source's schedule controls, choose **60 seconds** and **Enable schedule**.
   New sources default to paused/900 seconds. Enabling schedules the first check
   one interval later; it does not immediately create Entries or start a worker.
3. Start this selected-source worker from the repository root:

   ```bash
   .venv/bin/python -m app.workers.collection_worker \
     --subscription-id SUBSCRIPTION_ID \
     --spool .local/phase41-synthetic-spool --synthetic \
     --poll-seconds 5
   ```

   Keep the same spool used for this source's S1 worker. This process polls only
   that subscription and makes no provider, AI or AWS requests with `--synthetic`.
   Add `--max-cycles 30` for a finite demonstration, or stop with Ctrl-C. Nothing
   is installed at startup. Poll intervals are1–60 seconds; schedule intervals
   are60–604800 seconds (one week).
4. After the due time, expect a completed job without clicking Collect now.
   Further S3 cycles use new empty jobs/batches when the selected immutable data
   is unchanged, preserving the original two Entries/versions. Next check and
   last success remain visible.
5. **Pause schedule** cancels/fences active or retry-waiting work. Wait through
   the old due time: no new job should appear. Enable again to start a new future
   interval; cancelled jobs stay cancelled. **Cancel collection** stops only the
   current job; use Pause schedule to stop future jobs as well.
6. Stop and restart the polling command with the same spool. If no job was active,
   a past due time becomes one catch-up job rather than a job per missed interval.
   Interrupted active work waits for its90-second lease to expire, then replays
   the same frozen batch/receipts. No duplicate Entries should appear.

Failure paths are covered with isolated synthetic tests; they require no deliberate
credential breakage in the owner's database. Rate limit/timeouts/read failures
retry the same job at most three times after the first attempt, using30/60/120s
backoff plus0–25% jitter and respecting a later provider retry time. Retry waiting
shows `pending`, the error code and next retry. Crashed-worker takeovers count
toward the same four-attempt bound. The inherited reader also bounds each GET's
transport retries; request/time limits apply per worker attempt.

Authentication/configuration/format/quota failures and exhausted retries fail the
job and pause its schedule for owner action. A partial batch pauses with
`PARTIAL_COLLECTION`; last success is not advanced. **Retry failed job** explicitly
reopens only the latest failed job, resets its attempt budget and reuses its spool;
it does not enable scheduling. **Collect now** instead creates fresh work. Do not
remove a failed job's spool before retry. Branch/document configuration editing
is still unavailable; discussion selection has its own explicit control and
workers reject stale configuration revisions. Schedule interval
changes affect future slots without changing the selected content configuration.

Disabling Allow collection pauses schedules and cancels active work. Re-enabling
collection alone does not resume scheduling or enable AI. An active manual backfill
delays scheduled collection with `MANUAL_BACKFILL_ACTIVE`; finish it before retrying.

## S3 incremental and old-thread changes — may be performed later

S1/S2 were committed as `a2db2bc` before this work. Remaining owner checks stay
deferred. S3 tests use fictional records, never the owner's GitHub account.

1. Apply the migration above and restart the API/frontend. Open
   <http://localhost:5173/sources>. Use `example/repo`, ID123, branch `main`, in a
   clean synthetic demo database if earlier deletion tests would interfere.
   Stop any existing polling worker and pause its schedule before this walkthrough.
2. Check **Collect PRs, issues, comments and reviews for repo:123**, leave excluded
   numbers empty and **Save discussion selection**. Changing the selection
   cancels/fences active work, pauses scheduling, starts a new configuration
   revision and clears that revision's progress/success times. Archived records
   remain. New/existing sources default to discussions disabled; registration and
   this selection make no provider request and do not enable AI.
3. Click Collect now, then run:

   ```bash
   .venv/bin/python -m app.workers.collection_worker \
     --subscription-id SUBSCRIPTION_ID \
     --spool .local/phase41-synthetic-spool --synthetic --synthetic-revision 1
   ```

   Expect the synthetic commit/README, issue#1 and its initial comment. A clean
   source has four Entries. Graph completed/documents checked point to `aaaaaaaaaa`;
   the discussion inventory has one checked issue. Existing identical records
   produce unchanged receipts rather than new versions.
4. Click Collect now again and rerun with `--synthetic-revision 2`. Expect a new
   `dddddddddd` commit and README snapshot, an edited old comment and a new comment
   on issue#1. The issue's parent update timestamp intentionally stays unchanged.
   A clean source now has seven Entries/eight observed versions. Old document
   snapshots and the comment's previous version remain readable. Browse
   <http://localhost:5173/repositories/github?scope=repo:123> and its Discussions.
5. Repeat revision2. Expect unchanged discussion receipts, no new Entries/versions
   and no repeated immutable commit/document reads. With discussions disabled,
   an unchanged fully covered graph instead gives an `empty` batch.
6. Inspect Sources: branch observed/completed/document SHA and pending steps;
   known/unchecked/in-progress thread counts; inventory page/pass time and oldest
   completed thread check. A successful **bounded cycle** does not prove all
   history or all mutable records have been checked. Continue collect-now or
   resume a schedule for pending work. The polling command also accepts
   `--synthetic-revision 2` with `--synthetic`.

### S3 progress and limits

- Each new job uses a fresh provider-response cache. Interrupted work reuses its
  frozen preparation/manifest; schema migration labels pre-S3 jobs `backfill` so
  their original parser/config digests remain valid. Their old traversal behavior
  lasts only for those retained jobs; newly enqueued jobs use S3.
- Walk parent SHA edges rather than commit dates. Stop at a known SHA only when
  its ancestry has been completed. Each cycle processes at most50 graph steps
  (enter/exit frames), rotating branch priority; incomplete stacks persist across
  successful jobs. A new observed head does not discard an unfinished older walk.
  Source-selected head documents refresh when the pinned head changes. Branch or
  object unavailability fails visibly without deleting archived observations.
- When discussions are enabled, each cycle reads one rotating `sort=created`
  inventory page and one overlapping recent `sort=updated` page. Repository issue
  listings include PR roots; PR details provide their own object IDs. Revisit at
  most three oldest-checked/unchecked threads, reserving a slot for an older
  checked thread even while new roots are pending, and read at most three child-
  stream pages per thread. Stream/page/PR membership progress survives across jobs.
  This rotating check finds old-thread edits even when parent timestamps do not
  change. Live API semantics follow the official [issues](https://docs.github.com/en/rest/issues/issues)
  and [commits](https://docs.github.com/en/rest/commits/commits) contracts.
- Each thread refreshes its parent before/after page work. Parent revision changes
  restart its scan; mutation during the observation window produces a partial
  batch without advancing progress. Snapshots are not atomic across provider
  records. Missing comments/refs are never interpreted as confirmed deletions.
- Progress advances only in the transaction that verifies all receipts, current
  lease generation/revision/policy and successful batch completion. Failed,
  suppressed or partial observations do not promote coverage. Retained archive
  content still follows existing freshness and owner-review rules.
- Limits remain explicit: existing per-GET/request/runtime/spool/bundle limits;
  up to100000 graph stack frames and250 PR commit members. Large diffs/document
  trees still use the existing bounded adapter and may require same-job manual
  recovery; branch/document reconfiguration remains unavailable in this UI.
  Resource/auth/partial failures
  pause the schedule; they never silently declare remaining history complete.
  Reconciliation lag grows with corpus size; the displayed oldest check/inventory
  pass is an observation, not a live completeness guarantee. Old revision cursor
  metadata is retained; corpus-scale capacity/global retention remain unmeasured.

## Runtime, recovery and limits

- The existing manual and pre-S3 job paths retain bounded backfill preparation.
  New jobs use the S3 graph and thread progress described above.
- Registration is idempotent for identical configuration. Changing an existing
  branch/document configuration is rejected; discussion selection changes create
  a new revision and pause/cancel existing work. Schedule controls change timing
  only. No provider resolution runs during registration.
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
  request starts a fresh job; Retry failed job reopens frozen work. Failed/partial
  jobs never advance last success.
- Spool directories are private (0700; files0600), identity/config bound, with a
  512MiB aggregate guard and a single process lock per spool root. Existing
  per-bundle/page/request/time/response limits remain. Before a claimed job runs,
  under the spool process lock, completed/empty/partial/cancelled job caches older
  than seven days are removed after checking database/source/job identity.
  Failed/pending/running jobs are retained indefinitely for recovery; retained
  failures can exhaust quota and require operator action. After explicitly
  abandoning a terminal job and all worker processes exit, the operator may
  remove its `job-ID` directory explicitly.
  Cleanup deletes local cache/bundles, not archived Entries/receipts. Do not remove
  active/interrupted spools or unrelated directories. Use exactly one stable,
  private spool root per subscription/database. The512MiB guard covers that root,
  not disk usage across arbitrary operator-created roots. Hosted supervision and
  global disk capacity/retention remain later deployment work.
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

Follow-up on2026-10-22: fixed worker startup by resolving `.env` from the repository
root, independent of the working directory. Backend **963 passed**; worker
`--help` succeeded from outside the repository. The owner subsequently confirmed
the initial synthetic GitHub result in Sources. This does not establish the
remaining browser checks, live-source completeness or runtime acceptance.

S2 verification on2026-10-22 includes scheduled-slot coalescing, concurrent ticks,
pause during provider reads, retry timing/exhaustion, auth/manual recovery, stale
configuration, source disable, quota/expiry and deletion races. A separate Python
worker process collected a due fictional source and a restarted process added no
extra job. This establishes local synthetic process execution, not cloud uptime.
Final full backend **978 passed**; frontend **209 passed**, ESLint/build passed
(existing about505KiB chunk warning); diff checks passed. Application DB migration
and owner browser verification were not performed by the agent.

S3 adds synthetic checks for old newly reachable commits, bounded multi-job graph
and child pagination, changed documents/refs, old-thread/comment/review edits,
rate-limit recovery, partial/cancelled cursor protection, immutable cache freshness,
atomic receipt replay and upgrade/downgrade preservation of existing jobs.
Final S3 backend **995 passed** (84.56s); GitHub-focused **82 passed**; frontend
**210 passed**, including5 collection UI checks; ESLint/build passed (existing
about507KiB chunk warning). Diff and local documentation-link checks passed.
The agent did not migrate the application database or perform owner browser/live
provider acceptance.

Remaining S1–S3 owner browser verification and live selected-source acceptance
are deferred/open. S4 adds the Codex agent and credentials. A7 Mac sleep/wake/live
acceptance remains open for overall4.1. Final S3 check results are in CURRENT.md.
