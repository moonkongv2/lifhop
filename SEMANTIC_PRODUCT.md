# Semantic storage checkpoint

Current direction: `SEMANTIC_PRODUCT_PLAN.md`. This checkpoint adds the storage
and lifecycle foundation. It does not expose Semantic search or start an indexing
worker. No personal documents or questions are sent by this checkpoint.

Verified on 2026-10-11: 424 backend tests passed, including 15 new storage tests.
Development head is `f48d3e25c064`; all 15 pre-existing data-table fingerprints
were preserved across the upgrade. Backup/restore, upgrade/downgrade and vector
dump/restore checks passed. Private backups are in
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
- Vector publication and selection helpers are internal storage operations. No
  production endpoint or paid caller is wired to them in this checkpoint.

## Reproduce the synthetic checks

```bash
docker compose -f compose.test.yaml up -d --wait test-db
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test .venv/bin/pytest tests/test_embedding_store.py -q
```

Expected: 15 passed. This uses a disposable schema, synthetic vectors and no
OpenAI request. Full regression uses the same command with `tests/test_embedding_store.py`
omitted. The test DB uses a separate port and tmpfs; development records are not
test fixtures. Current schema can be checked with `.venv/bin/alembic current`;
expected revision after this checkpoint is `f48d3e25c064 (head)`.

There is no new browser control to verify yet. Next is explicitly activated
indexing with a dry-run scope/cost preview and a durable worker, then API/UI.
The untouched ten-case quality check follows product integration under a separate
paid-transmission approval. Rerank diagnostics remain deferred.

Sources checked during implementation:
[pgvector Docker/install documentation](https://github.com/pgvector/pgvector#docker),
[SQLAlchemy adapter](https://github.com/pgvector/pgvector-python#sqlalchemy).
