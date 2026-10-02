# Phase 2.1 — Acquisition and coverage checks

This slice verifies source reads and produces private local previews. It does
not create Entries, upload archives, run models, resume sessions, execute
captured commands, or start scheduled collectors. The CLI imports no application
settings or database/storage clients. No additional Python dependency is needed.

## Run and inspect

From the repository root with the existing `.venv`:

```bash
.venv/bin/python -m app.acquisition codex
.venv/bin/python -m app.acquisition github --repo moonkongv2/jy_yamyam
```

Each command prints aggregate metadata and an absolute HTML report path. Open
that HTML file locally in a browser; the adjacent JSON contains the same data.
Default output uses a unique directory beneath `.local/acquisition/`, excluded
from Git. Reports are private files (0600), contain sensitive selected content,
escape HTML, and refuse to overwrite existing files. They remain on your Mac for
review; temporary Codex snapshots are automatically removed. No API/worker,
PostgreSQL, SeaweedFS, AWS, or model credentials are needed for these commands.

Optional source selection:

```bash
.venv/bin/python -m app.acquisition codex --codex-thread THREAD_ID
.venv/bin/python -m app.acquisition codex --codex-home /path/to/.codex --cwd /path/to/project
.venv/bin/python -m app.acquisition github --repo OWNER/REPO --branch main --branch feature/example --document README.md --document DECISIONS.md
```

Additional GitHub branches/documents must be selected explicitly. Without a
branch option, only the default branch is inventoried. Without a document
option, the sample checks `README.md` at the sampled commit, not a current file
presented as historical content.

Public repositories work anonymously. For private repositories, provide an
existing `GH_TOKEN` or `GITHUB_TOKEN` in the local environment. Do not paste it
into a command or commit it. The current public sample needs no token. Local
`gh` was installed but not signed in; the connected GitHub app independently
confirmed repository access. Its credentials are not exported into the probe.

## Owner verification

1. Open the Codex HTML report. Check the original thread/item IDs, source date,
   ordered user/assistant messages, command outputs and exit codes, and file
   diffs/statuses. Missing output/exit codes remain unknown. The report excludes
   reasoning and unsupported tools and lists truncation/omissions explicitly.
2. Open the GitHub HTML report. Check repository identity, selected `main` head,
   commit message, author/committer dates, parents, two changed files and patches.
   Follow the original commit URL and compare the README at that same SHA.
3. Check coverage: inventory is broader than the single inspected sample.
   Other branches are listed but their commits are not collected unless selected.
   A page budget means a lower bound, never complete history. Access failures
   mean unavailable/unknown; they are not proof of source deletion.
4. The owner requested proceeding to Phase 2.2 without this preview check.
   Use `HISTORY.md` for current browser checks. Real Codex/GitHub collection is
   still Phase 2.3/2.4; these previews do not populate the archive.

### What to look at in the JSON-shaped HTML

You only need three sections; the inventory is context, not a checklist of all files.

| Report section | Owner check |
| --- | --- |
| Codex sample turns/items | Recognize one old question/answer; inspect one command's output/exit and one recorded diff. Null output means unknown, not successful execution. |
| GitHub `sample` | Match message and the two `files` patches with commit `c3107bc…`; `documents_at_commit` is README at that SHA. |
| `omissions` and coverage | Notice unavailable/truncated outputs and main-only scope. 372 enumerated commits does not mean every diff/document was ingested. |

The aggregate source-read checks were already executed by the agent. Owner
review asks whether the visible sample matches the history you recognize.
Phase 2.2's history/deletion/permission checks are in the application itself.

## Verified on 2026-10-02

| Source | Observed coverage and sample |
| --- | --- |
| Codex installed CLI | `codex-cli 0.158.0`; runtime schemas generated locally |
| Local inventory | 169 active-directory JSONL files, no archived-directory files; approximately 472 MiB at check time, including an active file that keeps growing |
| Session creation range | 2026-02-21 through 2026-09-30 UTC; metadata dates, not a guarantee of message coverage across that whole interval |
| Recorded CLI versions | 13 distinct versions, from `0.104.0-alpha.1` through `0.159.2`; inventory does not prove that every version's contents parse |
| Selected Codex sample | Existing lifhop session recorded by `0.149.0`, created 2026-08-22 UTC; 3 turns, 3 user messages, 11 assistant messages, 22 command items, 3 file-change items |
| Codex pagination | Two copied thread summaries read across two list pages; sample turns read across 3 pages in ascending order |
| GitHub repository | Owner-selected `moonkongv2/jy_yamyam`, repository ID `1228467402`, public, user-owned |
| Branch inventory | `main`, `yr_add_langs`, `yr_defer_motivation`; only `main` selected for history |
| GitHub history | 372 reachable commits at pinned `main` head; 4 API pages exhausted successfully |
| Sample commit | `c3107bc78ee7ac5e45a40023105eb89917d9ecd9`, 2026-08-21 UTC, 2 files with patches; README at this SHA available |
| Last returned ancestor | `b5479ad76a06c8aab728a061319a318db1d4ee21`, committer date 2026-05-04 UTC; Git history order does not promise chronological date order |
| GitHub authentication | Anonymous REST GET succeeded; no token expiry or organization approval applicable to this user-owned public sample |

The sample's recognizable credential patterns are redacted and text fields are
limited to 8,000 characters. Four Codex command items had unavailable output; large
command output and README previews were truncated. These are sanitized previews,
not exact uploaded originals. Secret redaction is incomplete and not a substitute
for Phase 2.3's exclusion/preview controls before any upload. Reports must remain
private and must not be sent to external AI.

Private repositories, organization SSO, expiring tokens, archived-session reads,
and every historical CLI version have not been verified with real owner samples.
HTTP failure and archived inventory behaviors have synthetic tests. The owner
preview check remains pending. No claim of full Codex/GitHub backfill is made.

## Selected methods and limits

### Codex

Prefer the documented app-server interface. It reads stored threads without
resuming them. Use `thread/list` for cursor pagination, `thread/read` for metadata,
and experimental `thread/turns/list` with full items for paginated history.
Legacy history uses `thread/read` with `includeTurns`. Explicit source kinds
avoid the default interactive-only filter; active and archived directories are
inventoried separately. Metadata parsing reads only the first bounded JSONL line
and is isolated in `app/acquisition/codex.py`.

Do not start app-server against the original Codex home: its normal list behavior
can scan and repair metadata. The probe copies up to two selected rollouts and,
for paginated history, backs up `thread_history_1.sqlite` through a read-only
SQLite connection. It runs app-server in that temporary `CODEX_HOME`. No auth,
config, state database, or unrelated local project files are copied. Read methods
are allowlisted. Source/copy hashes must agree; a changing selected rollout fails.
The snapshot DB is never written back. The history DB and rollouts are copied at
separate times, so this is not an atomic snapshot of an actively running session.
Select idle historical sessions.

The probe currently accepts installed CLI `0.158.0` only and records parser
version `codex-app-server-0.158.0-v1`. A new CLI/history DB format requires renewed
schema/sample checks; there is no silent unsupported-version fallback. Starting
from JSONL alone returned no turns for the paginated sample. The projection DB
and paginated RPC recovered the actual persisted items. Do not interpret an
empty legacy/full-history response as proof of an empty conversation.

Limits: 16 MiB per copied rollout, 256 MiB projection DB snapshot, 16 MiB RPC
response, 20 seconds per RPC/DB backup, and 20 pagination requests per list.
The full backfill's snapshot/checkpoint strategy remains Phase 2.3 work.

### GitHub

Use versioned REST GET (`2026-03-10`) with stable repository ID and original commit
SHA. Pin each selected branch head before enumerating its reachable commits.
List branches/history with 100 items per page and at most 10 pages per list.
Retain page completion separately from count. The sample inspects the first
commit-file page (100 files); additional pages are declared omissions. GitHub
caps commit-file listings at 3,000 files; absent patches remain unknown and may
be binary, large, or unavailable. Text documents use Contents API at the sampled
SHA with a 1 MiB preview budget; HTTP responses have an 8 MiB limit and 20-second
request timeout. Redirects are rejected so credentials cannot move to a new host.

Contents read plus repository metadata is the planned minimum permission for
commit/document checks. A successful read does not prove a supplied token is
least-privilege: granted scopes/expiry may not be exposed. Record safe rate-limit,
SSO, scope and expiry headers when available. Organization approval and token
expiry require a selected authenticated sample later. Return 401/403/404/429 as
access failures, preserve unavailable documents explicitly, and infer no deletion.
An empty/conflicting repository currently stops with a clear 409 check failure;
full empty-repository handling belongs to the backfill implementation.

## Checks and sources

Local full backend suite: 186 tests passed (25 acquisition cases), including real
migrations in a disposable PostgreSQL schema. Frontend checks are recorded in
`CURRENT.md`. Acquisition tests use synthetic history and mocked network replies;
real CLI/REST probes separately verified the sample reads above. The isolated DB checks required sandbox network permission.

- [Official OpenAI app-server documentation](https://developers.openai.com/codex/app-server)
- [GitHub commit API and file pagination limits](https://docs.github.com/en/rest/commits/commits)
- [GitHub Contents API and size limits](https://docs.github.com/en/rest/repos/contents)
- [GitHub repository metadata](https://docs.github.com/en/rest/repos/repos)
