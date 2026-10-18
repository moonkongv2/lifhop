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

### Local draft preparation (2026-10-18)

The new preparation command authenticates locally, reads a repeatable read-only
snapshot, and writes private drafts. It makes zero provider calls, creates no
usage reservations/jobs, and changes neither permissions nor source data.
Rebuild the local Passage projection first if it still uses v1. Backend, frontend
and workers do not need to run for this command; PostgreSQL must be running.

```bash
.venv/bin/python scripts/prepare_phase33_acceptance.py --email b@test.com --date-from 2026-10-01 --date-to 2026-10-18 --as-of 2026-10-17
```

Enter the account password in the terminal. The period dates above select source
events in October; `--as-of` selects the last observed version by the end of
October 17 in Asia/Seoul. These are explicit review choices, not evidence that
eligible records exist in that scope. Choose other dates when appropriate.
The command prints `State`, question/excerpt counts, gap codes, and a private
`review.html` path under `.local/evaluation/phase33/`. Open that file locally.

- `coverage_gaps`: one or more cases lack eligible primary text or required
  sources. Keep the gap; do not invent an answer or enable a denied source.
- `needs_owner_review`: structural evidence coverage is present. This does not
  mean the excerpts directly support the provisional expected answer.
- Local coverage now separates projection readiness from external-AI permission.
  A source/type inventory reports only this owner's record counts and the two
  permission flags. It does not display denied source bodies. Current-case
  diagnostics count matching primary records before policy, permitted matches,
  and record/source/type exclusions. These exclusion counts overlap.
- `MATCHING_PRIMARY_TEXT_AI_EXCLUDED` means local primary matches exist but none
  qualify under the AI gate. `NO_LOCAL_PRIMARY_MATCH` means no matching current
  primary projection was found; check global `pending` counts before concluding
  that records are absent. Neither code proves the answer is missing from the
  entire archive. Period/history diagnostics distinguish excluded scoped records,
  no observation by cutoff, and no historical keyword match.
- Review all six questions, relevance of the exact original excerpts, and the
  provisional outcome/checklist. The missing-proof case must actually lack the
  requested proof; the tool cannot determine this from IDs or source types.
- Only AI-permitted current records enter lexical candidates. The first twenty
  ranked candidates are bounded before text reads; choose up to five complete
  parents, one per Entry and document group, inside existing payload limits.
  The cross-source draft deliberately prioritizes Codex and GitHub candidates.
  Period/history drafts reuse the product's bounded previews and exact metadata.
  Assistant unknown phases and work-only ranges remain excluded.

The adjacent `spec.json` contains editable draft questions, lexical query terms,
filters and date scopes. An edited private spec can generate a fresh review:

```bash
.venv/bin/python scripts/prepare_phase33_acceptance.py --email b@test.com --spec .local/evaluation/phase33/DIGEST/spec.json
```

Replace `DIGEST` with the printed directory. For history, `question` must match
`historical.q`; the period question is generated from its scope. Current-case
`query` is draft discovery text, separate from the question eventually reviewed.
No source-derived "correct answer" is generated or marked owner-approved.
Protocol metadata binds owner/database, policy/configuration, question/checklist
digests, version/range/hash anchors, scope and coverage. Source bodies stay in
the local review; files/directories are private (0600/0700), outside Git.

This is **selected-context preparation**, not a paid execution protocol or an
automatic Semantic recall result. It cannot authorize execution. The future
answer-only ceiling is at most six calls/USD 0.06, counting only prepared cases
with evidence and no blocking gaps. Deferred/no-evidence cases add no calls or
cost reservation. Estimates are computed from exact
payloads; query embeddings and fresh indexing need separate estimates/approval.
Do not expand earlier three-case pilots or count mocked results as real quality.
Actual retrieval capture, owner-reviewed expected claims, approved execution,
settled cost/latency and citation/grounding review remain outstanding.

Preparation verification: full backend **681 passed**, including 17 preflight
checks covering source/record denial, source deletion, other owners, historical
text, HTML escaping, invalid specs, no HTTP/usage/jobs, local authentication,
private file modes, edited-spec regeneration and metadata-only exclusion counts.
CLI help and diff whitespace
checks passed. No personal-account review or actual provider call was performed.

The first owner-generated review was subsequently inspected through metadata
only. Projection readiness and AI permission are separate; the saved draft has
coverage gaps and does not authorize transmission. Its counts/candidate identities
are retained privately beside that review. Source/record permissions were not
changed, and candidate bodies were not read. Narrow approval to inspect an
AI-excluded candidate in this Codex conversation is separate from persistent DB
permission and from any additional OpenAI API call. Never grant either implicitly
to make a six-case set appear complete. Historical keyword hits and source-kind
coverage still require direct relevance/claim review.

Following that audit, the owner explicitly authorized inspection and persistent
AI permission for three selected Codex records and their source. The change was
applied through the existing policy invalidation boundary after checking for
matching active indexing work. Other record/source settings were verified
unchanged; no indexing run or provider request was activated. The authorized
primary-text review and refreshed preflight still leave acceptance incomplete.
Permission and relevance are separate checks. Detailed per-record findings and
the mutation audit are private under `.local/evaluation/phase33/`, outside Git.

### Revised draft and one-pass executor

An optional `deferred_reason` preserves an acceptance case without selecting
evidence or budgeting a call for it. An ordinary supported category may instead
contain an `insufficient` question when the reviewed text only mentions a desired
question. This remains an unresolved positive acceptance category; a correct
negative answer cannot satisfy the original positive fact-recall requirement.
`prepared_answer_cases` and `unresolved_acceptance_categories` report these
separately. Missing-proof itself must still expect insufficient evidence.

The revised owner-specific proposal prepares four answer candidates from nine
excerpts of the three permitted records. Two original categories remain deferred,
and positive ordinary-life fact recall remains unresolved. New dates/questions
are proposed in a separate private spec/review rather than overwriting the first
review. No expected answer has been marked owner-approved. Source-specific
details/checklists stay private and are not sent as hints to the provider.

`scripts/run_phase33_acceptance.py` can execute the prepared subset **after**
explicit approval of its questions, excerpts, one pass and caps. It is separate
from the earlier closed three-case pilot; those protocols and limits are unchanged.

```bash
.venv/bin/python scripts/run_phase33_acceptance.py --email b@test.com --protocol .local/evaluation/phase33/DIGEST/protocol.json --approve-digest DIGEST
```

The CLI authenticates locally and reconstructs the preflight. Owner/database,
source/version/permission/configuration, exact ranges/parent IDs, questions,
checklists, scopes or budget drift invalidate the frozen draft. Model configuration
must already enable answers; the script does not enable AI or alter `.env`.
Explicit digest approval is required before the run marker or any HTTP request.
Use existing `/answers`, `/retrospectives` and `/historical` handlers, shared
monthly budget and per-answer USD 0.01 ceiling, without new embeddings/indexing.
The four-case proposal has a maximum of four answer calls/USD 0.04, not six calls.

An exclusive private run-start marker and deterministic action IDs prevent replay.
Stop after an HTTP failure or unexpected supported/insufficient status, with no
automatic retry. Preserve raw provider output, route responses, latency and the
spent/reserved/uncertain ledger. An interrupted in-flight request is marked
uncertain rather than unsent; remaining cases are not dispatched. Successful
transport/status checks do not establish grounding or Phase 3.3 completion.
Review each claim against its original citation after the approved run. Automatic
Semantic retrieval, deferred categories and the positive life-memory example
remain outside this selected-context pass.

Revision/executor verification: full backend **692 passed**, including 20
preflight and 8 execution tests. Four mocked actions traverse current answer,
retrospective and historical HTTP handlers, settle usage once, and reject replay.
Wrong approval/spec/config/budget/count/order, HTTP failure and an interrupted
request are covered. Both CLI help commands and diff whitespace checks passed.
The actual private four-action request plan was validated locally before approval.

### Approved pass closed (2026-10-18)

The owner approved the exact four-question/nine-excerpt protocol for one pass,
at most four calls and USD 0.04. All four real calls completed once through the
existing product handlers: two expected insufficient answers, a supported period
review and a supported historical priority answer. Actual settled cost was
USD 0.000809; individual actions took 2.4–4.0 seconds. No new uncertain attempt
remained. Three older uncertain reservations were preserved without settlement
or release. No indexing or further permission change occurred.

Direct review checked all four returned citation ranges against the approved
versions and original text. Both refusals and the historical priorities were
grounded. Period content distinguished recorded activity from proposals, but one
calendar date used UTC instead of Asia/Seoul. Therefore expected-status agreement
does not mean all four passed full acceptance. Private raw output, ledger, route
responses and grounding findings remain beside the frozen protocol, outside Git.

The retrospective payload now supplies event/collection timestamps with explicit
Seoul offsets and instructions require Seoul calendar dates. Synthetic regressions
cover the UTC boundary and missing event dates; no real-model retest was made.
This changes the answer configuration hash: future calls require a fresh reviewed
preflight and approval. The old approval is consumed and its raw output must not
be rewritten or replayed. The approved process temporarily enabled answer mode;
it restored the original settings and did not edit `.env` or a running server.

Final backend verification after the date fix: **694 passed**, including the two
new date regressions and the preflight/execution guards. Diff whitespace checks
passed; no frontend code changed or browser check was repeated.

The two deferred categories, positive ordinary-life recall and automatic Semantic
retrieval remain unresolved. This bounded selected-context pass does not close
Phase 3.3 or authorize further paid diagnostics.

### Acceptance gates

The subsequent approved integrated smoke pass completed once: three real queries,
three answers, fourteen automatic excerpt occurrences, USD 0.000997 settled and
zero new uncertain usage. Codex priority recall and missing-proof refusal passed
direct review. GitHub purpose/flow is partial: the child-audience detail is present
in selected context but absent from its sole cited excerpt, and a reference
checklist detail was omitted. Two exact original citation reads passed; source
policy, versions and old reservations remained unchanged. Temporary answer mode
was restored off. Preserve this finding and the immutable raw outputs; expected
status agreement does not close grounding acceptance. No additional paid retry
is authorized. PHASE33_COMPLETION_PLAN.md records the remaining local work and
coverage gaps. These source-filtered known cases are not a broad quality benchmark.

The separately approved 46-record current-index restoration completed on
2026-10-18: 43 GitHub documents and three Codex records, 1,060 eligible slices,
67 embedding calls, USD 0.000996 settled and zero new uncertain usage. Exact
manifest anchors and local status API were independently verified without new
provider calls. Prior jobs/runs/reservations, source policies and versions were
preserved. No question/answer call was included. Index availability does not
establish integrated retrieval quality; the remaining sequence is recorded in
PHASE33_COMPLETION_PLAN.md. The consumed approval grants no follow-change work
or additional evaluation calls.

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
