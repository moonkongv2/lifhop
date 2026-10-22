# Phase4.2 — Durable import notification and stale-work recovery

직접 확인은 [Phase4 통합 절차](PHASE4_OWNER_CHECK.md)에서 시작한다.
아래의 장애 테스트/상세 명령은 개발자 참고이며 소유자의 추가 필수 과제가 아니다.

This slice follows Sources status/recovery commit `0d114ad`. It addresses the
ChatGPT archive ImportJob queue. Codex/GitHub already use revision-fenced leases
and durable receipts. Phase4.1 owner/browser/live/A7 acceptance remains deferred.

## Recovery behavior

An import is durably PENDING before its queue notification is sent. A process can
die between those operations. Local mode already discovers database rows; AWS
mode previously depended on a notification reaching SQS. The existing worker now
also discovers committed PENDING and stale RUNNING imports in either mode.

- Before an AWS receive, reconcile PENDING rows at least60 seconds old and stale
  RUNNING rows, even while SQS contains unrelated messages. If SQS is empty or
  unavailable, check database rows without the pending grace period.
- RUNNING is eligible after `import_max_seconds + 60` seconds (default180) from
  its start, or when its start time is absent. Age is not proof of process death:
  the existing owner's advisory lock protects live work across batch commits.
- Probe the oldest eligible job for each of at most50 owners per check. Skip
  owners holding the import lock, so one busy owner's backlog cannot fill all
  candidate slots. Over50 simultaneously blocked owners need a separate capacity/
  fairness review. The processor rechecks state, policy and attempt limits.
- Reconciled rows have no SQS receipt to acknowledge. Real deliveries are
  acknowledged after durable terminal state. An ACK failure leaves the worker
  running; a later duplicate terminal delivery does not rewrite records/versions
  or increase attempts. Exception text is omitted from queue error logs.
- SQS connect/read timeouts are3/25 seconds, SDK retries are disabled, and long
  polling remains20 seconds. These are network bounds, not a process watchdog.

Atomic Entry/cursor commits, collection/deletion policy and `import_max_attempts`
(default3) remain authoritative. FAILED/PARTIAL/COMPLETED rows are not reopened by
reconciliation. Infrastructure failures may return to PENDING until the attempt
limit; policy/archive errors remain visible terminal results.

Queue send errors retain visible FAILED/manual retry behavior when the submitted
PENDING attempt has not advanced. A send exception may follow delivery: upload
and retry handlers now lock/recheck status and attempt count before recording
failure, preserving running/completed work and later PENDING processing attempts.
A busy locked row is left untouched. This does not decide whether an uncertain
send reached SQS; duplicate delivery remains safe.

## Deferred owner verification — local synthetic data only

Follow [frontend setup](../../frontend/README.md) with local PostgreSQL/SeaweedFS,
`QUEUE_MODE=local`, `S3_MODE=local` and a fictional ChatGPT ZIP. No migration is
added. Start API/frontend and open <http://localhost:5173/imports> after login.

1. Stop the import worker, upload the fictional ZIP and open its job detail.
   Expect PENDING with no processed records.
2. From the repository root run `.venv/bin/python -m app.workers.import_worker`.
   Expect the same job to complete and its fictional entries to appear. No new
   queue or recovery daemon is needed.
3. Review the job and entries; restarting the worker must not add versions for
   terminal delivery. Use the automated tests for send/receive/ACK loss and stale/
   live-lock races instead of modifying application rows or using real AWS.

Developer command (disposable test database only):

```bash
.venv/bin/pytest tests/test_import_recovery.py tests/test_import_flow.py \
  tests/test_import_worker.py tests/test_sqs.py -q
```

## Limits and follow-up

Executed on2026-10-22: focused import/worker/queue suites **36 passed** before one
additional retry regression. Final full backend **1032 passed** (95.82s), including
all12 new recovery cases; full frontend **225 passed**. Python AST, diff and local
documentation links passed. Frontend code was unchanged in this slice, so the
preceding lint/build result (about521KiB chunk warning) was not rerun. No tests
failed in this recovery slice. Tests use disposable schemas and mocked SQS/storage.

The existing worker and PostgreSQL must be running. A live process holding its
lock indefinitely is intentionally not stolen. Two probes can select the same
candidate; the processor's lock/state recheck decides ownership. Database and
queue notifications can cause duplicate delivery, not duplicate permission to
write. Persistent failed jobs require explicit review/retry rather than looping.

Real AWS IAM/network behavior, retention/DLQ/redrive and deployed worker restarts
remain unverified. No new AWS resource, paid AI, personal archive, dependency,
schema or startup service was introduced. Durable DB rows avoid an outbox table
for this bounded import flow; revisit if measured delivery/capacity needs exceed
the existing-row reconciliation. Overall Phase4 remains open.
