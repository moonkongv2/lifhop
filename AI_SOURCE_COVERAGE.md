# Primary event evidence and Phase 3.3 acceptance

Implemented 2026-10-18. Verification uses disposable PostgreSQL schemas,
synthetic records and mocked providers. No personal archive was read, no real
database was rebuilt, and no new OpenAI request or indexing approval was made.

## Evidence scope

Source and record AI permission must both allow the record. The shared type gate
now admits the following validated PROJECT_EVENT evidence alongside existing
NOTE, DOCUMENT and CONVERSATION text:

| Collected source | Primary evidence | Retained outside primary evidence |
| --- | --- | --- |
| Codex turn | User messages and explicitly tagged assistant `final_answer` messages | Commentary, unknown/missing assistant phases, commands/results, diffs, other roles |
| GitHub commit | Commit message | SHA, author, parents, file metadata and patches |
| GitHub PR/issue | Collected title and available body | Author/status metadata and collection-gap markers |
| GitHub comment/review/review comment | Available body | Review status, code locations and diff hunks |

An empty/unavailable discussion body is never replaced with a placeholder as AI
evidence. A root title can still qualify by itself; it does not prove the missing
body was collected. Invalid provider/kind/object identity or a canonical body
that differs from the retained source produces no primary GitHub event ranges.
Arbitrary PROJECT_EVENT records and LOG records remain excluded.

Ranges use exact character offsets into immutable version bodies. Indexing,
vector retrieval, current answer egress, period review and historical selection
use the same source scope. Event egress additionally reconstructs canonical
ranges under the owner lock before transmission. The legacy whole-version AI
helper rejects events rather than sending their full raw body.

Codex unknown phases remain locally readable. They are classified as work-only
in the new disposable Passage projection, so local Passage search can find them
with work details included. GitHub metadata/patches similarly require that option
in Passage search; full record/exact-phrase reading retains the original text.
No Entry type or source body was rewritten. Period review prefers an explicit
Codex final-answer passage over the user question, still selecting only one
complete parent per record. Later sections can remain outside the bounded sample.

## Apply to existing records

The projection is now `current-passages-v2`. Old projections and their vectors
are unavailable to current Passage/Semantic retrieval until rebuilt. Retained
version citations continue to open their original text. No schema migration,
dependency, embedding-model or answer-model change is required.

Restart the backend and embedding worker so both use this code. In the repository
root, rebuild the authenticated account's **local** projection:

```bash
.venv/bin/python scripts/index_passages.py --email b@test.com
```

Enter the lifhop password at the terminal prompt. Expect `ready`/`partial` counts
and no `failed` items. Partial records retain explicit gap codes. This command
does not request embeddings. Changing projection/storage configuration prevents
old follow-change approvals from enrolling new jobs; existing queued old-config
runs pause when claimed. Review any remaining old runs in indexing status.

Existing vectors are deliberately not reused across this boundary. Before any
new paid indexing, create a **fresh** dry-run restricted to explicit Entry IDs
and review its scope, slices, estimated cost and caps. Source permission alone
does not activate jobs. Do not reactivate the earlier 43-document approval or
reuse closed evaluation protocols. Indexing activation remains a separate explicit
approval. New reindexing cost must be reviewed even for unchanged documents.

## Agent checks and limits

Final full backend suite: **664 passed**, including 23 event-evidence tests.
Diff whitespace check passed. Frontend and API schemas are unchanged; this slice
uses actual HTTP handlers against the disposable database, without a browser run.

`tests/test_event_evidence.py` covers all seven event payload kinds, primary-only
worker dispatch and vector publication, foreign owners, source/record denial,
source deletion, invalid payload mappings, corrupted work flags, old projections,
old follow approvals, empty/unavailable bodies and arbitrary project events.
An HTTP scenario combines Codex and GitHub in a cited answer, period retrospective
and observed-history answer, opens exact original citations, and accepts a mocked
insufficient-evidence result with no citations. Providers are mocked throughout.
Existing lifecycle, date, cost, request replay and citation tests remain required.

These tests establish wiring and policy behavior. A mocked supported answer or
insufficient result does **not** establish model grounding, classification, recall,
latency or actual per-query provider cost. Commit messages and final answers are
recorded assertions; they do not independently prove deployment or successful tests.
Relevant diffs/tool evidence remain retained; admitting selected such evidence
requires a separate bounded scope, not expanding this gate wholesale.

## Next bounded acceptance: six cases, one reviewed pass

Prepare a fresh, owner-reviewed evidence set with exact questions, expected claims,
required sources/versions and allowed excerpts. Keep failures in the report; do
not repeatedly tune against this set. Use the existing runtime model/configuration.

| Case | Expected observable result |
| --- | --- |
| Decision and implementation | Combine a Codex decision and a GitHub message/document; cite both; do not infer deployment |
| Reason and later change | Cite the recorded reason and distinguish a proposal from an adopted change |
| Ordinary life memory | Use a note/conversation for a non-project fact; do not force a repository association |
| Period review | Cite proposals, decisions and completed assertions separately; disclose partial/date coverage |
| Historical cutoff | Use the latest observation by cutoff, with no current-text substitution |
| Missing proof | Explain insufficient evidence when production use or a reason is absent |

Before provider calls, record fresh indexing/transmission manifests, exact question
and excerpt counts, serialized request bounds, per-action/aggregate call and cost
caps. Separately approve actual indexing and one evaluation pass; no approval is
inferred from this document. Preserve unavailable/disallowed sources as coverage
gaps, not permission changes. Existing normal flow caps are two calls and USD
0.011/action (query + answer); period/history use one answer call and USD 0.01.
Indexing is additional and needs its own bounded estimate.

To close Phase 3.3, record each case's result, original-citation checks, model/config,
latency and settled cost (including uncertain reservations). Required claims must
be supported by their cited originals; unsupported conclusions fail acceptance.
Owner isolation, prohibited egress and deleted-content resurfacing have zero
tolerance. Separate retrieval, answer and coverage failures. Fix a blocking failure
or explicitly agree a narrower release before proceeding; do not silently mark
it passed. Once accepted, start Phase 4 scheduled collection. This implementation
does not declare Phase 3.3 complete or start a new ranking/model-tuning experiment.
