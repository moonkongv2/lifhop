# Semantic search, storage and indexing

**2026-10-18 compatibility boundary:** `current-passages-v2` and its new storage
configuration require local projection rebuild and fresh, separately approved
embedding indexing. Old vectors are unavailable to current retrieval; old
follow-change approvals cannot enroll new work. Validated Codex/GitHub primary
event text now qualifies within both source and record permissions. Earlier real
indexing results below describe the previous configuration. See
[AI_SOURCE_COVERAGE.md](../design/AI_SOURCE_COVERAGE.md) before running activation commands from this document.

Current direction: [SEMANTIC_PRODUCT_PLAN.md](../plans/reference/SEMANTIC_PRODUCT_PLAN.md). Storage/lifecycle and explicitly
activated indexing and Semantic Search API/UI are implemented.
No personal document or question was sent during implementation verification.

Verified on 2026-10-11: 474 backend tests passed, including 15 storage, 29 indexing
and 21 Semantic HTTP tests; 122 frontend tests, lint/build and generated API types passed.
Development head is `g59e4f36d175`; all 16 pre-existing data-table fingerprints
were preserved across the indexing upgrade. Earlier storage backup/restore,
upgrade/downgrade and vector dump/restore checks passed. Private backups are in
`.local/backups/semantic-storage-20261011/` and must not be committed.

## Environment and schema

Both compose files pin the official pgvector PostgreSQL 17 image by digest:
`pgvector/pgvector:0.8.7-pg17-trixie`, PostgreSQL 17.11, pgvector 0.8.7.
It matches the development database's PostgreSQL major/minor, Debian family and
`/var/lib/postgresql/data` location. The `postgres_data` volume is retained.
The `pgvector==0.4.2` Python adapter provides the SQLAlchemy vector type and
cosine operator; its NumPy dependency handles vector conversion.

Migration `f48d3e25c064` follows the rerank usage migration. It checks extension
availability, enables `vector` in `public` when permitted, and creates the
`passage_embeddings` table. Restricted DB roles must have an administrator run:

```sql
CREATE EXTENSION vector WITH SCHEMA public;
```

An unavailable server extension produces an actionable migration error. Downgrade
removes only the new derived table and retains the shared extension. Test schemas
use `search_path = <isolated schema>, public` to resolve vector types/functions.

For another development checkout, install dependencies and upgrade after backing
up existing data and validating restore on the target image:

```bash
uv pip install -e '.[dev]'
docker compose up -d db
.venv/bin/alembic upgrade head
```

Before replacing an existing DB container, create a private backup (choose a new
filename each time), keep it outside Git, and verify restore in a separate DB:

```bash
mkdir -p .local/backups
chmod 700 .local/backups
umask 077
docker compose exec -T db pg_dump -U lifhop -d lifhop -Fc --no-owner --no-acl > .local/backups/before-semantic.dump
```

Do not use `docker compose down -v` for this upgrade. Keep the previous image and
backup until verification is complete. An image replacement can briefly interrupt
open DB connections; restart an API or worker that does not reconnect.

## What storage guarantees

- Vectors have 1536 dimensions and reference exact deterministic `sections-600-v1`
  body subranges, with parent ID/hash, absolute offsets, slice hash and config.
  Source text is not copied into the vector table. Parent deletion cascades.
- Publishing rechecks owner, current passage, source AND record AI permission,
  source deletion and policy revision under the existing owner lock. Entire
  batches are validated before insertion; repeated publication is idempotent.
- Current-version selection/edit, record/source deny and confirmed source deletion
  clean invalid vectors in the source transaction. Reallow cannot restore a
  removed vector. Queries also join live policy/current-index state independently.
- Float32 conversion rejects non-finite, wrong-sized and zero/underflow vectors.
  Different model/config rows cannot enter the current eligible query.
- Vector publication and selection helpers enforce these checks for the indexing
  worker and optional Semantic search too.

## Search flow and owner verification

Search keeps Exact phrase/Passages and adds Semantic. Enter a question and choose
filters, then press `Review index`. This only fetches local filtered coverage;
no question is included in that GET. Stored slices/records and indexing job counts
are shown, including that coverage may be partial. With no allowed stored slices,
the paid search action stays disabled and no question is sent.

Check `Send this question to OpenAI for this search`, then press `Search with OpenAI`
to make one explicit question-embedding POST. The query route searches stored vectors
locally, with current source/record permissions and exact cosine ordering. It sends
no document text and generates no answer. Results are limited to 20 groups without
an Entry quota; grouping identical verified GitHub document slices happens first.
View passage opens the exact source subrange/version. Retained-location reads apply
the same live policy/filters without requiring lexical question matches.

The screen never automatically repeats a paid query on focus, return, reload or
filter change. Results are kept only while this screen is mounted; returning restores
filters and requires another explicit submission for a fresh result. The same request
ID cannot make a second possible paid call; query vectors are never persisted.
Refresh index status rechecks local permissions and hides stale results. Failed status
or reader revalidation also hides cached evidence. Budget/disabled/busy/timeout states
are distinct; a dispatched request may have been charged even when results fail.

Before the approved real run, the development account had zero vectors. It now
has 1,031 ready slices from 43 allowed GitHub documents. On
`http://localhost:5173/search`, log in as `b@test.com`, choose Semantic, filter
Source to GitHub and Type to Document, and select Review index. Expected:
44 matched records, 43 allowed/indexed records and 1,031 ready slices. The
separate paid question action remains optional and incurs a new call.

### Synthetic demo with no OpenAI transmission

The owner demo is at `http://127.0.0.1:5174/search`, using a separate API on 8002.
Login with `demo@example.test` / `demo-password`. These are disposable synthetic
credentials. The demo's isolated test-schema JWT secret differs from the real app.

1. Choose Semantic, enter `where does the worker run`, and press `Review index`.
   Expected: two stored slices in two synthetic records; paid button disabled until consent.
2. Check the question-send box and press `Search with OpenAI`. In this demo that
   call is mocked. Expected: two result cards; Worker location appears first.
3. Open its passage. Expected: the synthetic deployment-server sentence and exact
   version/character range. Return to Search: filters remain, results clear and no
   paid POST repeats. Reload has the same no-auto-send behavior.
4. Choose Source = GitHub, review again. Expected: no matching stored slices and
   disabled paid action. Return to All sources to restore availability.

This verifies behavior, not model quality. The demo only uses a fresh schema in
the test database and never reads or modifies development records. Normal shutdown
removes its schema; hard termination can leave a disposable schema. Screenshots
and metadata are private under `.local/verification/semantic-demo/`.

To restart the demo after stopping it:

```bash
docker compose -f compose.test.yaml up -d --wait test-db
.venv/bin/python scripts/preview_semantic.py
```

In another terminal, from the `frontend` directory:

```bash
LIFHOP_API_PROXY_TARGET=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Keep the two demo processes running while checking it. The demo script creates
and indexes its two records with a mock provider; no standalone embedding worker
is needed for this verification. Stop each process with Ctrl+C after review.

Search endpoints: `GET /semantic/status`, `POST /semantic/search`,
`GET /semantic/slices/{id}` and `GET /semantic/slices/{id}/locations`.
They require owner authentication. Search requires a unique 32-hex request ID,
`confirm_external_ai: true`, question and optional source/type/date filters.
Unsupported extra body fields are rejected. Empty filtered indexes return coverage
without calling the provider. Each query is bounded to 256 characters/2048 UTF-8
bytes and the shared monthly budget; replay/busy return 409, budget 429, provider
failures 503 and missing consent 403. Policy changes before/after dispatch return
409 and successful usage remains settled.

## Preview and activate indexing

The API/CLI operate on authenticated owners. A preview reads allowed current body
slices, stores only IDs/hashes/offsets/byte counts in a private manifest, and creates
no job or paid request. Both source and record AI permissions must already allow
the data. Changing permissions is a separate action and still does not activate a run.

With the development database running, check the scope locally:

```bash
.venv/bin/python scripts/index_embeddings.py --dry-run --email b@test.com --provider github --scope repo:1228467402 --max-cost-usd 0.05 --max-calls 100
.venv/bin/python scripts/index_embeddings.py --status --email b@test.com
```

Enter the lifhop password in the terminal prompt. The first command prints
`allowed_records`, `indexed_records`, `ready_slices`, `pending_slices`, the maximum
estimated cost in micro-USD, the shared month exposure, and a private manifest path.
Selected record count can exceed allowed record count because it includes excluded
records in the scope. `--entries 123,456` restricts activation to explicit Entry IDs.

For a one-shot subset of a long record, add `--passages 789,790` together with
`--entries`. The API equivalent is `passage_ids` in `POST /indexing/preview`;
the reviewed manifest binds `selector_passage_ids`. Every selected parent must
belong to the explicit Entries and be current, owned, eligible and AI-allowed.
Unknown, duplicate, stale, denied or out-of-scope IDs fail before source inputs
are prepared. Only those parents' existing Semantic slices become jobs.
Passage selection cannot use `--follow-changes`; updates require a fresh preview
and approval rather than silently enrolling the rest of the Entry. This needs no
schema migration. Legacy manifests omit the new selector and keep their digest
and idempotent CLI/API replay contract.

This selects indexing work; it does not grant AI permission or introduce a
range-level policy system. Record/source AI flags still apply to Entries. Inspect
the complete selected parent text: its boundaries may exceed an earlier excerpt
review. Do not use an excerpt-only read grant as whole-record transmission consent.
The second command lists only this owner's runs; `[]` is expected before activation.

Metadata-only verification of the previously allowed 43 GitHub documents found
43 allowed/indexed records, zero ready slices, 1,031 pending slices, and an estimate
of 8,113 micro-USD (USD 0.008113). This is a conservative reservation estimate, not
an actual provider bill. The explicit 43-ID manifest is stored privately in
`.local/indexing/`. This paragraph describes the pre-activation checkpoint;
the approved run has since completed and should not be activated again.

After separately approving the exact scope and budget, activation is:

```bash
.venv/bin/python scripts/index_embeddings.py --activate --email b@test.com --manifest .local/indexing/preview-DIGEST.json --confirm-external-ai
```

Replace `DIGEST` with the fresh preview's filename. Activation checks the manifest
against the current owner/database/policy/content, then creates durable jobs.
`INDEXING_MANIFEST_STALE` requires a new preview and review. Repeating the same
activation returns the same run and does not reset its counters or resend work.
With a running worker, activation can immediately start sending approved body text.

Default activation covers the current snapshot. Add `--follow-changes` to the
dry-run only when also approving future eligible records/edits in that selector.
Without `--entries`, future enrollment covers the entire provider/scope; with IDs,
only those IDs follow changes. The same cumulative run budget/call cap applies.
Overlapping follow scopes in the same configuration, including paused ones,
cannot be activated again. Old-configuration runs require fresh scope approval.
Past experiment approval and `.env` alone never enroll records.

## Worker, status and recovery

```bash
.venv/bin/python -m app.workers.embedding_worker --once
.venv/bin/python -m app.workers.embedding_worker
```

The first command processes at most one batch; the second polls continuously.
This is separate from `app.workers.import_worker` and should use the same database,
provider credentials and billing scope as the API. For local development it runs
in a separate terminal while approved work is pending. Existing stored vectors
do not require a worker to remain running. Server supervision/deployment is future work.

Each batch contains at most 16 slices/16,000 UTF-8 bytes. The shared ledger reserves
cost before dispatch, the current-policy gate guards HTTP, and publication guards
the current version/policy again. Currently allowed identical same-owner text may
reuse a stored vector. No response body, input text or provider key is logged by
the worker. No HTTP retry is automatic. Mode off, missing key, monthly/run budget
exhaustion or call-cap exhaustion pauses the run with pending work and a safe code.

After activation, replace `RUN_ID` with the printed run ID:

```bash
.venv/bin/python scripts/index_embeddings.py --status --email b@test.com --run RUN_ID
.venv/bin/python scripts/index_embeddings.py --jobs RUN_ID --email b@test.com
.venv/bin/python scripts/index_embeddings.py --pause RUN_ID --email b@test.com
.venv/bin/python scripts/index_embeddings.py --resume RUN_ID --email b@test.com
```

Status shows ready/pending/running/blocked/stale/failed/uncertain counts, spent
and outstanding micro-USD, and caps. `completed` means this snapshot has no
pending/running work; examine the counts because failed/blocked jobs can remain.
Following scopes remain active when idle. Pause/resume/retry never resets counters;
resume catches up current allowed edits made while a follow scope was paused.
A dispatch already in flight can finish after pausing. Denied/deleted/currently
unmapped content is never eligible. Reallow does not restore old vectors or silently
retry an old blocked job; current eligible work needs an explicit retry or new activation.

A 60-second lease allows crash recovery. Work with no attempt or a proven released
pre-send attempt can return to pending. A possible request remains `uncertain`.
A paid response lost before publication remains `failed / INDEXING_RESULT_LOST`.
Neither automatically retries. Inspect usage without reading source text:

```bash
.venv/bin/python scripts/index_embeddings.py --usage --email b@test.com --run RUN_ID
```

For uncertain usage, stop the affected dispatch first and verify provider billing.
The existing authenticated ledger reconciliation supports conservative maximum
settlement or a verified no-charge release. For example, conservatively settle:

```bash
.venv/bin/python scripts/check_semantic_retrieval.py --settle-max ATTEMPT_ID --email b@test.com --confirm-settlement
.venv/bin/python scripts/index_embeddings.py --retry JOB_ID --email b@test.com --confirm-external-ai
```

Retry may send the text again and charge again. It requires current policy/anchors
and settled previous usage, and stays within the original cumulative caps.
An old job whose passage/version disappeared cannot be retried; preview current work.

Endpoints mirror the CLI: `POST /indexing/preview`, `POST /indexing/runs`,
`GET /indexing/runs`, `PATCH /indexing/runs/{id}`, `GET /indexing/runs/{id}/jobs`,
and `POST /indexing/jobs/{id}/retry`. They require the owner bearer token; activation
and retry require `confirm_external_ai: true`. Preview database failures return a
safe 503 code without database/private input details. HTTP DTOs and generated types
are explicit; indexing activation remains a CLI/API action rather than a Search button.

## Reproduce the synthetic checks

```bash
docker compose -f compose.test.yaml up -d --wait test-db
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test .venv/bin/pytest tests/test_embedding_store.py -q
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test .venv/bin/pytest tests/test_embedding_jobs.py -q
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test .venv/bin/pytest tests/test_semantic_product.py -q
```

Expected: 15 storage tests, 29 indexing tests and 21 Semantic HTTP tests passed. This uses a disposable schema, synthetic vectors and no
OpenAI request. Full regression uses the same command with `tests/test_embedding_store.py`
omitted. The test DB uses a separate port and tmpfs; development records are not
test fixtures. Current schema can be checked with `.venv/bin/alembic current`;
expected revision after this checkpoint is `g59e4f36d175 (head)`.

The owner confirmed synthetic browser behavior on 2026-10-12. The separately
approved real indexing and ten-case check are complete. The real index now has
1,031 ready slices from 43 allowed GitHub documents; the ten-question product
POST check found exact support by rank 20 in 7/8 supported cases, compared with
5/8 for current Passages. Total OpenAI cost was USD 0.000889 (65 document calls,
10 question calls). One Korean case missed its exact support by rank 20, and
another found it only at rank 17. See the private body-free
`.local/verification/semantic-product-20261012/report.json` for case scores,
ranks and usage. The owner has yet to check the populated real index in the
browser; Phase 3.3 scope is to be decided after reviewing the limits.

## Local-only product evaluation preview

This authenticates locally, checks the immutable reviewed dataset, current evidence
and fixed indexing allowlist, and writes a private body-free protocol. It never
activates jobs, opens retrieval results or calls OpenAI. Questions appear only as
hashes and byte counts; answers/evidence are checked locally and never become
provider inputs. A stale indexing manifest requires another indexing dry-run.

```bash
.venv/bin/python scripts/prepare_semantic_validation.py \
  --email b@test.com \
  --set .local/evaluation/fusion-review-b7a96801f0474c19901d9f5cdc7159b6/validation \
  --index-manifest .local/indexing/preview-9d266e657ef73a77e415121d052eea4c6f544478d5a3d7a291069acf7eb89a1f.json
```

Enter the local account password at the terminal prompt. Expected: ten reviewed
cases (eight supported, two insufficient), 43 documents, 1,031 pending slices,
zero ready slices, total conservative estimate 8,139 micro-USD, and proposed hard
caps of 60,000 micro-USD / 110 calls. The monthly remaining amount is dynamic.
The `product-preflight/` protocol has `approved: false` and `provider_calls: 0`.
These were the limits proposed before the separate 2026-10-12 owner approval.
The approved run completed within them. Future changes and automatic retries
remain disabled. Re-running the old preview now reports a stale manifest because
the index has been filled; it must not be used to activate another run.

Verify the preview safeguards with:

```bash
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test .venv/bin/pytest tests/test_semantic_validation.py -q
```

Sources checked during implementation:
[pgvector Docker/install documentation](https://github.com/pgvector/pgvector#docker),
[SQLAlchemy adapter](https://github.com/pgvector/pgvector-python#sqlalchemy).
