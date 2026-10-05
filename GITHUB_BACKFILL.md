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
Optional credentials are read only from the `GITHUB_TOKEN` environment variable;
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

This resolves the numeric repository ID. Review the config before preparation:
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
`c3107bc78ee7ac5e45a40023105eb89917d9ecd9`. The inventory walk reached its end with
**372 reachable commits**. Anonymous quota paused preparation after **29 commits
and 14 document snapshots (43 items)**. Full real-source collection is pending.

- Resumable preparation: `.local/github-backfill-20261005`
- Separate, sealed partial preview:
  `.local/github-backfill-20261005-partial/preview.html`
- Shared config: `.local/github-collector.json`
- Partial gaps: `PATCH_UNAVAILABLE`, `SENSITIVE_CONTENT_OMITTED`,
  `PREPARATION_INCOMPLETE`. Counts are lower bounds. No personal apply was run.

To review/apply those 43 items, use the partial directory with the apply command
in section 3. To continue full collection, use the original directory with prepare.
The partial and complete previews share a preparation UUID because the partial
is a local snapshot copy: **choose one to apply**. If the partial is applied first,
create a fresh preparation directory for the subsequent complete server run;
the old server manifest is immutable. Earlier data will deduplicate by repository/
object identity. Private repositories, organization SSO, expired-token recovery,
very large repositories and AWS deployment remain unverified with real sources.

Final local checks: **274 backend tests**, **87 frontend tests**, frontend lint/build,
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
a new test fixture; those fields were added and the build passed. Full real-source
preparation, owner account apply and actual mobile-device checks remain pending.
