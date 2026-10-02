# Phase 2.2 — Verify source history and policy

## Start locally

Stop an older API/worker before upgrading, then restart them with the new code:

```bash
docker compose up -d db seaweedfs
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

In another terminal:

```bash
.venv/bin/python -m app.workers.import_worker
```

In `frontend/` run `npm run dev`, then sign in at
<http://localhost:5173/login>. Open **Entries**, **Import**, and **Sources**.
The Phase 2.1 HTML previews are access/coverage evidence; they do not ingest
history or show Phase 2.2 behavior. Full Codex/GitHub collection remains 2.3/2.4.

## One disposable browser walkthrough

Use your existing account email; the helper asks for the password without echoing
or saving it. It creates labelled synthetic data only, through the local API:

```bash
.venv/bin/python scripts/seed_history_demo.py --email YOUR_LOGIN_EMAIL
```

The printed Entry URL is the starting point. The helper does not read Codex or
GitHub history, execute its example command, upload to AWS, or call an AI service.
It creates four synthetic snapshots and replays one; generated small Markdown/ZIP
fixtures stay under ignored `.local/verification/phase22/`.

| Where/action | Expected result |
| --- | --- |
| Open the printed Entry URL | `CURRENT synthetic text` appears, with a review warning; source content has no Edit button |
| Personal annotation → Save annotation | Your note changes independently of the imported text |
| View history and provenance | Four versions, exactly one Current; replay created no fifth version |
| Inspect version 1–4 | Initial, newer current, older, and partial text; parser, times, SHA-256, original identity and structured evidence are visible |
| Inspect partial snapshot | Completeness is partial; unknown command output/exit stays null, never “passed” |
| Use as current on a retained version | Confirmation; current body changes, other versions and annotation remain |
| Mark unavailable | Content remains; status is unavailable, with no claim of deletion |
| Mark confirmed source deletion | Confirmation; content remains; list shows deleted-at-source status |
| Entries → Source status filter | All retained records includes source deletions; deleted selects them, available excludes them |
| Sources → codex / verification | Collection and external AI are separate; source AI starts off |
| Record AI checkbox | Record permission is separate; both source and record must allow. No AI endpoint is connected |
| Delete synthetic Entry → Confirm delete | All its versions/annotation disappear; Sources lists its stable identifier as blocked |
| Re-submit the same source ID | HTTP 409; re-running the helper uses a fresh ID and is a new synthetic record |
| Sources → Allow reimport | Explicit confirmation removes the block; content is not restored; the next import starts record AI disabled |

To check exact-original purge with a shared ZIP, use **Import → ChatGPT ZIP** and
choose `.local/verification/phase22/shared.zip`. Wait for the two entries. Delete
one entry: the second Entry's text remains, but both original-download links
return HTTP 410. **Sources → Original-file purge** shows pending objects until
the worker removes the ZIP. Reupload the same ZIP: the deleted conversation has
a visible `POLICY_BLOCKED` item error, the remaining logical Entry is deduplicated,
and the newly uploaded ZIP is also blocked/purged. A blocked original cannot be
retried; explicitly allowed records require a fresh upload.

For Markdown, upload `demo.md` twice: one Entry and one version. To track edits,
use an explicit **Document ID**, e.g. `phase22-document`, on every upload and give
a verified **Source modified time**. A newer complete version replaces current;
older/unknown-time edits are retained for review. Without a Document ID, byte-
identical content is the identity; changed bytes are a separate document.
Deleting this fixture blocks the same ID/content on subsequent uploads before
object storage. Use Sources → Allow reimport to remove that block deliberately.
Manual notes still have Edit and retain their observed edit versions.

## Semantics and boundaries

- Identity is owner/provider/external ID; source scope is immutable. GitHub
  adapters must use stable repository ID as scope and combine it with source
  object identity. All scoped denies use that identity; a rename is not a new
  repository. The shared snapshot API is authenticated; collectors must sanitize
  and truncate before sending. It is an ingestion contract, not a collector.
- Hash covers normalized text/type/title/event time, structured payload and
  completeness. Source timestamps do not create a version when content/evidence
  is unchanged. An unchanged current observation advances the freshness frontier.
  Changed candidates only replace current when source time is strictly newer and
  completeness does not decrease. Missing/equal/older time requires owner review.
  Replaying a retained candidate preserves the owner's current selection.
- A completeness upgrade is new evidence, even if displayed text is identical.
  ChatGPT `complete` means the supported active-branch text scope, not every
  branch, media item, or tool output. `chatgpt-active-text-v1` labels this boundary.
- Existing Entries receive one `initial-observed-v1`, unknown-completeness, legacy
  version. Source modification time/previous history are not invented. A matching
  replay is deduplicated against that observed text. Known Markdown gets a byte
  hash ID; pre-existing identical duplicate rows are preserved independently with
  `legacy:<entry-id>` identities, rather than silently merged.
- Exact uploads are linked through artifacts; sanitized capture payloads are
  retained in version JSON. Every repeated upload is linked for later purge,
  even when it creates no version. Old unlinked uploads cannot be retrospectively
  attributed safely. Source-deletion markers are owner-confirmed in this slice;
  a fetch/auth/rate-limit failure must become unavailable/unknown in later adapters.
- Default local search includes all retained source states; it searches current
  content, not old versions or annotations. Lifhop-deleted Entries have no rows
  or versions to retrieve. External AI excludes confirmed source deletions unless
  the caller explicitly includes them and both permissions allow.
- External AI starts off at source **and** record levels. Collection excludes
  future imports but does not erase existing local records. Collection and AI
  permission are independent. Existing denies/annotations survive every upsert.
- `app.services.ai_policy` checks every dependency immediately before remote
  embeddings/reranking/summary/answer/telemetry transport. Derived contexts must
  supply all source-version dependencies; empty/unknown provenance is denied.
  Owner content/policy revisions invalidate prepared work and cached results.
  Future AI/derived-cache callers must use this boundary and revalidate before
  publishing/reusing. No remote model or persistent AI cache/job exists yet.
  Already sent content cannot be unsent. Keyword search has no AI egress.

## Deletion and retention policy

A lifhop delete removes normalized bodies, every version, annotations, and
attachment metadata in its committed transaction. A minimal owner/provider/ID
ledger remains. The owner transaction lock serializes deletion, collection,
policy changes, and egress; workers reacquire it before each durable batch.
Suppression is checked per item and again under that commit-held lock.

Raw artifact downloads are blocked immediately. An original ZIP is indivisible:
remove the entire object if any member is deleted, while retaining other Entries'
normalized text/version history. Already issued download links can work until
object removal or their 10-minute expiry. Attachment PUT links can upload again
until expiry, including after completion; their final purge waits 11 minutes.

A durable PostgreSQL outbox lets the existing worker delete originals and retry
failures every 60 seconds. Pending counts/failures are visible in Sources. When
it succeeds, raw filename/key/size metadata is scrubbed. Local SeaweedFS deletion
was integration-checked with synthetic content. AWS versioned deletion removes
exact-key versions and delete markers across pages; partial API errors stay
pending. Required future AWS permissions include `GetBucketVersioning`,
`ListBucketVersions`, `DeleteObject`, and `DeleteObjectVersion`. Object Lock/MFA
or denied permissions remain visible failures, never successful purge.
See [Boto3 version listing](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/list_object_versions.html)
and [version deletion](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/delete_object.html).
Actual AWS permissions/deletion remain unverified until deployment.

Target content-backup maximum retention is **30 days** from backup creation;
expiry must include database/object versions, replicas and copied archives.
Automatic backups and expiry are not provisioned in this local slice. Deployment
must enforce/verify this target before promising backup purge. PostgreSQL storage
pages/WAL may retain overwritten bytes until their own rotation; logical deletion
is not disk secure-erasure. Source originals outside lifhop are never deleted.

Before taking backups and after deletion/explicit reimport changes, keep the
latest minimal ledger separately from content snapshots:

```bash
.venv/bin/python -m app.workers.deletion_ledger export .local/deletion-ledger.json
```

Stop API/workers when restoring, restore into isolation, run migrations, then
apply the **latest** ledger before restarting collection/serving:

```bash
.venv/bin/python -m app.workers.deletion_ledger apply .local/deletion-ledger.json
```

Run the purge worker and verify pending objects/policies before serving restored
content. Ledger rows remain after Allow reimport so an older backup cannot restore
pre-deletion content; only new explicit imports are allowed. Preserve matching
owner IDs. Current source/record denies must be reapplied before enabling AI;
keep restored AI disabled until policy freshness is verified. A backup without
the latest ledger cannot safely be served. Deployment must automate ledger/policy
journaling and expiry/restore tests in Phase 5; manual export is the local operator
procedure. Ledger files are private, mode 0600, and excluded from Git.
