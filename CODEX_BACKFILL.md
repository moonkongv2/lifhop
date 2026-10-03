# Codex historical backfill

Phase 2.3 collects selected historical Codex turns from your Mac. Each turn
becomes a searchable Codex PROJECT_EVENT Entry with user/assistant messages,
recorded command results and recorded diffs in their original order. Missing
outputs and omitted material remain explicit. Collection is manual: the process
stops when the command exits. Already stored Entries remain available while your
Mac is offline.

## Setup

Use installed Codex CLI **0.158.0**, the project's Python environment, and the
running backend/frontend from `README.md` / `frontend/README.md`. Apply the DB
migration with `.venv/bin/alembic upgrade head`; Phase 2.3 head is
`b23c7d91e042`. No import worker or object-storage service is required for this
Codex flow. Sanitized text/evidence is stored in PostgreSQL. Raw rollouts and the
Codex history DB stay on your Mac.

```bash
.venv/bin/python -m app.collectors.codex init-config
.venv/bin/python -m app.collectors.codex preview \
  --include-cwd /absolute/path/to/project
```

The config is `.local/codex-collector.json`. Back it up privately: its device UUID
is part of the source identity. Existing configs are never overwritten. To recover
a lost config, copy the UUID from your authenticated Sources page (`mac:UUID`)
and explicitly run `init-config --device-uuid UUID`. Restore the previous filters
as well. Creating a different UUID for the same Mac creates a distinct source and
can produce separate Entries for the same history.

## Select and inspect before applying

`preview` requires explicit `--include-cwd`, `--thread THREAD_ID`, or
`--all-accessible`. Repeat the first two flags to select several projects/threads.
Project roots include descendant directories. Active and archived rollout files
are inventoried. Selection does not mean every candidate can be read.

Edit the config **before** previewing:

- `exclude_cwd`: absolute project paths; descendants are also excluded.
- `exclude_thread`: thread IDs. Exclusion wins over selection.
- `exclude_item_types`: official item type names such as `commandExecution` or
  `fileChange`; omitted items make the turn partial.
- `date_from` / `date_to`: optional inclusive `YYYY-MM-DD` dates, using the
  recorded turn start in Asia/Seoul. Missing dates are omitted with DATE_UNAVAILABLE.
- `field_bytes`: default 64 KiB; `turn_bytes`: default 1 MiB. Oversized evidence
  is truncated/omitted with a partial marker. A turn that still cannot fit is an
  INVALID_ITEM result without a body.
- `rollout_bytes`: 64 MiB; `bundle_bytes`: 512 MiB; `max_pages`: 1,000 per list;
  `run_seconds`: 1,800. These are upper bounds; smaller budgets are allowed.

The command prints an aggregate summary and the private `preview.html` path.
Open it locally and inspect its linked JSON payloads: these are the exact
sanitized bodies that apply checks and sends. Manifest and payload hashes bind
the preview, device and config. Changed config/files require a new preview in a
new directory.

Filtering omits recognized credential files, environment dumps and private-key
material; it masks recognized credentials and local home/project paths. Detection
is incomplete. Review the selected payloads before applying. Preview files remain
sensitive and are ignored by Git; new directories/files use 0700/0600. Payloads
must not be edited in place to preserve the reviewed manifest contract.

## Apply and resume

After reviewing the preview, use its directory:

```bash
.venv/bin/python -m app.collectors.codex apply \
  --run-dir .local/collections/codex/RUN_ID \
  --api-url http://localhost:8000 \
  --email YOUR_EMAIL
```

Enter your lifhop account password at the prompt. Password/access token stay in
memory. The API URL must be HTTPS or loopback HTTP; redirects are rejected. A
non-default config must be passed with `--config PATH` to every command.

Re-run the same apply command after interruption. The server saves an Entry/
observed version and its receipt in one transaction before acknowledging it.
An acknowledgment lost after commit is safe to retry. Local checkpoints are
bound to the API origin, account, device and manifest; the collector checks the
server receipt before skipping a saved checkpoint item. Concurrent apply of the
same bundle is rejected. Different owners cannot read or resume each other's runs.

Before sending each body, the collector checks collection permission and deletion
suppression; the server checks again under the owner lock. A policy change after
preflight can therefore reject a body already in transit. No rejected Entry is
stored. Bodies excluded locally are never part of the upload bundle.

Fresh previews with unchanged source evidence do not duplicate Entries or
versions. Changed evidence uses the existing version/freshness rules: newer
complete candidates may become current; older/partial/unknown-time candidates
remain available for review. Personal annotations and AI permission are preserved.
Source and record external-AI permission both default off; this flow makes no AI
calls.

Blocked outcomes are terminal within that reviewed run. After re-enabling
collection or explicitly allowing reimport, create a **new preview** to collect
those records. Allow reimport does not restore deleted content automatically.

## Browser checks

1. Open `http://localhost:5173/sources`. The Codex source appears when its run is
   registered. Check the run's selected/read/failed/deferred sessions and
   new/unchanged/updated/retained/blocked/failed turns, timestamps and gaps.
2. Open `http://localhost:5173/search`, select Codex and search for a phrase in a
   reviewed turn. Verify messages, recorded command output/exit code and diff.
3. Open Notes & history, inspect a version, and check thread/turn IDs, fork/archive
   context, completeness and collection gaps. Unknown output is never a claimed
   success. Add a personal annotation and replay; it must survive.
4. Re-run the same apply command; Entry/version counts must stay unchanged.
   A fresh preview may report unchanged observations instead of a new Entry.
5. For a disposable record, delete it in lifhop, then create/apply a new preview.
   It must remain absent and the run must report blocked. Pause collection in
   Sources to check body-free policy blocks. Keep external AI disabled.

Sources polls results every five seconds and paginates 20 runs. `Disconnected`
means an active run has had no contact for five minutes; resume from your Mac.
`Partial` includes source/coverage gaps or blocked/failed items. `Completed`
means the reviewed manifest has durable results, not that all local history was
recovered. Individual Entries can contain declared omissions even in a completed
run. Receipt counts describe that ingestion, not the number of currently retained
Entries after later deletion.

## Cleanup and known limits

```bash
.venv/bin/python -m app.collectors.codex cleanup \
  --run-dir .local/collections/codex/RUN_ID
```

Cleanup validates the bundle and refuses unknown files/symlinks or an in-flight
apply. It removes only that local preview/checkpoint, leaving the device config,
Codex originals and server Entries intact. Local preview cleanup is separate from
lifhop deletion; deleting an Entry does not remove your local Codex source files.

Official app-server reads run against disposable rollout copies and a read-only
SQLite backup. Only history-read RPCs are allowed; recorded commands are evidence
and are never executed. Source hash changes, active turns, identifier/order
divergence, unknown consistency schemas, duplicate thread files, unsupported
formats, timeouts and pagination limits remain visible gaps. Duplicate candidate
thread IDs are conservatively rejected, including byte-identical duplicates.
Empty legacy reads are EMPTY_HISTORY gaps, not proof that the source had no
conversation. There is no fallback raw-content parser or reconstruction of missing
history. Full-corpus performance, additional CLI versions and other browser
engines remain unverified. Scheduled collection/collect-now belongs to Phase 4.

## Local verification on 2026-10-03

- 237 backend tests passed against migrations in fresh isolated PostgreSQL
  schemas, including real loopback HTTP ingestion/replay, pre-commit rollback,
  lost-ack retry, ownership, policy/deletion, bounded evidence and child-process
  timeout cleanup. An initial final-suite attempt used the wrong test DB account
  and failed at setup; rerunning with the compose account passed.
- 80 frontend tests passed; lint/build passed. Chromium with synthetic API data
  verified Sources, failure/retry and search-to-evidence navigation at 320, 390,
  768 and 1,440px without overflow or page errors.
- Actual private local preview: 171 files discovered, 13 selected, 158 excluded,
  10 sessions read, 3 failed, 33 turns prepared. Gaps: SOURCE_CONFLICT and
  EMPTY_HISTORY. Personal history has **not** been applied to the server.
- Development DB migration applied; actual owner-history browser checks above
  remain pending. The owner confirmed local preview review and authorized the
  implementation commit before personal apply. No new package, AWS resource or
  recurring cost was introduced.
