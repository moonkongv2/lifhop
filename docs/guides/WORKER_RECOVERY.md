# Phase4.2 — Bounded database reconnects in existing workers

This slice follows collection lease visibility commit `8287085`. A database
connection error in import purge/receive or GitHub polling previously terminated
the explicitly started worker immediately. Both loops now bound retries for
connection-style DB errors and stop on other errors. No service is installed.

## Behavior and process exit

- In continuous import/GitHub polling, `OperationalError`/`InterfaceError` triggers
  waits of1,2,4 seconds before retrying the cycle. A fourth consecutive connection
  failure stops with exit1 and a generic restart instruction.
  These exception classes can also represent persistent authentication/configuration
  faults; retry does not establish that the error is transient. Such faults stop
  at the same consecutive-failure bound.
- A successful cycle resets this consecutive failure budget, including a healthy
  poll with no eligible job. Per-job attempt limits and lease/revision/policy
  guards are unchanged. A reconnect is not a new approval to write.
- Other unexpected errors stop with exit1 and a generic configuration/schema/
  source/spool instruction, without printing exception text, SQL or credentials.
  KeyboardInterrupt exits0 and preserves durable state.
- A single GitHub run (no `--poll-seconds`) and import `--once` try one cycle,
  then exit1 on a DB connection error rather than reconnecting automatically.
  Successful bounded runs exit0. Job/batch failures remain in their existing
  status APIs: exit0 alone does not establish that every record was collected.

Import CLI now accepts `--once` (at most one purge/receive cycle) and
`--max-cycles N` (positive bound on attempted cycles, including failures). GitHub
keeps its existing polling/max-cycles options; failed polls also consume that
bound. Reaching a finite cycle bound on a DB failure returns1. An import cycle
still performs bounded purge work and at most one delivery; it is not a record
selection mechanism. Existing queued imports may be processed.

Recovery uses the same database rows and private spool. A GitHub action interrupted
after a receipt commit can leave RUNNING until its90-second lease expires; quick
DB recovery does not bypass that wait. The next eligible claim replays the frozen
batch and increments generation/attempt according to existing rules. Source AI
permission is unchanged; neither worker starts embedding or answer requests.

## Deferred verification — synthetic environment only

No migration or new dependency is needed. Use the existing local setup and a
fictional-data-only environment with `QUEUE_MODE=local`/`S3_MODE=local`.
API/frontend setup and URLs: [Sources guide](COLLECTION_RECOVERY.md) and
[import guide](IMPORT_RECOVERY.md). Inspect `/sources` and import job detail for
durable status, rather than relying on process output alone.

For deterministic faults without stopping PostgreSQL or changing application
rows, run from the repository root with test PostgreSQL available:

```bash
.venv/bin/pytest tests/test_worker_reconnect.py -q
```

Expect13 cases to pass: both loops reconnect, bound persistent failures, reset the
failure budget, sanitize nontransient errors and stop on Ctrl-C; one-shot failure
does not reconnect; import and partially committed GitHub work resume correctly.
Faults and sleeps are injected. The GitHub case advances an isolated test lease
to exercise recovery without waiting90 seconds; it does not bypass real leases.

To perform one normal fictional import-worker cycle later:

```bash
.venv/bin/python -m app.workers.import_worker --once
```

Expected exit0 with a healthy purge/receive cycle; inspect the job for its actual
result. `--max-cycles 3` attempts at most three cycles. GitHub retains the finite
synthetic command in [its setup guide](PHASE41_COLLECTION.md). Do not stop a shared
database or use personal archives/AWS credentials to inject a connection fault.

## Limitations

Executed on2026-10-22: targeted reconnect/import/collection tests **39 passed**
(5.41s); final full backend **1047 passed** (94.23s); full frontend **227 passed**.
Both worker CLI help commands, Python AST, diff and local-document links passed.
No tests failed. Frontend files were unchanged, so its previous lint/build result
(about522KiB chunk warning) was not rerun. DB faults/sleeps are injected in test
schemas; no live PostgreSQL shutdown, AWS, paid AI, personal data, migration or
startup installation was exercised. Actual browser verification remains deferred.

These are bounded reconnect waits, not a wall-clock deadline on DB queries,
connection establishment, file I/O or a hung process. They do not install a
supervisor or restart an exited process. A live import lock is never forcibly
stolen. Persistent errors require checking the DB/configuration and explicitly
restarting; real network/driver/deployment behavior remains unverified.

Existing processor-level retries remain independent: the import processor may
already return storage/DB processing failures to PENDING, and collection leases
may expire while the process waits. Codex's HTTP agent and the embedding worker
retain their existing loops; no paid job or agent installation is added here.
Owner/browser/live/A7 acceptance and Phase4 exit remain open.
