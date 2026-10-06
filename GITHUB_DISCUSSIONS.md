# GitHub discussions — Phase 2.4B

Collect accessible PRs, issues, general comments, reviews and code-review comments
from one explicitly selected repository. GitHub Discussions boards are outside
this slice. Collection is manual and read-only on GitHub. Apply stores filtered
text/evidence in PostgreSQL using existing Entry versions and durable receipts.
No S3 upload, queue, worker, AI call, dependency or migration is added.

## Quick browser verification with synthetic records

Run the usual local PostgreSQL, backend and frontend. If they are stopped:

```sh
docker compose up -d db
.venv/bin/uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
npm run dev
```

Use an existing local lifhop account. From the repository root:

```sh
.venv/bin/python scripts/seed_github_discussions_demo.py --email YOUR_EMAIL
```

Enter that account's local lifhop password. This creates a separate fictional
repository and 30 `[Synthetic]` records per invocation, with no GitHub request.
It prints the private preview/config paths and the exact browser URL.
The import worker is unnecessary for this text-only flow.

### What to check

1. Open the printed `http://localhost:5173/repositories/github?...&tab=discussions`
   URL. Expect **one PR and one issue**, rather than 30 rows in the discussion list.
2. Open **[Synthetic] Preserve the migration decision**. Expect a preserved
   parent decision and **27 comments/reviews**, paginated 20 at a time, oldest first.
3. Click **Next page**. Use **Read record** to inspect an empty APPROVED review,
   a PENDING draft with an unknown submission date, and two code comments.
   **Recorded code context** is folded by default; the reply retains its original
   comment ID and code location. The draft date gap makes this demo run Partial.
4. Search `discussion-focus-demo` with source GitHub. Click the result title.
   Expect the matching comment opened on **page 2**, then **Back to search**.
5. Follow **Open record and history**, inspect versions/annotation/AI controls,
   and return. Reload and opening the record URL in a new tab preserve the thread
   page and original Entries/Search return context.
6. In **Sources**, choose GitHub. Expect counts for PR/issue/general comment/review/
   code comment, the observation window and any gaps. Counts are prepared outcomes;
   they differ from current retained record counts after deletion.
7. Optional destructive check on these disposable records: delete the parent PR
   through its individual record page. Its comments remain, with **Parent not
   retained**. No parent body/title is reconstructed. Deleting a comment affects
   only that comment. Per-record reimport suppression remains active.

Related SHA links in the demo describe synthetic commits that are not retained
locally. Original links point to a fictional repository. Each invocation has a
new source ID, so repeated seeding creates a separate demo, not a replay check.

To inspect the demo before applying:

```sh
.venv/bin/python scripts/seed_github_discussions_demo.py --prepare-only
```

## Prepare real selected history

The selected source remains `moonkongv2/jy_yamyam`. Fresh authenticated inventory
and collector reads on 2026-10-06 found **0 PRs and 0 issues**. The sealed private
preview is `.local/github-discussions-20261006/preview.html`. Its page walk is
complete with no gaps; isolated HTTP apply/replay correctly finished Empty.
No personal-account apply was run. A nonempty public/private discussion archive
has not been verified against a live source in this slice.

For a new preparation, choose a fresh run directory. Do not modify the existing
2.4A config, previews or checkpoints. New B config is separate:

```sh
.venv/bin/python -m app.collectors.github_discussions init-config \
  --repository moonkongv2/jy_yamyam \
  --run-dir .local/github-discussions-NEW_DATE --github-cli-auth

.venv/bin/python -m app.collectors.github_discussions prepare \
  --run-dir .local/github-discussions-NEW_DATE --github-cli-auth
```

Run init-config only once: it refuses to overwrite the existing config.
Alternatively explicitly select `GITHUB_TOKEN` in the environment and omit
`--github-cli-auth`; tokens are never saved to config, preview or checkpoint.
Private/organization access needs the existing account's read permissions for
PRs and issues, with applicable SSO. No automatic login or permission changes occur.

Config supports `exclude_numbers`, `exclude_paths`, field/item/bundle budgets,
page/request limits and per-invocation time limits. Excluded code paths keep the
comment body but omit the path/diff. Review the filter output personally; the
secret filter is incomplete. Cached upstream responses may still contain private
unfiltered data, so keep the entire run directory private and out of Git.

Both open and closed objects are selected, regardless of A's branch scope.
Parents created after preparation starts are deferred to a subsequent run.
Lists/pages may change while read: this is an **observation over a time window**,
not an atomic source snapshot. A parent's changed edit clock triggers at most
one staged retry; otherwise the observation retains an explicit change gap.
Finished parents are not silently refreshed during a resumed preparation.

### Pause, resume and seal

On quota/time/request limits, the command prints a body-free pause reason and
retry time. Rerun the same prepare command and directory. Authentication quota
mode switches are explicit; do not create directories to bypass a quota deadline.
Permanent access/fetch failures are gaps, not confirmed source deletion.

Successful prepare automatically seals a preview. To deliberately seal an
unfinished preparation:

```sh
.venv/bin/python -m app.collectors.github_discussions seal \
  --run-dir .local/github-discussions-NEW_DATE --partial
```

Inspect `preview.html` and linked filtered JSON. Seal records exact hashes,
kind counts, observation window and omissions. It cannot be rewritten. Incomplete
or inaccessible data is Partial/Failed; a successfully inspected empty scope is Empty.
PR commit membership is explicitly incomplete when GitHub's endpoint cap or
counts prevent verifying all members; no other branch/fork is fetched automatically.

### Explicit apply after preview review

```sh
.venv/bin/python -m app.collectors.github_discussions apply \
  --run-dir .local/github-discussions-NEW_DATE \
  --email YOUR_EMAIL --api-url http://localhost:8000
```

Apply authenticates to lifhop. Checkpoints bind owner, API origin, source scope
and exact preview. Same-preview replay does not duplicate records or versions.
To use another account/API, use a separate reviewed preview; do not remove a
checkpoint to evade its binding. Server-side policy/deletion checks still apply
to already acknowledged items. A newly reviewed run is required after re-enable.

Each parent/comment/review is an independent Entry. Source edit dates control
current-version selection. REST reviews lack a verified edit clock; changed
reviews remain candidates needing explicit version selection. Submission time
and collection time are not substitutes for an edit date. Unavailable prior edits
and deleted source records cannot be reconstructed.

## Cleanup

Once a preview is no longer needed:

```sh
.venv/bin/python -m app.collectors.github_discussions cleanup \
  --run-dir .local/github-discussions-NEW_DATE
```

Cleanup validates the matching config, recognized paths and absence of symlinks;
it refuses unknown files. Keep config outside the run directory. The demo script
does this automatically. Cleanup removes local bundle/cache/checkpoint files,
not already applied lifhop Entries or the persistent config.

## Agent verification and limits

- Full backend: 297 tests passed. Full frontend: 104 tests passed; lint/build and
  whitespace checks passed. The existing sealed 415-item A preview still validates.
- Backend/frontend tests exercise source kinds, pagination, mutable resume,
  filters, empty/draft reviews, parent failures, PR commit limits, identities,
  old A serialization, receipts, replay, ownership, annotations, source pause,
  individual deletion, orphan dates, related SHAs and search focus.
- Actual 0-item preview and a 30-record synthetic bundle were applied/replayed
  through real HTTP in fresh migrated schemas within `lifhop_test`; personal DB
  and original reviewed directories were untouched.
- Synthetic Chromium against the real isolated API passed at 320/390/768/1440px:
  list/thread/reading, paging, reload, individual records, search return, Sources,
  no horizontal overflow or page errors. In-app browser initialization failed;
  standalone Chromium was used. Real mobile devices/other engines remain unverified.
- Scheduled collection, AI, whole-thread deletion, live nonempty/private/org
  source verification, very large corpus performance and owner browser confirmation
  remain follow-up. Source deletions are not automatically inferred.

Repeat the isolated checks using the disposable local test DB:

```sh
.venv/bin/python scripts/check_github_preview.py --discussions \
  --run-dir .local/github-discussions-20261006 \
  --config .local/github-discussions-collector.json \
  --report-dir .local/verification/github-discussions-empty \
  --test-database-url postgresql+psycopg://lifhop:lifhop@127.0.0.1:5433/lifhop_test
```

For the 30-record fixture, substitute the preview directory and external config
path printed by `--prepare-only`. The discussion branch of this verification
helper currently targets the empty selected source and that synthetic fixture.
`--hold-for-browser` retains the isolated API temporarily and writes private
access details for a browser check; its own schema/server are cleaned on exit.
Do not expose that API/access file or commit verification artifacts.

The usual frontend proxy target remains localhost:8000. A dedicated isolated
frontend can optionally set `LIFHOP_API_PROXY_TARGET` to the check API origin.
Never point an actual-account verification at a disposable test DB by accident.
