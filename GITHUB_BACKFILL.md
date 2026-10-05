# GitHub historical backfill — Phase 2.4A

Commits and selected Markdown documents can be collected manually into lifhop.
Preparation only performs GitHub GET requests and writes a private local preview.
Apply is a separate authenticated action. PRs, reviews, issues and comments belong
to Phase 2.4B, after owner verification of this slice. No AI, worker, S3 or queue
is needed for this collector.

## 1. Quick browser verification with synthetic records

Start PostgreSQL and the local backend/frontend as described in `frontend/README.md`.
No new migration or dependency was added. From the repository root:

```bash
.venv/bin/python scripts/seed_github_demo.py --email YOUR_EMAIL
```

Enter your local lifhop password at the prompt. This creates **two disposable
synthetic records** in a separate source per invocation. It does not fetch GitHub
or execute the recorded diff. The repository and source links are fictional.

At `http://localhost:5173`:

1. Open **Sources**, choose **GitHub** under Backfill source. The newest run shows
   one commit, one document snapshot, two new records and Completed. Pinned head
   and history-walk status are visible; there are no session/turn counts.
2. Open **Search**, choose **GitHub**, search `Synthetic historical README`.
   Open the commit result. Expand Recorded file changes to read the diff.
3. Follow **Records from this commit** to the README snapshot. Confirm its commit,
   blob, historical snapshot notice and content. Back to search preserves filters.
4. Write a personal annotation; open View history and provenance. Imported source
   text is read-only. External AI is disabled by default and source/record controls
   are independent. Delete the two demo Entries individually when finished.

## 2. Choose a real repository and prepare

The selected repository is `moonkongv2/jy_yamyam`, default branch `main`.
Optional credentials come from the `GITHUB_TOKEN` environment variable or an
explicit `--github-cli-auth` selection of an existing GitHub CLI login;
never put a token in config, command arguments, Git, screenshots or chat. For
private repositories, provide access limited to that repository with Contents
read permission. Real private/organization SSO access remains unverified.

```bash
.venv/bin/python -m app.collectors.github init-config \
  --repository moonkongv2/jy_yamyam \
  --branch main \
  --config .local/github-collector.json \
  --run-dir .local/github-backfill
```

To reuse an existing GitHub CLI login without copying a token into your shell:

```bash
gh auth login --hostname github.com --git-protocol https --web
.venv/bin/python -m app.collectors.github prepare \
  --config .local/github-collector.json \
  --run-dir .local/github-backfill --github-cli-auth
```

The collector reads the CLI credential into memory for its repository GETs; it
does not print or save it. A switch between anonymous and authenticated reads
rechecks the corresponding quota instead of retaining the other bucket's wait.
Configuration, pinned heads and record identities stay fixed.

The init-config command resolves the numeric repository ID. Review the config
before preparation:
branches, document patterns (`README.md`, `ROADMAP.md`, `DECISIONS.md`,
`docs/**/*.md`), exclusions and budgets. Configuration is fixed for a run.

```bash
.venv/bin/python -m app.collectors.github prepare \
  --config .local/github-collector.json \
  --run-dir .local/github-backfill
```

Each selected head is pinned to a SHA. All reachable commit pages and each
commit's file pages are walked. Added/modified/renamed selected documents are
read at that commit, and deleted files remain commit evidence. Head baselines
fill documents whose path/blob snapshot was not already captured in the reachable
history. Symlinks/submodules, external downloads and LFS content are not followed.

When paused, the command prints a reason and `retry_at` (Unix seconds). Re-run
**the same prepare command** after quota reset. Cached GETs and completed items are
reused; a fresh run gets fresh heads. Network/5xx retries are limited to three.
No process sleeps until the hourly quota resets. Unknown failures and repository
identity changes are not silently treated as successful coverage.

A completed preparation creates `preview.html` and a sealed `manifest.json`.
Open the HTML locally and inspect linked sanitized JSON: messages, patches,
document content, dates, omissions and excluded material. Files are private and
`.local/` is ignored by Git. Raw responses in `cache/` are private too and **are
not guaranteed sanitized**. Do not serve this directory on an external network.

If you deliberately want only the prepared part:

```bash
.venv/bin/python -m app.collectors.github seal \
  --config .local/github-collector.json \
  --run-dir .local/github-backfill --partial
```

This fixes the partial bundle and stops further preparation in that directory.
Use a new directory for subsequent collection. Incomplete preparation cannot be
applied without explicit sealing. Partial/omitted evidence has gaps; receipt
completion does not imply full source coverage.

## 3. Apply a reviewed preview

Backend on `http://localhost:8000` is required. Frontend is required only to browse.
After reviewing the sealed preview:

```bash
.venv/bin/python -m app.collectors.github apply \
  --config .local/github-collector.json \
  --run-dir .local/github-backfill \
  --email YOUR_EMAIL
```

Enter the local lifhop password. Apply validates the preview before login, checks
collection/deletion policy before sending each body, and saves durable server
receipts with Entry/version changes. Re-running the same apply resumes or replays
without creating duplicate Entries/versions. A new equivalent preview also
returns unchanged records; partial versions follow existing review rules.

The local checkpoint binds owner, API origin, provider/repository scope and the
preview/parser/filter digest. To use another lifhop account, prepare a new run
directory. Do not edit the checkpoint to bypass the binding.

Sources displays the repository, pinned heads, prepared commits/documents,
lower-bound counts, run outcome totals and gaps. Search supports GitHub source
and event dates. Commits show message, author/committer dates, parents, per-file
diffs and patch state. Documents identify their commit/blob and snapshot reason.
Related links include current records from the same commit owned by your account.
Legacy GitHub canonical documents fall back to the plain-text reader.

## 4. Limits and cleanup

Defaults: response 8 MiB, document 1 MiB, wire item 1 MiB, field/patch 64 KiB,
cache + item files 256 MiB, journal 32 MiB, 100,000 items/commits, 1,000 pages,
1,000 GET requests and 600 seconds per invocation. The journal/HTML/manifest
also consume disk outside the cache/item budget. File evidence is retained within
half the wire budget before final encoding checks; remaining files can still
supply selected documents. Truncation, missing patches, tree/API caps and invalid
selected documents remain explicit gaps or body-free failed outcomes. The GitHub
3,000-file cap cannot establish that a commit's file coverage is complete.

All reads are sequential. A preparation budget can pause collection; changing
fixed config requires a new run. Anonymous API access may take multiple quota
windows for a repository of several hundred commits. Tokens increase the usable
quota but do not guarantee full coverage. Source exclusions/redaction are not a
proof that every secret was removed: always review private previews.

To explicitly remove the recognized private files from a run after verification:

```bash
.venv/bin/python -m app.collectors.github cleanup \
  --config .local/github-collector.json \
  --run-dir .local/github-backfill
```

Cleanup refuses unrelated files/symlinks. It leaves the lock file and config;
it does not delete server Entries or GitHub content. It removes the local preview,
raw cache, preparation journal and apply checkpoint, so keep them if you need to
resume or audit that run.

## 5. Checks and actual preview (2026-10-05)

Automated backend tests use a fresh migrated schema in the isolated PostgreSQL
test DB, including real loopback HTTP apply/replay. Synthetic cases cover commit
and file pagination, branch duplicates, pinned resume, omitted patch, symlinks,
submodules, nested document globs, invalid document outcomes, strict provider/
identity contracts, owner separation, deletion suppression, rate-limit errors,
redirect rejection, numeric repository Link paths and immutable preview checks.
Frontend tests cover provider switching, inert HTML, related Search links,
baseline labels, unsafe URLs and selected-version changes. A local Chromium
walkthrough covers Sources, commit/diff and document screens at
320/390/768/1440px with no horizontal overflow or page errors.

Actual selected repository ID: `1228467402`, pinned main head:
`c3107bc78ee7ac5e45a40023105eb89917d9ecd9`. Preparation is now finished for
**372 reachable commits + 43 historical document snapshots = 415 items**.
The anonymous run paused at 43 items, later reached 96, and resumed to completion
using the owner's explicit GitHub CLI login selection.

- Full sealed preview: `.local/github-backfill-20261005/preview.html`
- Config: `.local/github-collector.json`
- Earlier 43-item partial preview remains untouched in
  `.local/github-backfill-20261005-partial`; use the full preview for the first
  personal apply. They share a preparation UUID and cannot both replace the
  same owner's immutable server manifest. No personal account apply was run.
- Full-preview gaps: `PATCH_UNAVAILABLE`, `SENSITIVE_CONTENT_OMITTED`,
  `CREDENTIAL_REDACTED`. The selected history walk finished, while evidence has
  omissions. Sources correctly finishes as **Partial**, with zero failed items
  in the isolated verification. No PREPARATION_INCOMPLETE gap remains.

Fresh GitHub GETs matched the oldest/latest commit messages and tree SHAs, and
the oldest/latest historical document blob SHAs and sanitized content. Git blob
hashes were independently recomputed for the document samples. Commit event
range: 2026-05-04 03:37:11 UTC to 2026-08-21 12:46:00 UTC. These are the selected
source's dates, not lifhop import times.

All 415 items were applied through a real loopback HTTP API into a fresh migrated
schema in `lifhop_test`: **415 Entries + 415 versions**. Same-bundle replay and
a new equivalent preview did not increase those totals. All 415 current evidence
responses were checked. Search/related records, annotation/AI-deny preservation,
owner boundaries and deletion suppression passed. All temporary schemas, APIs
and generated browser credentials were removed afterward. Development records
and their collection policies were not modified.

The real frontend used the isolated API responses without fixture responses.
390/1440px checks passed for Sources → Search → document → related commit →
Search return; document text matched stored evidence, with no page errors or
horizontal overflow. Private reports/screenshots are under
`.local/verification/github-actual-full`; reference comparisons are under
`.local/verification/github-evidence`. No real credential is in those reports.

To reproduce the actual HTTP/DB checks without applying to a development account:

```bash
docker compose -f compose.test.yaml up -d test-db
.venv/bin/python scripts/check_github_preview.py \
  --run-dir .local/github-backfill-20261005 \
  --config .local/github-collector.json
```

The check creates only its own schema in the hard-coded isolated test DB, verifies
database/schema before mutation, and cleans that schema on normal exit. It clones
the reviewed files into a private temporary directory for ACKs, so the original
preview is unchanged. `--hold-for-browser` is for agent verification: it keeps a
loopback API for up to 20 minutes, writing generated temporary login details to a
private `access.json`; the release-file path in that file ends the hold. Otherwise
the script performs all API/DB checks and cleans up immediately. PR/issue access,
private/org SSO and actual mobile devices remain unverified.

Final local checks: **276 backend tests**, **87 frontend tests**, frontend lint/build,
OpenAPI generated-file consistency and `git diff --check` passed. The backend
suite includes upgrading a fresh isolated PostgreSQL schema to migration head.
No new persistent schema was required. Synthetic preparation measured 102
commits + 102 document snapshots, 301 file rows per commit and two overlapping
branches: 622 fake GET calls, 4.93 seconds and 3.27 MiB peak Python allocations
under tracemalloc. This excludes a real HTTP reader/JSON response cache and is
not a production capacity estimate.

Initial sandbox attempts could not reach local PostgreSQL or launch Chromium;
approved execution succeeded. The in-app browser could not initialize because
its tool reported a missing `sandboxPolicy`; standalone local Chromium supplied
the synthetic UI checks. A build initially caught incomplete required fields in
a new test fixture; those fields were added and the build passed. Owner account apply and actual mobile-device checks remain pending; full selected
source preparation and isolated actual HTTP/browser checks are complete.
## Repository browsing checkpoint (2026-10-06)

Existing GitHub Entries require no recollection. Restart the API if it was started
without `--reload`; the Vite development frontend reloads changed code.
With PostgreSQL, API and frontend running, open `http://localhost:5173/entries`.
The collector/import worker is not needed for browsing already stored records.

1. Entries shows one card per retained repository, alongside Codex sessions and
   ordinary notes. Counts are retained commits, document paths and snapshots.
2. Open the card → **Commits**. Source/event dates descend, unknown dates come
   last; open a commit, expand a recorded diff, and use **Back to repository**.
   The selected page survives reload/new tabs and reader-sidebar navigation.
3. **Documents** groups paths. Choose a path, then an older snapshot to read
   its historical content. **All documents** returns to the path-list page.
   Path-list and snapshot-list page offsets are independent.
4. Search still finds individual records. **Browse repository** provides context
   and **Back to search** restores the original search. Direct record reading from
   Search retains its existing Search return.

`Latest retained snapshot` is the most recent stored observation by known event
date, not a promise of current GitHub or selected branch HEAD content. Renamed
paths remain separate. Partial evidence/version-review/source-deleted status is
visible; collection coverage and selected heads remain in Sources.

If your account has no GitHub data, create disposable synthetic records with:

```bash
.venv/bin/python scripts/seed_github_demo.py --email YOUR_EMAIL
```

It asks for the local lifhop password in your terminal, creates a fictional source
with one commit and one document, and prints the repository URL. Each invocation
creates a different disposable source. Actual reviewed source apply remains an
explicit separate command described above.

Backend/API tests cover owner scoping, grouping before pagination, metadata/version
changes, date ties/unknown dates, path/snapshot pagination and last-record deletion.
Frontend tests cover repository/search/sidebar navigation, independent pages,
URL validation, empty/error/retry states and cache invalidation. Actual-source
verification uses `scripts/check_github_preview.py` in a fresh isolated test schema;
private reports/screenshots stay under `.local/verification/github-repository-view`.

Final checks: 282 backend tests, 97 frontend tests, frontend lint/build, generated
API schema consistency and whitespace checks passed. Actual 415-item replay,
annotation/AI-deny preservation, ownership and deletion suppression passed in a
fresh isolated PostgreSQL schema; aggregate results show 372 commits, 13 paths,
43 snapshots. Real HTTP Chromium browsing/search/reader/sidebar/reload/new-tab
checks passed at 320/390/768/1440px. Disposable schemas/API processes were cleaned
up. The initial browser transport teardown errors were verification-script issues;
waiting for pending requests and handling navigation cancellation resolved them.
Personal account apply, owner confirmation and actual mobile/other engines remain
unverified. No real source fetch, user DB migration or external AI was required.
