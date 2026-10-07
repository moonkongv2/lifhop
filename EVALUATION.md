# Private retrieval evaluation — Phase 3.1

The local CLI authors private evaluation questions and measures the existing
owner-scoped keyword search. It does not generate answers, send AI requests,
create embeddings, or modify lifhop records/policies/versions.

## Setup

Run from the repository root with `.venv` installed and the normal `.env` database
configuration. Start PostgreSQL if needed:

```sh
docker compose up -d db
```

The backend/frontend/worker are unnecessary for evaluation commands. For existing
record links, run the usual backend/frontend and log in as the evaluation owner.
The app must use the same database as the CLI; report IDs are database-local.

Each command authenticates using the existing local password hash inside a
PostgreSQL `REPEATABLE READ READ ONLY` transaction. Passwords are entered through
getpass and are not stored. The database is read from existing settings; it is
not silently replaced with a test database. Missing source policies remain denied
for external AI and are not inserted.

## Start the owner's real set

The owner selected `b@test.com`. Initialize once:

```sh
.venv/bin/python scripts/evaluate_retrieval.py init --email b@test.com
```

Enter the local lifhop password in the terminal. The command prints a private
directory such as `.local/evaluation/SET_ID`. Subsequent commands use that exact
directory; `SET_ID` below is a placeholder. Twenty **draft** cases are created.
Two contain the roadmap seed questions; the remaining questions are blank.
No answers, passages or reviewed status are invented.

Optionally author local-rule candidates once, before editing revision 1:

```sh
.venv/bin/python scripts/evaluate_retrieval.py draft --set .local/evaluation/SET_ID
```

This creates revision 2 and `candidates-revision-000002.html`, with 20 template
questions and bounded candidate spans. All remain drafts. It excludes records whose
titles start with `[Synthetic]`, inspects only the bound owner's local records, and
makes no model/network call or database write. Explicit SHA overlap proposes
cross-source candidates (up to 100 Codex turns/1000 commits); document comparisons
use up to 1000 snapshots within one source scope/path. These are bounded candidate
searches, not semantic verification or proof of completeness. A matching record
may repeat a question without answering it. The `[Candidate]` claim placeholder
must be replaced with a verified fact before `review` accepts the case. Once any
case has been authored, `draft` refuses to replace the owner's work.

```sh
.venv/bin/python scripts/evaluate_retrieval.py edit --set .local/evaluation/SET_ID
```

Choose a case ID. Blank keeps a field; `-` clears a string. JSON fields use one
line. For an initial supported case, enter a real question, language, outcome
`supported`, tags, and optional keyword queries. Leave anchors empty until you
inspect the real record. Example JSON structure with fictional wording:

```json
{
  "tags": ["decision"],
  "keyword_queries": ["chosen keyword"],
  "filters": {"source": "codex", "date_field": "event_at"},
  "claims": [{"id": "claim-01", "statement": "A fact I verified in the original record", "required_group_ids": ["reason"]}],
  "evidence_groups": [{"id": "reason", "anchors": []}]
}
```

These are **five separate JSON prompts**, not one combined input. Replace the
fictional statement with a fact checked in your own record. Edit initially accepts
drafts without anchors. A claim must reference an existing group ID.
Use separate required groups for different claims/sources. Multiple anchors in
one group mean alternative evidence for that one requirement.

Useful tags: `decision`, `life`, `cross_source`, `history`, `changed_decision`,
`ai_excluded`, `coverage_gap`. Tags describe owner-reviewed cases; they do not
automatically prove semantic correctness or source completeness.

## Find and pin evidence

```sh
.venv/bin/python scripts/evaluate_retrieval.py inspect --set .local/evaluation/SET_ID
```

Choose a case and enter a query interactively. It shows the first 20 matching
Entry IDs, current version IDs and browser links. Open the original record to
check its meaning and history. A full natural-language question often has no
literal substring match; use inspect to locate candidate evidence without changing
the frozen primary question.

```sh
.venv/bin/python scripts/evaluate_retrieval.py anchor --set .local/evaluation/SET_ID
```

Choose the case/group, Entry ID, version ID, `content` or `title`, and starting
character offset. A bounded preview shows each line's starting offset. Choose an
exclusive end offset and `current` or `historical` selection. Offsets count Python
Unicode characters in the original version, including newlines; an emoji counts
as one code point. Terminal control characters are displayed escaped, while stored
offsets still refer to the original text. To start simply, use start `0` and choose
the end of one short supporting paragraph in the displayed preview.

The saved anchor contains identity, version/content hashes, span and passage hash,
not a copy of the source passage. Each selected field has an 8 MiB budget and each
passage an 8,000-character limit. Wrong owner/version, invalid offsets, stale current
selection or oversized fields are rejected. Historical anchors do not make older
content searchable through the current Entry search.

## Validate and approve

```sh
.venv/bin/python scripts/evaluate_retrieval.py validate --set .local/evaluation/SET_ID
.venv/bin/python scripts/evaluate_retrieval.py review --set .local/evaluation/SET_ID
```

Validate prints anchor status and set composition without changing files. Review
shows the chosen case and requires you to type `REVIEWED` after checking the meaning
of its claims/evidence. Supported and policy-excluded cases need claims and nonempty
required groups. Negative outcomes need a reviewed scope and explanation:

- `insufficient_evidence`: insufficient support within the examined records/scope.
- `coverage_gap`: missing or incomplete collection prevents a trustworthy answer.
- `policy_excluded`: supporting records exist locally but external AI use is restricted.

A zero-result search alone does not prove that the answer does not exist. Clearly
distinguish a considered option from the adopted choice and a proposal from completed
work. `policy_excluded` cases still have local retrieval scores; exclusion is an
independent eligibility observation, not an AI refusal test.

Every edit/anchor/review publishes a new immutable `revision-000NNN.json`, linked
to the previous digest. Editing resets the changed case to draft. Earlier revisions
are preserved and never overwritten. Commands choose the latest valid revision;
use `--revision N` to examine/run an earlier one. Starting edits from an older
revision that already has a successor fails with `OUTPUT_EXISTS` rather than creating
a branch or overwriting later work. Do not hand-edit approved revision files.

## Run both baselines

```sh
.venv/bin/python scripts/evaluate_retrieval.py run --set .local/evaluation/SET_ID
.venv/bin/python scripts/evaluate_retrieval.py run --set .local/evaluation/SET_ID --mode keywords
```

The first command searches the question exactly as written. The second independently
evaluates up to three preselected keyword queries per case. It averages query scores
within each case, then averages cases equally. Results are not merged and the best
keyword is not selected retrospectively. Primary and keywords remain separate runs.
Cases without keywords have `no_keyword_query`; common-keyword case scores allow
comparison on the same subset.

Each run prints paths to new `manifest.json`, `results.json`, and `report.html`.
Open the HTML locally. Expect case IDs, statuses, scores and ranked record links.
Source bodies, titles, questions, expected claims, annotations and credentials are
absent from report files. Look up question/claim text in the private revision file.
Historical-only cases have no current-retrieval score; their Entry hits are reported
separately and do not prove retrieval of the older passage.

### Reading scores

- **GroupRecall@5/10/20:** fraction of required evidence groups found by Entry and
  the pinned current version. Alternative anchors count once.
- **AllGroupsHit@20:** whether every required group was found.
- **MRR@20:** reciprocal rank of the first valid current supporting Entry.
- **CurrentVersionHit:** whether at least one pinned current anchor was found.
- **HistoricalEntryHit:** whether an Entry carrying historical gold was returned;
  historical passage retrieval remains unsupported.

Draft/negative/historical-only cases are outside the current-retrieval denominator.
Reviewed cases with invalid/stale/unavailable anchors retain the denominator and
cannot count those anchors as success. Timeout/budget failures also retain zero
scores. Clean scores and failure/status counts are provided alongside the complete
scored denominator. Mixed current/historical requirements cannot pass AllGroupsHit
through a historical Entry-only hit.

Targets are GroupRecall@20 ≥ 0.80 and AllGroupsHit@20 ≥ 0.70. A low initial baseline
is a useful measurement, not a failed tool implementation. Full real-set readiness
requires at least 20 reviewed questions, both seeds, Korean/English ≥3 each, life ≥4,
cross_source ≥3, history ≥2, ai_excluded ≥2 and coverage_gap ≥2. These are structural
checks of tags; the owner still verifies meaning and applicability. Do not add fake
answers to satisfy the checklist.

Compare implementations using the same dataset revision, mode, query configuration
and corpus fingerprint/policy revision. The manifest records the Git commit, dirty
state, evaluation/search code digest, observation time, record/version counts and
bounded recent collection coverage. Different corpus/policy/filter data means the
comparison includes data changes. Collection coverage is limited to the newest
100 runs before grouping; it is not a full source audit.

## Privacy and limits

Files are confined to `.local/evaluation/`, excluded by Git, and saved with directories
0700/files 0600. Symlinks/path escapes and overwrites are rejected. Source passages
are resolved in memory; the dataset does contain private questions and human-written
claim/review notes. Treat the entire directory as sensitive. Existing private backups
and manually copied files need separate owner cleanup.

A source deletion marker differs from deletion in lifhop. Source-deleted records
remain locally inspectable with a marker, but external-AI eligibility defaults to
false for them. A lifhop deletion makes its anchors unavailable and existing record
links return 404. Old reports describe their original observation time and carry no
source body copy. Policy inspection never enables collection or AI use.

Limits: 2 MiB/dataset, 100 cases, 1,000 immutable revisions, three auxiliary queries
(four queries across both modes), 20 anchors/case, 5-second DB statement timeout and
5-minute evaluation budget. A SQL timeout rolls back its savepoint and marks the case
failed. A preflight corpus fingerprint budget/database error stops before publishing
a report; retry creates a fresh run. Authentication/file errors print body-free codes.
Very large real corpora and real owner benchmarks remain unverified.

## Synthetic verification

To generate disposable demonstration reports without touching the owner database:

```sh
.venv/bin/python scripts/check_evaluation.py
```

This uses `lifhop_test` (default localhost:5433; override through `TEST_DATABASE_URL`),
verifies its name, migrates a fresh `evaluation_check_*` schema, creates 20 labeled
fixture cases, authenticates the synthetic owner, executes both modes, and drops that
schema. It prints the report paths. Expect 14 current scored cases, two historical-only
cases, four negative cases; primary recall 0 and keyword mean recall 0.5. Synthetic
record links are disabled because the fixture schema is removed. This is not a real
20-question owner evaluation, and composition never marks it complete.

Agent checks: backend regression tests, real read-only PostgreSQL authentication and
snapshot consistency during concurrent updates, query/API equivalence, Unicode spans,
hash/version/owner validation, policy inspection, revision/CLI flow, timeout recovery,
metrics and private outputs. Chromium checks use only synthetic HTML; the in-app
browser could not initialize, so standalone Chromium was used. The owner initialized
the real set with a local password; the agent received only its path. A subsequent
authorized local read-only preparation saved revision 2: 20 draft cases, 13 with
candidate spans, seven without connected candidates, 14 valid anchors. The corpus
has 415 real GitHub and 33 Codex records, with 32 synthetic records excluded.
All source records currently deny external AI; their bodies were not output or sent
to a model. No real retrieval benchmark or semantic evidence approval was completed.

Executed on 2026-10-07: full backend **316 passed**, evaluation tests **19 passed**,
compile/help/whitespace checks passed. A first full run failed five GitHub count
assertions because the new concurrency test retained committed fixture rows;
adding fixture cleanup fixed the rerun. Initial sandbox PostgreSQL/Chromium permission
errors were resolved by approved executions. Final synthetic reports passed at
390/1440px with 20 rows, no page errors, outbound requests or document overflow.

Final checks after local candidate authoring: full backend **319 passed**, including
**22 evaluation tests**; compile/help/whitespace checks passed. Candidate tests cover
owner/synthetic isolation, explicit SHA pairing, valid anchors, immutable revision
publication, private HTML escaping/permissions, overwrite refusal and placeholder
approval rejection. The real private candidate sheet was not exposed to an AI
browser; owner meaning review remains pending.

## Current next step

The owner checked case-04 and found mainly code-location information rather than
an explicit explanation of the worker's purpose/execution location. Its candidate
is not approved support. Search for explicit answer passages; if the declared
reviewed scope lacks them, record insufficient evidence. Only classify a collection
gap when missing source coverage is known. The saved revision remains draft.

Open the private candidate sheet locally as `b@test.com`. Start with one question:
check its usefulness, linked original record and pinned span; distinguish mentions
from actual answers. Use `edit` to replace the placeholder claim with a fact checked
in that span, retaining its required group ID. Then `review` that case and run
primary and keyword modes. There is no explicit retained Codex/GitHub SHA overlap
in this corpus; life and real PR/issue candidates still lack connected support.
After that, complete about 20 verified questions together and freeze the real baseline
before implementing Phase 3.2 retrieval improvements or Phase 3.3 AI answers.
