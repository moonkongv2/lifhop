# Phase4.1 S4 — Explicit Codex Mac agent and source credentials

Implemented: exact device/CWD/thread registration, paused schedules, collect-now,
source credentials, lease-checked HTTP ingestion, private local spool and bounded
thread rotation. No daemon is installed. The server never opens Mac files and
the agent needs no database, owner password/JWT or AWS credentials. Existing
manual backfill commands remain available.

The owner deferred direct verification and authorized S4 development after S3
commit `4fad0e6`. All executed S4 reads/uploads use fictional fixtures or isolated
synthetic files; real personal sessions, actual Mac sleep/wake, background startup
installation and A7 acceptance remain open. This does not complete Phase4.1.

## Later owner walkthrough — synthetic only

Use the existing [local setup](../../frontend/README.md). From the repository root,
apply migration `l04d9e81c620` before restarting API/frontend:

```bash
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

In another terminal run `cd frontend` then `npm run dev`. Open
<http://localhost:5173/sources> and log in.

1. Under **Codex device collection**, generate a UUID for a **new fictional demo
   device**, enter `/synthetic/project` as its selected CWD root and register it.
   Leave explicit thread IDs empty. Registration reads no files, creates no job
   or token, leaves scheduling paused and keeps AI disabled. A real previously
   imported Mac must reuse its original `mac:UUID`; do not regenerate its identity.
2. Click **Issue or rotate device token**. Copy the one-time token now; closing
   it or refreshing cannot retrieve the secret again. Issuing/rotating pauses
   collection, cancels current work and revokes all previous tokens for this
   source. Metadata remains visible; the secret is not in settings downloads.
3. Keep **Agent API address** at `http://localhost:8000` for this local setup.
   Click **Download agent settings**. Initialize private local files with the
   downloaded JSON path substituted below:

   ```bash
   .venv/bin/python -m app.collectors.codex_agent init \
     --settings-file SETTINGS_JSON \
     --config .local/codex-agent-demo.json
   ```

   Paste the token only at the hidden prompt. Never put it in a command argument,
   chat, screenshot, repository file or log. The command writes a0600 configuration
   and adjacent `.token` file, then exits without reading history. `.local/` is
   ignored by Git. Hide the browser token after saving it locally.
4. Click **Collect device now**. It stays pending while the agent is offline.
   Run a single finite synthetic cycle:

   ```bash
   .venv/bin/python -m app.collectors.codex_agent run \
     --config .local/codex-agent-demo.json \
     --spool .local/codex-agent-demo-spool \
     --synthetic --synthetic-revision 1 --max-cycles 1
   ```

   Expect `completed`, one fictional turn Entry and last connection/check/success
   times. Open <http://localhost:5173/sessions/codex> and select this demo scope.
   The synthetic path never invokes Codex or opens its home, and makes no external
   provider, inference/embedding or AWS request.
5. Collect again and repeat revision1: unchanged receipt, no new Entry/version.
   Collect again with `--synthetic-revision 2`: a second turn appears on the same
   old thread; repeating revision2 adds no duplicates. Each cycle revisits selected
   old threads rather than relying on file modification time.
6. Set a60-second device interval and enable the schedule. Run the same command
   with `--poll-seconds 5 --max-cycles 30` (or omit max-cycles and stop with Ctrl-C).
   Due work runs without a click. Stop/restart with the same private config/spool:
   missed intervals coalesce into one job, and committed receipts replay safely.
   A different worker must wait for the existing90-second lease to expire.
7. Pause the device schedule: active/retry work is fenced, future scheduled claims
   stop and archived records remain. Re-enabling does not revive cancelled work.
   Cancel device collection stops only that job; Pause also stops future jobs.
   Disabling **Allow collection** fences incoming work independently of AI policy.
8. Test **Disconnect device** or revoke its current token. Uploads/heartbeats fail,
   pending/running work is cancelled and schedules pause. Issue a replacement
   token, save it privately with the following command, then explicitly resume
   collection. Replacing the local secret does not enable the server schedule.

   ```bash
   .venv/bin/python -m app.collectors.codex_agent set-token \
     --config .local/codex-agent-demo.json
   ```

9. Changing selected/excluded CWD roots or threads creates a new revision, clears
   its progress/success times, cancels active work and revokes credentials. Download
   and explicitly initialize fresh local settings/token and a new spool root for
   that revision. A running agent cannot accept a remotely broadened selection
   without matching local approval. Old archive content remains.

## Scope, authentication and runtime

- Each opaque token has256 bits of randomness. Only its SHA-256 hash is stored;
  default expiry30 days, API maximum90 days. Issuance responses use `no-store`.
  The UI keeps the secret out of localStorage and query/mutation caches. Owner
  JWTs manage device selection and credentials; collector tokens cannot call
  ordinary archive, account, manual-upload or AI endpoints.
- A token binds to one owner/device subscription and configuration revision.
  Every claim/write checks current revocation/expiry and source policy under the
  owner lock, then job/worker/generation/lease. A presented active expired token
  pauses/fences its own source; an old rotated token cannot pause its replacement.
  Tokens cannot override owner/source or upload to another device. Explicit-only
  thread selections are also checked server-side. For CWD selections, the trusted
  local agent enforces path inclusion/exclusion and sanitization: the server cannot
  attest which local file produced submitted text. Protect source tokens accordingly.
- The agent validates HTTPS origins (loopback HTTP allowed), rejects redirects
  and proxy inheritance, and sends the token only in Authorization headers.
  Logs print status/error codes, not tokens or private bodies. Real operation
  requires an explicit `--codex-home` instead of `--synthetic`; no implicit home
  scan/all-accessible option exists. Do not run it against personal sessions until
  exact device, filters, destination, retention and finite budget are approved.
- The local runtime reuses the supported-version guard and disposable read-only
  app-server snapshots. It never resumes/starts turns or invokes generation.
  It does not copy `auth.json` or Codex configuration files. Raw rollout/history
  snapshots are temporary local inputs; sanitization occurs before upload bundles
  are written. The paginated reader can snapshot the local history database,
  then queries only selected threads and uploads only selected sanitized turns.
  The CLI compatibility
  allowlist remains unchanged; unsupported versions fail visibly and pause work.
- Inventory is bounded to10000 metadata files and up to30 seconds (or the smaller
  selected runtime). A cycle reads at most five selected threads by default
  (configurable1–10), with a persistent rotation offset. Selected old threads are
  revisited even if their modification timestamp is unchanged. Appends and complete
  observations of formerly partial turns use existing stable IDs/version rules.
  Equal/missing source clocks still require explicit current-version review;
  observing a complete candidate does not automatically replace the current one.
- Defaults: schedule paused/300 seconds, schedule minimum60 seconds, heartbeat20
  seconds, lease90 seconds; agent polling1–60 seconds. The existing four total
  job-attempt bound/backoff applies to transient preparation failures. The explicit
  process continues polling through connection failures and retry waits; rejected
  credentials or changed local-selection approval require owner action.
- Active/changing/timed-out/run-limited threads remain deferred. Their partial
  batches remain visible and do not advance last success. A rotation offset may
  move after durable deferred receipts so other selected threads get a turn; it
  is not a completed-history cursor. Later fresh jobs revisit deferred threads.
  Scheduling continues only when these are the sole gaps and no receipt is blocked
  or invalid.
  Blocked, invalid, auth/format/quota and other permanent failures preserve the
  old offset and pause scheduling. No missing session is inferred to be deleted.
- The private spool is bound to origin, subscription and local selection. It stores
  the worker UUID and frozen batches/checkpoints before upload. A lost response
  reuses the same manifest/UUID and durable receipts; another spool cannot replace
  a server-bound frozen batch. Body-free status lookup resolves an uncertain finish.
  Incomplete **unuploaded**, recognized preparation can be rebuilt after a crash.
- One0700 spool per source/revision has a512MiB aggregate guard and process lock.
  Default bundle64MiB (maximum128MiB) reserves space for manifest/preview metadata.
  Source configuration is limited to32KiB. HTTP writes are limited to2MiB; existing
  item/page/snapshot bounds still apply. After seven days, a later tick removes only
  locally confirmed completed/empty/partial/cancelled caches. Failed/unconfirmed
  recovery data remains and may require explicit operator cleanup after abandonment.
  Never remove active/interrupted work or unrelated files. No global disk quota,
  snapshot cleanup after abrupt process death, automatic startup or supervision
  has been verified/installed; deployment/runtime hardening remains later work.

## Executed checks and open acceptance

Automated tests exercise token hash-only storage, normal-route rejection, source/
owner isolation, expiry/revoke/rotation, selection mismatch, offline catch-up,
repeated/uncertain batch/item/finish acknowledgements, stale lease takeover,
deletion suppression, private files/quota, CLI initialization and slow-read pause
fencing. Synthetic rollout files go through the existing disposable snapshot
reader, including unchanged-mtime old-thread appends and active-to-idle recovery.
A separately launched local API and restarted Python agents communicate with only
source credentials and add no duplicate Entries. No personal Codex history is read.

Final full backend **1017 passed** (90.33s), S4-specific **22 passed**, frontend
**215 passed** including five device UI checks. ESLint/build passed (existing
about515KiB bundle warning), as did AST/diff/local-link checks. The test fixture
upgrades the full Alembic chain in a fresh disposable schema. No application DB
migration or owner browser/live acceptance was performed. Details are in
[CURRENT.md](../../CURRENT.md). These establish synthetic
application behavior, not actual Mac sleep/wake or live-provider completeness.
Remaining owner checks stay deferred; S5 integrated acceptance and A7 remain open.
