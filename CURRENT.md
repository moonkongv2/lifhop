# lifhop Current Status

Last updated: 2026-10-18

## Roadmap checkpoint (2026-10-18)

Active stage: **Phase 3.3, implementation present but exit acceptance incomplete**.
Phase 1 archive and Phase 2 manual collectors/history/policies are implemented;
selected-source coverage and older owner-confirmation notes still need reconciliation.
Phase 3.1 evaluation tooling and Phase 3.2 indexing/search are implemented, with
real quality checks concentrated on GitHub documents and selected known cases.
Phase 4 scheduled Codex/GitHub collection and Phase 5 private AWS daily use remain
unimplemented. Existing import/embedding workers are not scheduled collectors.

The audit found a source-coverage gap: current import normalization produces
PROJECT_EVENT for Codex sessions and GitHub commits/discussions, while embedding
jobs/storage, answer egress, historical answers and retrospectives admit only NOTE,
DOCUMENT and CONVERSATION. These event records can be retained/read/searched locally
but do not become AI evidence even when their AI permission is enabled. GitHub
documents do qualify. Synthetic normalization and the compiled storage type filter
confirmed this without private record reads, DB changes or provider calls.
Address the bounded primary-evidence scope before declaring cross-source RAG or
Phase 3.3 complete; this audit did not change any egress permission or type gate.

## Current product slice

**2026-10-18 Search UI consolidated:** The form now exposes Search & ask and
Review a period. Ordinary searches call local Passage retrieval without answer
status/provider calls; an optional Get an answer with sources panel reuses the
existing consented integrated answer. AI-excluded records remain searchable.
Advanced options hold exact phrase matching (local record search, no AI action)
and observed-version cutoffs (existing historical keyword preview/answer), plus
source-state/work controls. Legacy URLs remain readable; new normal URLs use
mode=search and strip UI-only fields from API requests. Citation returns preserve
filters/options/page without replay. Draft/purpose/version/account/panel changes
abort paid work; account-specific caches and failed-recheck hiding prevent stale
local bodies from resurfacing. Frontend 194 tests, lint/build and synthetic
Chromium desktop/mobile flow passed; an Advanced-panel collapse was found and
fixed with regression coverage. Actual OpenAI calls: zero. Backend/schema,
activation, ranking, indexing and dependencies are unchanged; backend tests were
not rerun for this UI checkpoint. Owner usability and real-model quality remain
unverified. Owner authorized this commit checkpoint. See UNIFIED_ANSWER.md.

**2026-10-18 observed historical questions implemented:** Search now offers
Historical question with an explicit end-of-day Asia/Seoul observation cutoff.
Choose the latest retained observation per record before keyword matching; never
fall back to an older matching version or substitute today's text. The local
preview shows exact dated evidence, observation/AI coverage and all selection
limits (twenty candidates, five full excerpts; no historical vectors). A reviewed
owner/scope/revision/config-bound digest gates one consented answer. The existing
answer caller/ledger rechecks historical eligibility and exact ranges/date metadata
before reservation, under the dispatch owner lock and before returning output.
Current exclusions, allowed record/version types and deletion apply to old versions.
Citations open retained originals separately from the current record. Current
answer/retrospective defaults and AI activation are unchanged; no schema, dependency
or indexing change. Backend 641 and frontend 181 tests passed; Chromium verified
January Alpha vs February Beta, original/current citation destinations, no evidence
before collection, and no replay on return/reload. Two mocked answer calls, zero
actual OpenAI calls. A test-owner cleanup leak and async UI result reset were
found and corrected before passing verification. Owner authorized this commit checkpoint.
Late imports do not reconstruct earlier external state; semantic recall and actual
model grounding/classification remain unverified. See HISTORICAL_QUESTIONS.md.

**2026-10-17 retained citation freshness implemented:** New answer and
retrospective citation links carry version/field/range/hash anchors. Local
`GET /passages/citation` reads at most 2,000 characters directly from the owned
retained version, checks its hash, and reports whether that version is currently
selected. It survives disposable Passage/embedding removal without replacing
old evidence with current text. The reader shows the original title/event date,
version observation time, current-version identity and source deletion/unavailable
warnings; Open current record provides a separate destination. Local deletion,
missing versions, another owner and mismatched text all return generic 404 with
no replacement. Local reading remains available when external-AI permission is
off, consistent with existing version history; this endpoint cannot dispatch AI.
Readers discard cached text on failed rechecks and separate account/anchor keys.
Full backend 615 passed, frontend 167 passed, lint/build passed; Chromium verified
mocked answer → citation → edit → retained original/current record → AI permission
revocation → source deletion → local deletion → search return. Actual OpenAI
calls: zero. No schema/dependency/indexing changes. Owner authorized this commit checkpoint.
Legacy links without anchors still depend on disposable IDs; historical retrieval
and real-model quality remain outside this checkpoint. See ANSWER_SLICE.md.

**2026-10-17 bounded period retrospective implemented:** Search offers **Period
retrospective** for up to 92 days, defaulting to source/event dates with an Added
date option. Local preview counts scope/AI eligibility/current body coverage,
groups repeated document parents and samples across time (at most twenty
candidates, five complete first-body Passages within the actual request limit).
Unknown event dates, unindexed/partial records, omitted sections and byte skips
remain visible. It always labels the view partial and uses current retained
versions, without reconstructing past state. One consented summary call reuses
the existing answer ledger/caps; no query embedding or index change is needed.
The preview digest binds current scope/owner/revision/anchors/dates/config and
is recomputed before dispatch. Date/source metadata is checked again by the
common caller. Every supported item requires an allowed source marker and a
category; plans/commits alone must not be presented as proof of completion.
Format is mechanically checked; factual support/classification still require
review. Existing normal answer payloads retain their behavior; the configuration
hash includes the new retrospective contract. No migration/dependency/activation
change. Full backend 613 passed, frontend 162 passed, lint/build and generated
OpenAPI types passed. Synthetic Chromium checked one mocked summary, per-item
citations, date-basis changes and return/reload without replay. Actual OpenAI
calls: zero. Owner authorized the commit checkpoint; owner usability and real
model quality remain unverified. See RETROSPECTIVES.md. The synthetic demo now has four dated
records, including an explicit proposal and recorded completion.

**2026-10-17 unified question flow implemented:** Search now offers **Answer with
sources**. After reviewing question/filters and one combined consent, **Ask from
my records** runs existing Semantic retrieval → local parent recommendation →
cited answer. Manual selection is optional under an advanced action. At most
one query and one answer call (USD 0.011 combined); the browser freezes session,
parameters and revision, uses a shared action ID in separate ledger domains,
and never retries or resumes automatically. Stop, draft/filter/account/policy
changes and a 60-second deadline prevent subsequent stages. Already dispatched
requests may still finish/be charged. Answers now optionally check an observed
policy revision before reservation, while retaining existing current-source
dispatch/result guards. No database migration, model, index, dependency or activation change.
Final checks: 589 backend tests, 150 frontend tests, frontend lint/build and diff
whitespace passed. Synthetic Chromium verified one-action execution,
original-passage review, citation return/reload without replay and advanced mode.
No real OpenAI call occurred; general answer quality remains unverified. The owner
authorized this checkpoint's commit; separate owner browser confirmation was not
reported. See UNIFIED_ANSWER.md.

**2026-10-17 local evidence recommendations implemented:** Phase 3.3 now supports
Semantic results → local original-passage recommendation → full-text review and
selection adjustment → separate consented cited answer. The new local POST checks
all (at most twenty) candidates against current ownership, policy, version and
filters; it keeps at most five complete parents within the actual 14 KiB request
limit and reports omissions. It sends nothing externally and reserves no usage.
The existing answer route rechecks the selected Passage IDs before/after dispatch.
No database, dependency, embedding or ranking change was introduced.
The saved eight supported cases improve complete span coverage from 3/8 to 6/8,
with no evidence-group regressions; cases 01/07 still lack complete support.
This is known-case local context coverage, not a model-quality improvement claim.
The synthetic browser flow passed including consent reset, evidence-kind switch
and reload without replay. Final checks: 581 backend tests, 131 frontend tests,
frontend lint/build and diff whitespace passed. Initial sandbox DB access was
blocked; host execution passed. A frontend test type error was corrected before
the final successful build. No new real-provider call occurred. The owner authorized
this checkpoint's commit after discussing the interim UI. Separate owner browser
confirmation was not reported. The model checkpoint is `8731d0b`.
See `EVIDENCE_SELECTION_PLAN.md` for the implementation/result boundary.

**2026-10-17 GPT-6 Luna migration and next-slice plan:** Answer generation now
uses `gpt-6-luna`, reasoning effort none, temperature 0, no prompt caching
(explicit mode without breakpoints), and standard short-context prices of
USD 0.10 input/USD 0.50 output per million tokens. The shared ledger stores new
prices/config per attempt and preserves historical prices. Unexpected nonzero
cache usage cannot silently settle at the uncached rate. Embedding/indexing and
the deferred reranker retain their own existing models; no vectors were changed.
All 555 backend tests passed; no public API/frontend change occurred.
One user-requested migration round, protocol
`c751209e1b80052158403777d7b04b0f2304962c7d3888d615880a8cd21fdce0`,
sent the previously reviewed three questions/five excerpts once per question
under three calls/USD 0.03. All pass: supported answers cite slices 34/187;
the composer question returns insufficient with empty citations. The agent
checked claims/citations against source. Actual cost USD 0.000205, all three
attempts spent; reasoning/cache-write tokens zero. Old uncertain reservations
remain untouched, and normal ANSWER_MODE=off is preserved. This is a known-case
migration check, not independent quality/speed superiority evidence.
Private result: the new protocol's `run/results-review.html`; owner rechecking
is optional. Next work is planned in `EVIDENCE_SELECTION_PLAN.md`: first test
bounded local parent-Passage recommendations, then implement only if local
coverage justifies them. Keep text-embedding-3-small (1536); large-model
comparison/reindexing is deferred pending measured need and separate approval.
Migration code, the next-slice plan and accumulated execution records form the
completed model-migration checkpoint.

**2026-10-17 corrected-key negative regression, passed and closed:** After the
owner corrected a key typo and requested another attempt, new protocol
`b7ad00623a71c76d4ebe4e262d33e121ea5bbc16e7ee16640bdb6e1c569cc104`
sent the same one question/three excerpts once, under the one-call/USD 0.01 cap.
HTTP 200 returned in 2.329s: insufficient, empty citation IDs/public citations,
and an accurate explanation that the selected excerpts omit the composer.
The agent verified the answer against the source context and parsed the retained
raw response. The nested result schema is accepted by the pinned real provider.
Usage is spent (496 input/44 output tokens), actual cost USD 0.000269; no uncertain
usage for this attempt. All earlier failed runs and uncertain reservations remain
unchanged. No retry or key-management operation occurred. Normal answers stay off.
Private result: this protocol's `run/results-review.html`; owner rechecking is
optional. This closes the known negative-case regression, not independent quality
validation; the new wrapper's supported branch has synthetic coverage and was not
retested live. Stop repeated paid diagnostics here. Next: commit execution records
and plan automatic evidence selection for Phase 3.3. Product code is unchanged;
latest full backend tests remain 549 passed. Only result docs are uncommitted.

**2026-10-17 resumed check after user key replacement, closed:** The user stated
the key was replaced and requested resuming the same check. New protocol
`567d6ff39e5621ca51450316dc73ef3d6e563932aa4802804185770b18ae07de`
preserves all previous closed markers and sent the same one question/three
excerpts once, under the one-call/USD 0.01 cap. OpenAI returned HTTP 401,
`invalid_api_key`, in 0.745s; lifhop returned HTTP 503. No retry or answer occurred.
Secret-safe local checks confirm .env matches the loaded value, with no process
override, whitespace, non-ASCII characters or literal wrapping quotes. The loaded
value does not start with `sk-`; no key content, length or fingerprint was printed.
Next: owner verifies the actual newly issued secret (rather than name/ID) is set
as OPENAI_API_KEY in the repository-root .env. No further provider request before
credential correction. New usage remains uncertain, USD 0.002267 reserved, zero
settled; previous reservations are unchanged. Actual billing/schema acceptance/
answer behavior remain unmeasured. Private result: this protocol's
`run/results-review.html`. No product code changed; latest full tests remain 549.

**2026-10-17 approved diagnostic run, closed with authentication rejection:**
Protocol `d51d005ac86f7f251df0787a706de8320c3f5cd72fc6300b6ac85d2905fb4e73`
sent the approved question/three excerpts once (one-call/USD 0.01 cap). Upstream
HTTP **401**, type `invalid_request_error`, was safely captured in the private
rejection sidecar/report; code and parameter are null. Lifhop returned HTTP 503
`ANSWER_PROVIDER_REJECTED` in 0.799s. No retry or answer occurred. Authentication
rejection is established; the exact credential/project/access cause is not.
Local secret-safe checks confirm .env loading, no environment override and no
edge whitespace. No key was printed or changed. The new attempt remains uncertain,
USD 0.002267 reserved, zero settled; actual billing is unknown. Prior reservations
and closed run markers remain unchanged. Results and agent assessment are in the
new protocol's `run/results-review.html`; user evidence checks are unnecessary.
Next: owner checks key validity and project/organization/access settings in the
OpenAI console, updates .env if needed, then requests a new explicitly bounded
check. Do not blame the schema from HTTP 401 or repeat paid requests before fixing
authentication. Code is unchanged; latest full backend suite remains 549 passed.

**2026-10-16 commit/preflight checkpoint:** Core output-contract and safe-provider
diagnostics are committed as `b3f76ac`; explicit evidence-selection/capture tooling,
synthetic tests and run history form a separate tooling checkpoint. A new diagnostic
preview is ready for holdout-10 with the same three excerpts and unchanged model/
schema, now acknowledging the last closed provider-rejection run. Protocol:
`d51d005ac86f7f251df0787a706de8320c3f5cd72fc6300b6ac85d2905fb4e73`.
Its `review-complete.html` is under the private validation answer-preflight tree.
Estimate USD 0.002267, one call/USD 0.01, no retry. The agent has checked input
scope and privacy locally. No new provider dispatch or usage reservation occurred;
the earlier uncertain USD 0.002267 remains untouched. Next: obtain separate
approval for this exact new protocol before any real request. This next check
either confirms insufficient/empty-citation output or preserves safe upstream
error metadata; it does not establish independent retrieval quality.

**2026-10-16 safe provider-rejection diagnostics:** Non-200 answer responses now
retain HTTP status plus allowlisted error type/code/parameter. Error bodies are
read only within 8 KiB and two seconds; invalid JSON, HTML, oversized bodies and
read failures retain status alone. Raw upstream messages/headers and unknown
field values are discarded. The public API still returns only
`ANSWER_PROVIDER_REJECTED`; readable local logs and private pilot rejection
sidecars expose the sanitized metadata. Pilot reports verify the sidecar run ID
and safe fields before joining them. Sidecar-write failure preserves the
original API error. Provider rejection keeps conservative uncertain usage and
one-call replay protection; no model, prompt/schema, policy or ledger migration
change was made. No real provider request occurred. The earlier USD 0.002267
uncertain reservation and closed run markers remain untouched; its lost rejection
cannot be reconstructed. Next: commit the coherent local changes, then decide
whether a separately approved minimal provider check is needed. User repetition
of mock/ledger/privacy verification is unnecessary. Actual provider acceptance
and the prior real rejection's precise cause remain unverified.

**2026-10-16 approved one-call contract check, closed:** The owner approved
protocol `8954d9ec5080887d68301b84be1dc5adbe2859680f066f432ccd5e8d7b08492e`
(one question/three excerpts, at most one call/USD 0.01). Current preflight was
identical to the reviewed protocol. The single dispatch returned lifhop HTTP 503
`ANSWER_PROVIDER_REJECTED` after 0.707s, with no answer. No retry occurred.
The transport discarded the upstream rejection's status/error body, so the
precise reason cannot be established. Do not assume schema incompatibility,
model unavailability or a billing issue from this generic code. Actual schema
acceptance and insufficient-answer behavior remain unmeasured.
The ledger retains one uncertain attempt with USD 0.002267 reserved, USD 0
settled; actual billing is unknown. Preserve the reservation until authenticated
reconciliation. The run marker/approval, HTTP result, ledger and private assessment
are retained under the protocol's `run/`; `results-review.html` needs no server.
Next: add safe upstream-rejection diagnostics and verify them synthetically before
proposing another paid request. No code/model/ranking/permission change occurred
in this execution; prior implementation checks remain 538 backend tests passed.
All three answer runs are closed. Further paid attempts need separate approval.

**2026-10-16 structural answer output contract:** Provider output now wraps a
`result` object with a nested `anyOf`: supported requires 1–5 citations;
insufficient requires zero. The parser unwraps the result into the existing
public API shape and still rejects invalid IDs, duplicates, malformed output
and overlong/empty answers. This uses the official Structured Outputs subset
(object root, nested union and array size bounds). The pinned model is unchanged.
Synthetic fixtures and the preview provider use the new format. The config hash
changed, so completed protocols cannot authorize new dispatches. Prior raw
responses stay in their original format and are not rewritten or accepted by the
new parser. No paid request, embedding or policy change was made in this slice.
Agent local checks include both API evidence kinds and spent-cost/replay behavior;
no owner repetition of those checks is needed. A new private preview is limited to
holdout-10 and its three previously selected snippets; estimate USD 0.002267,
ceiling one call/USD 0.01. Protocol:
`8954d9ec5080887d68301b84be1dc5adbe2859680f066f432ccd5e8d7b08492e`.
Next: separately approve this minimal real contract check if desired. API schema
acceptance for the pinned snapshot and real-model behavior remain unmeasured;
local tests do not establish them. Both earlier answer runs remain closed.

**2026-10-16 approved selected-context diagnostic, closed:** Protocol
`ddfd55c3054e58123361d80b0b65bba9c22f68439a714cfae2b05995097d11b1`
sent the approved three questions/five excerpts in three answer calls. The agent
checked both supported answers against returned citations and registered claims:
holdout-03 and holdout-02 pass (HTTP 200; slices 34 and 187). holdout-10 correctly
said the excerpts lack composer information, but returned citation IDs with
`insufficient`; strict parsing rejected it (HTTP 503,
`status_citation_mismatch`). Raw capture now confirms this precise cause for this
new attempt; the previous pilot's lost response remains undiagnosed.
The overall gate failed, the run is closed, and no retry occurred. All three
attempts are spent, totaling USD 0.000726; none is uncertain. HTTP times were
3.420/1.238/1.113 seconds. This demonstrates two known-context answers, not
automatic retrieval quality. Agent evidence checks are complete; owner review
is optional via the new protocol's `run/results-review.html`.
Next: plan a structural output-contract improvement for insufficient/citation
consistency; avoid repeated prompt-only paid attempts. Normal answers remain
off. No implementation/model/ranking change or new test run in this execution;
the prior local implementation passed 532 backend tests. All changes remain
uncommitted, with diagnostics and explicit-selection tooling as recommended units.

**2026-10-15 selected-context answer reliability:** Answer instructions now spell
out empty citations for insufficient output, distinct supplied IDs for supported
output and the 1,500-character answer limit. Strict parsing reports bounded
reason codes through local structured logs while the public error stays
`ANSWER_OUTPUT_INVALID`. Approved pilot tooling stores private raw responses and
safe reason sidecars; capture-write failure preserves conservative accounting,
and diagnostic-write failure preserves the original settled rejection.
Explicit manifests freeze one-to-five saved slice IDs per case, their order,
current hashes/policy, changed prompt configuration and acknowledgement of the
closed prior protocol. Case-count/order checks and durable markers prevent
automatic restart; reports identify unsent cases. No new provider call, embedding,
DB write or policy change occurred. A new private preview has three questions and
five excerpts (supporting slices 34/187 and the negative case's saved top three),
estimate USD 0.005896, hard ceiling three calls/USD 0.03. Protocol:
`ddfd55c3054e58123361d80b0b65bba9c22f68439a714cfae2b05995097d11b1`.
Review `review-complete.html` in its private answer-preflight directory. It shows
required claims and pass criteria; these are never part of provider input.
Next: owner preview review, then separate exact-protocol transmission approval.
This known-context diagnostic will not establish automatic retrieval quality.
Implementation plan: `ANSWER_RELIABILITY_PLAN.md`; final checks: `ANSWER_SLICE.md`.

**2026-10-15 local answer diagnosis:** Saved anchor comparison places complete
gold support at rank 6 for both holdout-03 and holdout-02, outside the pilot's
top-three context (and outside top five). The product's manual passage selection
does not impose that pilot rule. Synthetic checks reproduce schema-valid but
parser-invalid citation/status/length combinations, plus incomplete/refused/
malformed output. The actual holdout-02 rejected field remains unknown because
its raw response was not retained. No provider request, DB write, model/prompt
or ranking change was made. Next: align output instructions with parser rules
and add body-free failure diagnostics, then separately review a sufficient-context
answer check. Preserve the failed run; these inspected cases are diagnostic data,
not fresh validation for tuning. Details: `ANSWER_SLICE.md` local diagnosis.

**2026-10-15 actual answer pilot:** The owner approved the fixed three-question/
nine-excerpt protocol, one run, at most three calls/USD 0.03. The run sent two
questions/six excerpts, then stopped without retry: holdout-03 returned
`insufficient` because its selected top-three snippets omit the location answer;
holdout-02 returned `ANSWER_OUTPUT_INVALID` after valid usage settlement.
holdout-10 was not sent. Both attempts are spent, totaling USD 0.000528; no
uncertain charge remains. HTTP times were 3.862 and 2.405 seconds. The first
abstention is appropriate for the sent context but does not satisfy the supported
question's end-to-end target. The second response's raw output was not retained
in this first run, so the rejected field cannot be diagnosed conclusively.
The pilot did not pass; no model/ranking setting changed and normal answers stay
off. New runner code prevents replay with an exclusive run marker and captures
bounded private provider output for future explicitly approved runs. A temporary
ledger-summary field-name error was corrected by a read-only ledger lookup;
there was no retransmission. Private output: the approved preflight's `run/`.
Next: inspect the selected-context gap and local validator diagnostics before
proposing another bounded check; this completed authorization does not permit a
second run. Actual unsupported/negative-case quality remains unverified.
Checks: final backend suite 500 passed, including preflight and durable-run
tests; both CLI help commands and whitespace checks passed. No frontend change.

**Phase 3.3 answer-quality preparation:** A local-only preflight now freezes up
to three reviewed questions and the top three saved Semantic hits per question,
checks current exact source ranges and AI policy, and writes a private HTML
transmission review plus a body-free protocol. The actual preview selects
holdout-03/02/10: three questions, nine excerpts, one run, three-call/USD 0.03
cap, conservative USD 0.006260 estimate. No new embedding, answer call, usage
reservation or DB permission change occurred. Four synthetic preflight tests
pass; the final full backend suite passed all 497 tests.
The exact review remains private under the validation dataset's
`answer-preflight/e2c9f60c69552f2a548b5876884a9c66f7e1ff0011f64fa74a742444b691b69d/`.
This is the preparation checkpoint; the approved actual run and runner now
supersede its pending-approval status. Criteria and results are in `ANSWER_SLICE.md`.

**2026-10-14 Phase 3.3 local-passage answer extension:** Search → Passages now
lets the owner choose one to five current content passages and request a cited
draft through the same separate answer consent. This works without Semantic
vectors or a paid question embedding. The server accepts either local Passage
IDs or Semantic slice IDs, never a mixture, and rechecks current exact text,
owner, source/record AI permission and deletion under the owner lock before and
after the answer call. Full local passages are bounded at 2,000 characters each
and 14 KiB per request. `ANSWER_MODE=off` remains the normal default. Synthetic
HTTP search → answer → citation and durable replay checks passed with no real
OpenAI transmission. Full backend 493 and frontend 125 tests, lint and build
passed. The owner still needs to verify this Passages UI extension; real answer
quality, automatic evidence selection and period retrospectives remain open.

**2026-10-13 Phase 3.3 first slice:** The existing Semantic result screen now lets
the owner select up to five exact current passages and request one cited draft
answer. The separate answer POST rechecks owner, version and external-AI permission
immediately before sending, then rechecks current permissions before returning
citations. It uses the shared durable monthly usage ledger with a USD 0.01 and
one-call cap per request. The UI requires a second explicit consent; neither the
question nor the draft answer is persisted. `ANSWER_MODE=off` is the default.
The owner confirmed this first synthetic answer flow on 2026-10-14. The demo
mocks the answer provider; personal answer generation and
answer-quality evaluation have not run. This slice supports selected current
passages only. Historical versions, date-range retrospectives and automatically
assembled multi-source context remain later Phase 3.3 work. The real populated
index still awaits owner browser confirmation. See `ANSWER_SLICE.md` for the
exact demo flow and remaining checks.

Checks: seven new backend answer tests, including before/after revocation,
durable paid replay and invalid citation handling; full backend 490 passed.
Frontend 124 passed, lint/build passed. Official OpenAI Responses/Structured
Outputs documentation and the pinned GPT-4.1 mini model page were checked.
The synthetic HTTP demo confirmed search, answer, exact citation and replay
rejection without an external request.

**2026-10-11 direction change; 2026-10-12 measurement:** The owner ended B1 model/ranking experiments
and approved optional Semantic search in B2. Earlier failed promotion decisions
remain failed. Semantic-only 17/18 on reused tuning cases supports trying an
optional feature, not a claim of independently validated quality. Hybrid and
reranking are deferred. The rerank response failure remains unresolved and its
diagnostic work is no longer a prerequisite for B2. No further paid run is scheduled.
Storage, indexing and Semantic API/UI are implemented. Keep existing local search
as the default. The untouched ten-case validation set was measured once under its
separate transmission/cost approval. Review the observed results and real-index
browser usability before defining 3.3. Policy/ownership/deletion/budget failures
still block delivery.
See `SEMANTIC_PRODUCT_PLAN.md` for the current implementation sequence. The
following B1 notes are historical results, not the active next-task instruction.

**B2 storage checkpoint:** pgvector `0.8.7` / PostgreSQL `17.11` on Debian trixie
is pinned by image digest in both compose files. The existing development volume
is retained; migration `f48d3e25c064` is applied. `PassageEmbedding` stores 1536-d
vectors with exact section offsets/hashes/config and a parent-passage cascade.
Internal publication rechecks current source/owner/policy revision under the
owner lock; reads independently join current permissions/index state. Existing
source invalidation removes disallowed derivatives in the same transaction.
Reallow cannot resurrect removed vectors. Shared section splitting preserves B1
behavior. At that checkpoint no indexing endpoint/worker existed and no real vector
or paid call was produced.

Checks: all 424 backend tests passed on the final pinned image, including 15 new
storage tests for exact Unicode ranges, idempotence/cosine ordering, invalid
vectors, ownership, edit/restore/delete, source/record denial, stale publication,
and upgrade/downgrade preservation. Original table fingerprints matched through
backup/restore and development upgrade (15 data tables; Alembic head changed).
Extension/vector dump/restore passed. Private 0600 backups and verification
metadata are under `.local/backups/semantic-storage-20261011/`. The first image
checked used a different PostgreSQL patch/OS base; the final image matches the
existing 17.11/trixie environment and the full suite was rerun on it successfully.
CLI migration/head and whitespace checks passed. No frontend files changed.
The storage-only notes above describe the first checkpoint. The indexing checkpoint
below supersedes its statement about endpoints/worker availability.
Setup and reproducible checks: `SEMANTIC_PRODUCT.md`.

**B2 indexing checkpoint:** Migration `g59e4f36d175` is applied to development.
Authenticated scope/cost preview and explicit activation create body-free
`EmbeddingRun`/`EmbeddingJob` rows. The separate embedding worker publishes current
vectors through the existing policy/cost boundary, at most 16 inputs/16,000 UTF-8
bytes per call. No activation means no dispatch. Future edits/new records require
the separate `follow_changes` option; default activation covers the current snapshot.
Pause/resume retains cumulative cost/call limits and resuming follow scopes catches
up eligible edits. Possible dispatch or lost paid results never retry automatically;
uncertain costs require reconciliation before an explicit job retry. Overlapping
follow scopes, including paused scopes, are rejected. Import workers are unchanged.

Checks: all 453 backend tests passed, including 29 indexing tests; all 110 frontend
tests, lint/build and generated OpenAPI types passed. Concurrent workers, pre-send
pause, post-send revocation, crash/lease recovery, timeout settlement, default denial,
future enrollment, cumulative limits and migration upgrade/downgrade were checked
with synthetic data/mock provider calls. Initial new-test import/budget fixture and
old-schema fixture errors were corrected before the successful final suite.
Development upgrade preserved all 16 existing data-table fingerprints. Metadata-only
preflight of the previously allowed 43 GitHub documents found 1,031 pending slices,
zero stored vectors, and an estimated conservative maximum of USD 0.008113; its
proposed run cap is USD 0.05 / 100 calls with future changes disabled. Private
manifests are in `.local/indexing/`; preservation metadata is in
`.local/verification/embedding-indexing-20261011/`. No real run/job was activated,
no permission changed and no new OpenAI request was made. CI now uses the same
pinned pgvector image; remote workflow execution remains unverified.
The indexing-only notes above describe the previous checkpoint.

**B2 Semantic API/UI checkpoint:** Search now offers optional Semantic alongside
Exact phrase and Passages. Review index shows local filtered coverage; a separate
checkbox/button explicitly sends one question embedding POST. Empty/disabled/
unconfigured indexes send nothing. The provider/cost gate is reused, and a
domain-separated request ID with a durable one-call limit prevents paid replay.
Query vectors stay in memory. Current allowed slices rank by exact cosine distance,
with up to 20 grouped results and no Entry quota. Verified GitHub slices group by
repository/path/hash even with different parent boundaries. Exact slice readers and
lazy locations independently recheck current owner/policy and do not require query
word matching. Permission revision changes before/after dispatch suppress results;
completed charges survive. Return/reload/filter changes never automatically POST.

Checks: full backend 474 passed; focused Semantic HTTP 21 passed; frontend 122,
lint/build and generated API types passed. Synthetic live HTTP Chromium checks
passed at 390/768/1440px for consent/query/exact reader/return/reload, no overflow,
browser errors or external requests. Demo login and the separate Vite proxy also
passed after correcting a harness wait for login completion. Failed local status
or reader revalidation hides cached evidence. In-app browser startup failed due to environment
sandbox metadata; standalone Chromium was used instead. Initial fixture-return and
TypeScript DOM iteration errors were corrected. Remote CI remains unverified.
`scripts/preview_semantic.py` serves two synthetic records and a mock provider in
a fresh schema of the separate test DB. It uses a separate JWT secret and drops
the schema on normal shutdown. Owner demo: API 8002, frontend 5174 proxy; login
`demo@example.test` / `demo-password`. Demo calls establish behavior, not quality.
Hard termination can leave a disposable schema; no development DB is used by it.

The owner confirmed the Semantic browser flow on 2026-10-12. The separately
approved real indexing and one untouched ten-case product-path evaluation are
complete; results are below. Next: review the observed limitation and choose the
Phase 3.3 scope. Hybrid, reranking and answer generation remain deferred.

**2026-10-12 product evaluation preflight (before activation):** The reviewed validation revision 2
still contains eight supported and two insufficient-evidence cases. A new local-only
preview binds its digest/question hashes to the current 43-document allowlist,
policy revision 483 and fixed product configuration. Current anchors and permissions
passed; no retrieval results were opened. At this checkpoint there were zero real runs/jobs/vectors.
The combined conservative estimate is USD 0.008139. Proposed hard limits are
USD 0.05/100 indexing calls plus USD 0.01/10 question calls (USD 0.06 total),
one validation pass, no follow changes or automatic retry. Fresh transmission
was then given explicitly for this exact scope. Previous experiment grants did not
activate the queue. No quality outcome was implied by the preflight alone.
Checks: full backend 483 passed; the final focused preview suite has nine passing
tests; frontend lint and whitespace checks passed. The first full run exposed a
new test's assumption that the shared usage table was empty; it now checks that
the preflight leaves pre-existing counts unchanged, and the full rerun passed.
Local metadata checks used a read-only transaction; the interactive password
prompt was checked via CLI help rather than a real authenticated CLI invocation.

**2026-10-12 real B2 measurement:** The explicitly approved snapshot run indexed
all 1,031 slices from 43 permitted GitHub documents in 65 OpenAI calls, spending
878 micro-USD. Ten distinct reviewed questions were sent once each through
`POST /semantic/search` (10 calls, 11 micro-USD). Total spent: USD 0.000889,
below the USD 0.06/110-call authorization. All attempts settled as spent; no
uncertain attempt or retry. Independent ledger read confirmed 1,031 ready jobs and
1,031 current vectors. The authenticated local status endpoint for GitHub documents
reports 44 matched, 43 allowed/indexed, 1,031 ready, policy revision 483.

On the eight supported cases, exact gold-range coverage in the first 20 grouped
results was Semantic 7/8 and current Passages 5/8. Semantic met the planned
0.80 recall and 0.70 complete-evidence reference levels at 0.875 each. Both
insufficient-evidence cases were diagnostic only; the product does not yet make
answers or abstain. Semantic lost one Passages success at rank 5 (holdout-02 moved
from rank 1 to rank 6), none at ranks 10/20. One Korean question, holdout-01,
missed the exact support span in both methods: Semantic ranked a title slice from
the correct Entry at 5, but its required content range was outside the top 20.
Another Korean case, holdout-07, found its support only at rank 17. Among four
supported Korean questions, Semantic found 3/4 by rank 20 and 1/4 by rank 5.
The earlier B0 early-loss criterion is retained only as historical context;
Passages here is the actual local comparison, not a reproduced B0 run.

The in-process authenticated Semantic POST median was 0.605 seconds, maximum
0.812 seconds for these ten calls. Timing excludes browser rendering and separate
evidence-reader requests. The complete private body-free per-case report is under
`.local/verification/semantic-product-20261012/report.json`. This is a small,
single-repository validation set; it supports a limited B2 result, not a general
search quality guarantee or automatic Phase 3.3 answer rollout. The owner has not
yet checked the newly populated real index in the browser.

Phase 3.2B1 tooling and the first owner-approved real OpenAI experiment are complete.
The expanded two-capture follow-up is complete and failed held-out validation;
B2 remains deferred. The frozen condition removes the early Entry quota and keeps
the final quota. It is experimental only; browser search has not changed.
The provider defaults off; the owner's ignored local configuration enables OpenAI.
A body-only current-passage gate, explicit query consent, durable project-wide
cost reservations/reconciliation and authenticated dry-run/run CLI are available.
Vectors remain in bounded memory; reports/manifests contain no source/query bodies.
Development migration `e26b9c13a842` is applied. Synthetic integration checks cover
durable dispatch, timeout accounting, owner-lock serialization, empty-month budget
races, CLI comparison and stale manifests.

On 2026-10-09 the owner approved transmission of 43 GitHub documents/267 body
passages and three frozen pilot questions for `b@test.com`, `repo:1228467402`.
The repository source policy and those 43 record permissions were enabled and
remain enabled; other record permissions were not changed. A fresh explicit-ID
manifest estimated at most USD 0.007779. Run `b438d06014304c9ea8c5ddb6dc2b5741`
completed 28 calls (25 document batches/3 questions), 81,572 tokens, in 16.13s.
All usage is settled as spent: USD 0.001643 in the conservatively rounded app ledger.
The two Korean questions failed complete gold-span coverage at top 20 in all
three methods. The English gold span ranked lexical 1, semantic 19, hybrid 4.
There were 171 non-gold groups; the B2 benefit gate is `criteria_not_met`.
Existing search remains unchanged. The diagnostic follow-up below identifies the
failed ranking stages; the smaller-chunk experiment below is also measured.
The private report contains IDs/scores/usage only; vectors remain memory-only.
B1 omits commit diffs, LOGs and work passages by default. B2 pgvector/worker/browser
semantic modes are not implemented and await demonstrated B1 benefit and owner confirmation.
Plan: `SEMANTIC_SEARCH_PLAN.md`; commands: `SEMANTIC_SEARCH.md`.
Final B1 checks: 357 backend tests passed, including 18 focused semantic tests;
migration upgrade, CLI integration and whitespace checks passed. Earlier CLI vector
unwrapping and committed synthetic-fixture cleanup failures were corrected.

Follow-up diagnostics now record gold coverage ranks after raw ordering, exact
grouping, the two-results-per-Entry quota, the 100-candidate cap and top-20 cutoff.
They contain counts/ranks only and do not affect ranking or gold scoring. Approved
same-scope run `e5487232da5b43daaeac88f2794ece14` reproduced all first-run method
scores and passage lists: Korean pilot-01 ranked 46 raw / 25 grouped / 24 after
quota, then missed top 20; pilot-02 ranked 61 / 38 and was dropped by the quota.
English ranked 27 raw / 19 grouped and retained rank 19. Each gold span fits in
one chunk, so split evidence is not the cause. Removing the quota alone cannot
recover either Korean case at top 20. The repeat used 28 successful calls and
USD 0.001643 in ledger cost (both runs total USD 0.003286); no uncertain attempts.
The section-aware experiment below tests smaller chunks with the same frozen
gold, model and document scope. B2 remains gated.
Follow-up checks: 359 backend tests passed (20 semantic tests); first/repeat method
scores and passage lists matched exactly, and whitespace checks passed.

The `sections-600-v1` B1 option now splits allowed parent passages into exact
subranges of at most 600 characters, preferring Markdown headings/paragraphs.
It does not modify the live index. Each send rechecks the parent ID/hash, owner,
AI permission and exact subrange/hash; lexical scores use PostgreSQL simple FTS
on the same experimental slices. Metadata maps experimental IDs to parent readers.
Same-scope run `715294e643b14fe99f7baa74fb53f29f` processed 1,031 subranges from
the same 43 documents/267 parent passages and three frozen questions. Semantic
gold ranks improved to 16/11 for Korean; hybrid recovered only pilot-02 at 15.
English remained lexical rank 1 but was lost in semantic/hybrid: its complete
gold chunk ranked 14 after grouping, then was removed by the Entry quota.
All three gold spans still fit within individual chunks. The B2 gate remains
`criteria_not_met`; smaller chunks alone are insufficient. Next proposal: examine
candidate quotas and fusion with the same frozen evidence, preserving the English
lexical success before considering B2. No automatic next paid run is scheduled.
The run took 33.86s, 68 successful calls/81,584 tokens, USD 0.001668 in ledger cost;
three-run total is USD 0.004954, with no uncertain attempts. Checks: 369 backend
tests passed (30 semantic/chunk tests), CLI help and whitespace passed. An initial
test-module import error was corrected before these successful runs.

Follow-up plan reviewed on 2026-10-09: `SEMANTIC_EXPERIMENT_PLAN.md` is the next
B1 work plan. Implement private candidate-rank capture/replay, predeclare four
quota-placement comparisons, and prepare about 20 questions split into 10 tuning
and 10 validation cases before another capture. The existing pilot is tuning data,
not independent validation; 43 snapshots cover 13 document paths. Additional
questions require their own scoped transmission consent. Review itself made no
API call or policy change.

The follow-up tools are implemented: `--capture-ranks` saves
private complete ranks after a successful run, and authenticated `--replay`
compares fixed A–D quota conditions without a provider call. Replay checks live
owner/database/dataset/corpus/policy/config bindings, rejects damaged inputs,
and requires exact A ordering/coverage/score reproduction. Reports include
document-family concentration; insufficient-evidence cases remain manual review
and do not enter positive recall scores. B2 still requires independent validation.
Private review folder `quota-review-72a1f8146022447ea30215fdd527f0f6` under
`.local/evaluation/` contains `review.html`, two ten-case datasets and body-private
review metadata. All twenty cases are now owner-approved in revision 2 (the three
pilot cases, fifteen additional supported cases and two insufficient-evidence
cases). The document paths are split between
tuning and validation; validation includes four Korean-to-English and four
English supported questions. The two-capture estimate was USD 0.016279 and was
confirmed against fresh approved manifests before dispatch. Completed capture,
freeze and validation results follow below. The private review must not be committed.
Checkpoint checks: 375 backend tests passed, CLI help and whitespace checks passed.
The first full-suite attempt hit the 256MiB process-peak guard in nine experiment
tests after unrelated tests accumulated memory. Experiment tests now use a
controlled RSS fixture and separately verify over-limit failure; the production
guard is unchanged. Private datasets, split membership, HTML parsing and 0600
file permissions were checked. Synthetic integration uses a mocked provider;
owner-authorized real capture/replay results are recorded below.

On 2026-10-10 the owner approved the seventeen new cases and transmission of the
same 43 documents/all twenty questions for two captures. Both private datasets
are revision 2; `consent.json` and pre-run `protocol.json` record the grant and
selection policy. No DB AI policy was changed. Tuning capture
`9abebf70107b4e7f9b529df874572149` measured A/B/C/D at 8/9/8/7 complete hits out
of ten. Only B satisfied the selection requirements without losing a lexical
success; immutable `freeze.json` pins B and the validation dataset before its run.
Validation capture `83810bb5b61e4278ac9629adb10fac83` found complete evidence in
5/8 positive cases with frozen B hybrid (lexical 5/8, semantic 7/8). It lost one
lexical success and recovered one Korean miss. B2 is `criteria_not_met`.
Two negative cases keep null recall and manual review flags; no generated answer
or abstention assessment exists. Private result files preserve the failed result;
the earlier draft review HTML remains an immutable historical preview.
Each run made 75 calls, costing USD 0.001675/0.001676 and taking 33.83/30.86s.
Total USD 0.003351; cumulative experiment cost USD 0.008305, no uncertain attempts.
Both A replays matched original IDs/order/aliases/scores, with zero provider calls.
Checks: 378 backend tests passed, CLI help/whitespace checks passed. No frontend,
schema, dependency or persistent vector change was made. Next: report failures,
review fusion and the final Entry quota in a separate plan; if this held-out set
is used for further tuning, a new validation set is required. No further paid
experiment or B2 implementation has started. This completes the approved round.

The next B1 fusion tooling is implemented: separate B0/R/P/S replay rules,
protected top-five leaders from both lanes, bounded body-free rank traces,
legacy baseline equivalence checks and freeze/validation helpers. Synthetic
checks cover quota loss, protection, aliases, ties, report integrity, policy
changes and no-provider replay. Browser ranking remains unchanged.
Fresh independent validation drafts are prepared at
`.local/evaluation/fusion-review-b7a96801f0474c19901d9f5cdc7159b6/review.html`:
eight supported questions (four Korean-to-English, four English), two negative
candidates and four previously unused gold-document paths. The owner approved
all ten; validation revision 2 was fixed before opening the new tuning results.
Private HTML, dataset composition, exact positive anchors and file permissions
were checked. `protocol-v2-draft.json` records the current pre-review settings.
Checks: 385 backend tests passed; CLI help and tracked/untracked whitespace checks
passed. No frontend, schema or dependency change was needed.
Both old captures were replayed locally as twenty tuning cases (18 supported,
two negative). B0/R/P/S complete @20 hits were 14/13/14/17 out of 18. R/P failed
recall >=0.80; S lost two B0 @5 successes, exceeding the allowed one. No candidate
qualified; `freeze.json` records `no_candidate`. The round stops without a new
provider call, independent capture or B2. Six non-gold candidate excerpts were
inspected: related snapshots, title-only chunks and introductory paragraphs can
rank ahead of direct evidence. This is a limited relevance review, not full labeling.
Private `results.html` contains the comparison and early-rank losses. Related tests:
7 passed after real replay; report integrity/private permission checks passed.
The `SEMANTIC_RERANK_PLAN.md` local tools and guarded caller are implemented;
the owner-approved real round stopped on its first invalid grade response, as
recorded below. Candidate union uses semantic/lexical top 50 each,
opaque IDs in group order, one bounded strict-grade request per question and
grade/RRF/group ordering. Private capture/replay, T freeze/validation helpers,
owner-locked exact-slice egress, shared billing locks and separate input/output
reservations are available. Rerank defaults off. Migration `e37c2d14b953` is applied
to development; upgrade preserves old embedding records and their cost semantics.
Existing browser ranking, section chunks, gold and old captures remain unchanged.
Real local preflight verified both old captures/current policy: all 18 positive
questions have full gold coverage in the fixed candidates, including valid-05.
Twenty questions select 51–86 candidates each, 1,331 total from 37 representative
documents within the existing 43-document scope. Estimated maximum is USD 0.411324;
proposed round cap USD 0.75, maximum 20 calls, no document re-embedding in tuning.
Private review: `.local/evaluation/rerank-review-2731b5483d014a0b8d259b68efd95210/review-v2.html`.
Both manifests and `protocol-draft.json` pin the rules/price/dataset/requests. Existing
monthly cap remains USD 1; exposure at preflight USD 0.008305. Preflight made no
consent or .env change; the later explicit run grant is recorded below. The ten
approved held-out cases remain unmeasured.
Checks: 409 backend tests passed, CLI help/whitespace checks and private file/digest
checks passed. Synthetic coverage includes malformed grades, Unicode payloads,
spent/uncertain/released accounting, no-provider replay, immutable attempt markers,
owner policy locks, shared call slots, freeze/no-reselection and migration preservation.
The first new CLI fixture used the wrong private root; it was corrected and the
full suite rerun successfully. Account model access and the actual response failure
were subsequently verified in the owner-approved round below.
Preserve these failed results and the approved, still-unmeasured ten-case held-out set.

On 2026-10-11 the owner approved one rerank round: the old twenty questions and
1,331 candidate placements, at most twenty calls and USD 0.75. Fresh manifests,
live policies, unchanged rules/prices and snapshot model access passed preflight.
Run `12aa580dbb7545278e4d9234118cd79a` sent only `pilot-01` and its 74 candidate
bodies. Valid model/usage metadata was received, but grade validation failed with
`RERANK_GRADES_INVALID`; execution stopped without retry or remaining dispatches.
The single paid call used 8,532 input/30 output tokens and settled USD 0.003461 as
spent, with no uncertain reservation. Cumulative experiment spend is USD 0.011766.
Private `failure.json`, `usage.json`, the immutable attempt marker and failed
zero-case capture preserve the result under the rerank review folder above.
No retrieval-quality score or T selection is available; this is an execution
failure, not measured recall failure. The discarded response is not retained, and
the generic error cannot distinguish refusal, shape or candidate-ID errors.
If reranking is revisited, add body-free failure diagnostics and test the rejection
branches before proposing a new paid attempt. Do not rerun this round or alter the frozen prompt
to optimize unseen quality. The fresh ten-case set has not been sent or measured;
B2/browser ranking remains unchanged. Focused rerank checks: 24 passed after the
real failure; the prior full implementation suite passed all 409 tests.

Phase 3.2A local passage retrieval is implemented and owner browser checks 1–5
are confirmed, including disposable note create/edit/delete search updates.
The passage reader now has dedicated desktop/mobile inner padding.
Search keeps Exact phrase and adds Passages with current-version source offsets,
bounded original readers, lazy retained-snapshot locations and preserved return URLs.
PostgreSQL simple FTS ranks body matches; identical verified GitHub document chunks
group before representative-Entry quotas and pagination. Source-deleted records are
excluded by default and can be explicitly included locally. No embedding, answer,
external AI request, dependency, queue or worker was added.

Migration `d15e8a02b731` is applied to development. Create/edit/select/reimport and
delete synchronize disposable current passages in the source transaction; historical
versions remain unchanged. The authenticated `scripts/index_passages.py` resumes
bounded owner-scoped backfill. The selected `b@test.com` account has 480 ready records
(448 real and 32 synthetic); backfill took 3.73 seconds and preserved the source/policy
manifest. Existing records in other accounts may still need backfill.

The owner authorized necessary real-record reads by the current Codex for this
development/verification. This does not change application AI policies, authorize
embedding/answer API transmission or share private sources with Antigravity.
The frozen three-question pilot remains revision 2. Same-snapshot literal versus
passage checks found natural-question support in 0/3 versus 1/3 cases; the two Korean
questions still fail. Auxiliary mean recall@20 was 1/3 versus 1, scoring complete
gold spans and verified snapshot aliases for passages. This is one English README,
not broad semantic-search quality. Original dataset/baseline reports remain intact.

Disposable migrated PostgreSQL/HTTP/Chromium checks cover owner/current boundaries,
edit/delete/restore, Codex primary/work mapping, snapshot filters/grouping, pinned
readers and 390/768/1440px returns/layout; no external browser requests occurred.
Plan: `PASSAGE_SEARCH_PLAN.md`; operations: `PASSAGE_SEARCH.md`. In-app browser
connection failed; separate Chromium provided the synthetic browser verification.
Final checks: 339 backend tests, 110 frontend tests, lint/build, migration upgrade,
OpenAPI alignment and tracked/untracked whitespace checks passed. The 42 targeted
passage/evaluation tests include source rollback on projection failure.

Phase 3.1 evaluation tooling is implemented; the real private set is not complete.
Owner-selected account: `b@test.com`. The owner initialized the private set locally;
the original set is now revision 6 with all 20 cases draft. The owner returned
case-04 to draft after its first registration/semantic review; revision 5's reports
remain historical provisional results. A separate three-question private pilot
now has three owner-approved answers in revision 2, each linked to an exact valid
span from one retained README snapshot. Both baselines completed: natural questions
found no results; auxiliary mean group recall@20 is 1/3 (two cases found the target
with one of two queries each, at rank 12; the other case found neither within top 20).
All three scored cases passed evidence checks with no failures. These are a limited
first baseline, not a broad corpus or answer-quality guarantee.
This smaller first check preserves the roadmap's eventual diverse about-20-question target.
The retained
corpus has 415 real GitHub and 33 Codex records;
32 synthetic records were excluded. All records currently deny external AI.
The owner explicitly authorized limited agent reads of case-04's selected claim/span
and selected source excerpts for three pilot questions; source policy settings remain
unchanged. Those were scoped authoring permissions; the later development-read
authorization is described above. Keyword matches do not prove factual support.
The three-question pilot was owner-approved and both fixed baselines were run;
the original 20-case set still needs verified facts and evidence.
No owner password was supplied to the agent. The owner ran the provisional case-04
baseline locally; the pilot was approved after explicit owner confirmation and
scored in a read-only snapshot. Original reports and source AI settings remain intact.
Owner checked case-04: the linked candidate mainly identifies code location and
does not clearly answer the worker's purpose/execution location.
Its old support was removed in revision 3; the tentative insufficient-evidence case
was superseded in revision 4 after the owner reported supporting sentences.
The owner registered revision 5 locally. On explicit one-time permission, the agent
read only that case's entered claim and selected excerpt: the claim does not directly
answer the question, and the selected span does not support all requested aspects.
Hash/owner/version validation passed; semantic approval is not established by those
checks. Case-04 is now draft and excluded from future scored denominators.
Primary retrieval found no result; one of two auxiliary queries hit the evidence at
rank 1, the other found none (mean group recall@20 0.5). These are retrieval measurements.
An owner-only local review sheet shows pinned saved excerpts and up to five other
keyword matches per case (37 alternatives in this snapshot), using saved filters.
No candidate was automatically approved. This private HTML contains source text
and must stay local; measurement reports continue to omit source bodies.
The CLI uses read-only PostgreSQL snapshots, immutable private revisions, the same
keyword search conditions/ranking as the API, versioned passage hashes and body-free
reports. Natural questions and auxiliary keyword scores are separate. Synthetic
20-case migrated-schema verification and Chromium reports passed; no schema,
dependency, AI call or worker was added. Plan: `EVALUATION_PLAN.md`.

Phase 2.4B GitHub discussions is implemented; the owner confirmed the synthetic
browser flow using `GITHUB_DISCUSSIONS.md`. A separate manual collector prepares/seals/applies
PRs/issues/comments/reviews, retaining independent versions and policy/deletion
boundaries. Repository Discussions groups roots before pagination, reads children
lazily, preserves missing-parent groups, and focuses Search hits on their page.
No migration, dependency, worker, external AI or AWS service was added.
Selected `moonkongv2/jy_yamyam` has 0 PRs/issues as of 2026-10-06: real empty
preparation and isolated PostgreSQL/HTTP apply/replay passed. A labeled 30-record
fixture passed isolated HTTP/Chromium checks; live nonempty/private sources and
personal-account apply remain unverified. Plan: `GITHUB_DISCUSSIONS_PLAN.md`.
Final local checks: 297 backend tests, 104 frontend tests, lint/build and whitespace
checks passed. The existing sealed 415-item Phase 2.4A preview still validates.

GitHub repository browsing checkpoint after Phase 2.4A is implemented;
owner browser confirmation is next. Entries groups GitHub by numeric repository
scope before pagination. Repository pages show source-date ordered commits and
path-grouped retained document snapshots, with separate document/snapshot pages.
Search stays Entry-level with repository context; readers/sidebar preserve return
URLs. Existing Entries, versions, permissions and receipts are unchanged.
No migration, dependency, external AI call or service was added.
Implementation plan: `GITHUB_REPOSITORY_VIEW_PLAN.md`; checks: `GITHUB_BACKFILL.md`.

Phase 2.4A GitHub commits/document backfill is implemented with local checks;
owner verification is next using `GITHUB_BACKFILL.md`. Strict run/evidence contracts,
pinned resumable preparation, reviewed apply, Sources results and GitHub readers
reuse the existing PostgreSQL history/receipt model; no migration/dependency was
needed. The plan and implementation are included in this Phase 2.4A commit;
owner verification remains pending.
Full selected public preparation is finished: 372 commits + 43 document snapshots
(415 items), following quota pauses and owner-selected GitHub CLI authentication.
All 415 were verified in isolated PostgreSQL + real HTTP/browser; same/equivalent
preview replay, owner/policy/annotation/delete checks passed. Oldest/latest source
samples match fresh GitHub reads. The sealed full preview is private; no personal
account apply was run. Evidence omissions correctly finish Partial. Owner account
apply/browser confirmation and private/org access remain pending. The owner explicitly
requested implementing Phase 2.4B while those confirmations remain pending.
Authentication/verification follow-up: `48f6f52`.
Codex plan: `bdfcd57`; session browsing: `ab40b30`; saved titles: `fd7597b`;
conversation-only reading: `2598187`. Local checks pass. Development DB upgraded to
`c04d8a12e673`. Phase 2.3 implementation is committed at `36de1de` with whitespace
cleanup at `63f0c1a`; owner confirmed its preview. Personal apply remains unverified.
Phase 2.1 committed at `69dc764`; owner requested continuing without its HTML
preview check. Phase 2.2 committed at `d99ef9e`. The owner
confirmed successful synthetic-demo execution (Entry 1270) and authorized the
commit; the complete browser scenarios in `HISTORY.md` remain pending.
Phase 2.2 migration `a22b8c30d567` gave all 1,266 existing Entries one
initial observed version; source timestamps/history were not invented.
Local API health/new routes verified and import/purge worker restarted.
The owner requested a Notebook-inspired frontend refresh before further collection
work, followed by separating Search from recent Entries. Implementation and local
checks are complete. The owner requested English-control/session fixes after
browser review and authorized committing the UI checkpoint. The broader visual
walkthrough remains available in `frontend/README.md`.
UI checkpoint: `19e395a`. Owner confirmed B synthetic discussion browsing;
A repository browsing and personal apply remain separate pending checks.

## Personal-release target

Finish private daily use before commercial service work. Prioritize past
solutions and decision reasons, then period retrospectives, then project
resumption; include ordinary life records without requiring a project.
The agreed additional sources are Codex CLI on one Mac and selected personal/
organization GitHub repositories, including accessible historical records.
Both need scheduled collection and collect-now controls. GitHub delivery starts
with commits and key documents; PRs/issues remain in scope.

The release must support access from other devices/external networks, prefer
AWS, and fit a combined hosting/storage/AI budget of USD 20/month. Version
retention, deletion suppression, and source/repository/record-level external-AI
exclusions are implemented foundations; full collectors remain upcoming.

## What works now

- Private evaluation CLI: init/draft/review-sheet/record-answer/edit/inspect/anchor/validate/review/run with explicit
  local authentication, owner/database binding, immutable revisions and fixed queries.
  Current-vs-historical evidence, AI eligibility, collection gaps and failed-score
  denominators remain explicit. Synthetic fixture readiness never counts as the
  real evaluation set. First full backend check failed 5 tests because the concurrent
  evaluation test left committed fixture rows; fixture cleanup fixed that and the
  rerun passed 316 tests; final checks including local candidate authoring passed
  319 backend tests (22 evaluation tests). Reports passed 390/1440px standalone Chromium checks with
  no page errors, outbound requests or document overflow. Real owner data/large
  corpus benchmarks remain pending; private files stay in ignored `.local/evaluation/`.
  Candidate claims cannot be approved unchanged. There are no explicit SHA overlaps
  between these retained Codex turns and GitHub commits; life/PR/issue support remains
  incomplete. Candidate relevance and adopted decisions require owner verification.
  Review previews validate owner/version/hash before displaying excerpts, omit
  deleted/stale/invalid spans, escape source HTML and keep immutable private files.
  Export does not edit evidence, approvals, records or policies. Regenerate after
  changes; saved local HTML is a snapshot and may retain previously exported text.
  Final follow-up checks: 322 backend tests (25 evaluation tests), compile/help and
  whitespace checks passed. Synthetic review expansion/escaping passed Chromium at
  390/768/1440px without errors, outbound requests or overflow. An initial excerpt
  test exposed a missing first character; correcting the paragraph boundary fixed it.
  Guided record-answer lets the owner select evidence, enter each verified fact,
  explicitly approve, save one immutable revision and generate both baselines.
  Canceling before approval saves nothing; benchmark failures after registration
  leave the approved revision intact and can be retried with run.
  Latest registration checks: 324 backend tests (27 evaluation tests), compile/help
  and whitespace passed. Synthetic end-to-end registration confirms two claims,
  two reports, unchanged source AI policy and cancellation without publication.

- GitHub discussions: typed source IDs, immutable private previews, mutable-source
  staged resume, kind-count receipt checks and existing observed-version rules.
  Discussions tab, per-root lists, orphan-date filters, lazy comments/reviews/code
  context, individual history/deletion, SHA role links and search focus work.
  Selected actual source is empty; synthetic 30-record real HTTP/browser checks
  cover paging/reload/readers/search/Sources at 320/390/768/1440px without overflow
  or page errors. Test details and owner walkthrough are in `GITHUB_DISCUSSIONS.md`.

- GitHub repository browsing: owner-scoped grouping before archive pagination,
  compact chronological commits, document paths and historical snapshots,
  individual search references and reader/sidebar return preservation. Latest
  checks: 282 backend tests, 97 frontend tests, lint/build, generated API types
  and whitespace checks passed. Actual 415-item isolated PostgreSQL/HTTP checks
  show one repository, 372 commits, 13 document paths and 43 snapshots, preserving
  replay/annotation/AI-deny/deletion behavior. Real HTTP Chromium navigation,
  reload/new-tab/search returns passed at 320/390/768/1440px with no page errors
  or horizontal overflow. Early sandbox TCP and browser transport teardown issues
  were resolved by the approved DB run and corrected verification cleanup.
  Personal account apply and owner browsing confirmation remain pending.

- GitHub commit/diff and historical Markdown snapshot collection: private cached
  preparation with pinned heads, quota pause/resume, immutable preview validation,
  authenticated idempotent apply and owner/policy/deletion checks. Sources provider
  switching and current-version evidence readers connect related commit/doc records.
  Backend 276 tests and frontend 87 tests passed; Chromium synthetic UI checks fit
  320/390/768/1440px. Final lint/build and OpenAPI consistency checks are recorded
  in `GITHUB_BACKFILL.md`. No real account apply was performed.

- Entries groups current Codex turns by owner/scope/thread before server pagination;
  other records remain individual. Sessions retain fork/archive/gap metadata,
  inferred-order warnings, lazy turn reading and focus links from Search.
  Final answers and unknown messages stay in primary reading/search; explicitly
  classified commentary stays in Work details and an optional search scope.
  Per-turn history, annotation, delete/suppression and AI permission remain intact.
  Read turn and Codex Entry detail show only user/assistant messages, excluding
  classified commentary. Commands/results/diffs remain in Work details and search.
  Collection gaps are a separate notice. Existing structured records need no
  recollection; records without valid structured evidence retain a warned full view.
  Current-version primary_content is derived separately; existing bodies/hashes
  remain unchanged. v1 manifests/receipts remain valid, v2 records phase/order.
  Session titles prefer saved Codex names; fallback titles normalize whitespace
  and cap display at 60 characters plus an ellipsis. First questions appear in
  separate two-line card previews. Original turn titles/content remain unchanged.
- Latest checks: 249 backend tests, 83 frontend tests, lint/build and whitespace
  checks pass. Real loopback HTTP/isolated-schema verification covers 25 synthetic
  turns, search scope, grouped count/focus and replay without duplicate versions.
  Synthetic Chromium checks pass at 320/390/768/1440px with no page errors.
  An initial full run's health test used an offline development DB; corrected
  DATABASE_URL/TEST_DATABASE_URL isolated settings passed. Frontend old list/cache
  assertions were updated for archive; an initial browser stub intercepted module
  imports and was corrected. No unresolved check failures remain.
  The added snapshot-index test initially called a yielded generator as a function;
  correcting that test passed. Saved-name sanitization, latest valid index row,
  legacy serialization, name priority and fallback/preview are covered.
  Final targeted rerun hit sandbox TCP restrictions; the approved host rerun
  passed all 28 collector/session tests. No application failure remained.
  The new conversation test initially omitted required command/diff item IDs;
  correcting its fixture passed. Reading excludes tools without changing search,
  evidence, versions, or command-like text inside an assistant answer.
  The supplied sample.html matched a private preview: seven command/result blocks
  are excluded from reading, leaving two messages (18,485 → 2,404 characters),
  with no server writes. Synthetic Chromium reading/work checks pass at four widths.
- Installed CLI 0.160.0 schemas and actual bounded reads verified: 33 turns from
  10 selected readable lifhop sessions, with 63 commentary and 32 final messages.
  Original v1 preview's 33 payload digests remain unchanged. New private v2 preview
  is `.local/verification/codex-session-v2/preview`; it has not been uploaded.
  A separate title-verified preview at `.local/verification/codex-session-titles-verified/preview`
  captures saved names for 4 sessions/25 turns. The owner's local apply checkpoint
  acknowledges all 33 turns; final run status and current-version UI are unverified.
  `scripts/seed_codex_session_demo.py` creates an explicit synthetic 25-turn local
  source for user checks. See CODEX_BACKFILL.md.
- Codex CLI 0.158.0 manual backfill: explicit project/thread selection, exclusions
  and date filters, immutable private sanitized preview, device-scoped turn IDs,
  bounded official reads against disposable snapshots and explicit gaps.
  Authenticated direct HTTP apply saves Entry/version and receipt atomically;
  interruption/lost acknowledgment can resume without duplication. Server receipts
  verify local checkpoint skips. Ownership, collection policy, deletion suppression,
  annotations and AI-off defaults are preserved. No S3, worker or new AWS service
  is required for Codex text ingestion. Sources displays paginated runs/coverage;
  Search and version inspection show ordered recorded evidence and omissions.
  See `CODEX_BACKFILL.md` for execution and verification.
- Phase 2.3 checks: 237 backend tests with fresh-schema migrations, including actual
  loopback HTTP synthetic apply/replay and pre-commit rollback; 80 frontend tests,
  lint/build pass. Synthetic Chromium Sources/search/evidence/failure/retry checks
  pass at 320/390/768/1440px. A final-suite setup attempt used the wrong test DB
  account; the corrected rerun passed. Actual private preview selected 13 of 171
  files, read 10 sessions, failed 3 and prepared 33 turns; SOURCE_CONFLICT and
  EMPTY_HISTORY remain gaps. Personal source content has not been uploaded.
- FastAPI/PostgreSQL backend with authentication and user-owned Entries.
- Observed versions, explicit current pointer, source identity/locator/times,
  content/evidence SHA-256, parser/completeness and original-material links.
  Newer complete snapshots replace current; older/partial/unknown-time candidates
  remain inspectable. Unchanged replay has no duplicate Entry/version.
- Imported content read-only; separate personal annotations survive imports.
  Manual editing works. Browser history/provenance and explicit version selection.
- Confirmed source-deletion markers retain content; unavailable/unknown is distinct.
  Search explicitly filters source state and otherwise includes retained records.
- Lifhop deletion removes body/versions/annotations immediately, blocks reimport
  through minimal identities, and durably queues original purge in the worker.
  Shared ZIP deletion blocks/removes the entire raw object, preserving other text.
- Sources UI separates collection and AI permission; AI starts disabled at source
  and record levels. Egress guard checks every dependency/policy revision; mocked
  embeddings/reranking/summary/answer/telemetry deny tests pass. No AI provider is
  connected. Latest deletion-ledger export/apply protects isolated restores.
- Owner-scoped literal phrase search in title/content, combined source/type/date
  filters, total counts, and 20-record browser pagination. Search has its own
  `/search` screen; `/entries` shows recent records. Empty Search makes no API
  request; keyword and filter-only searches apply on submission. Old filtered
  `/entries` URLs redirect to Search. Validated detail return URLs preserve
  origin, conditions and page across sidebar navigation, reload and new tabs.
  Entries pagination survives note creation/cancellation.
- Title matches rank before body matches, then newest registration and ID. Dates
  are displayed/filtered in Asia/Seoul; registration and source/event dates are
  separate. Missing event dates are never inferred from text.
- New notes/Markdown imports have explicit provenance. Only old Markdown rows
  with matching owner/artifact MIME evidence are backfilled; other unproven
  sources remain unknown. User/date/ID index supports ordered browsing.
- Browser Markdown/ChatGPT ZIP upload, job polling/history, saved progress counts,
  sanitized item errors, paginated result Entries, retry, and protected originals.
- Local SeaweedFS storage and PostgreSQL ImportJob queue are defaults; explicit
  AWS S3/SQS modes remain available. Worker startup is separate from the API.
- Original artifact links on newly imported Entries; persisted job result IDs.
- ZIP upload/download uses bounded streams and temporary files. Legacy and
  numbered conversation JSON arrays are parsed one record at a time. Defaults:
  ZIP 1 GiB, declared archive 1 GiB, JSON 256 MiB, one record 16 MiB.
- Entries and progress commit together every 25 items. An owner session lock on
  a pinned PostgreSQL connection serializes imports across commits. Interrupted
  attempts resume from durable counts; full item-error retries replay the file.
  Three attempts, completed-delivery no-op, and item savepoints remain.
- S3-backed Entry attachments.
- Local S3-compatible storage is the default for development; tests block
  unexpected AWS client creation.
- React login, Entry list/detail, and note creation/editing/deletion using
  authenticated Entry APIs and server-result cache updates.
- English interface labels, instructions, job statuses, and frontend error messages.
  Dates use English formatting in Asia/Seoul; user content retains its language.
  Search/Markdown date controls use an English calendar and `YYYY-MM-DD`;
  Markdown time uses `HH:mm` in the device timezone. File selection and form
  validation messages stay English even with a Korean browser locale.
  Login changes to Logout after authentication. Logout clears tokens/private
  query caches, redirects to Login, and propagates to other tabs. API 401 responses
  end the matching session with an English notice; stale responses cannot restore
  the previous session's record cache.
- Light panel UI: collapsible Search filters and preview cards; detail record navigation,
  full-text reader, and annotations/history. Import, Sources, job, note, and login
  pages share the same styles. Narrow screens stack panels. Delete lives in the
  record actions menu with an explicit confirmation near the top of the reader.
  Switching records resets the previous edit state and preserves list filters.
- Empty/loading/error states, draft-preserving save errors, title validation,
  deletion confirmation, and account-switch cache clearing.
- Read-only Codex/GitHub verification CLI produces private local HTML/JSON previews,
  with source IDs/dates, command outcomes/diffs, coverage, and omissions. These
  Phase 2.1 commands do no Entry writes, uploads, model execution or scheduling;
  Phase 2.3 adds a separate explicit Codex apply command.
- Codex CLI 0.158.0 official app-server reads run against disposable rollout/history
  DB copies. Local inventory: 169 files; selected historical sample: 3 turns,
  22 command items and 3 file-change items; list/turn pagination verified.
- Selected public GitHub repository `moonkongv2/jy_yamyam`: 3 branches inventoried,
  only `main` selected; 372 reachable commits across 4 pages. One commit's 2 file
  patches and README at its pinned SHA verified through anonymous REST GET.
- Disposable PostgreSQL tests use real migrations in fresh schemas. Local
  Phase 2.2 checks: 211 backend tests (25 acquisition and 25 history/policy cases).
  UI checkpoint checks: 79 frontend tests, lint/build pass; backend unchanged.
  Local Chromium checks with synthetic API responses cover Entries, Search initial/
  results, detail, Import, Sources, job, login and new note at desktop/mobile sizes,
  plus 320/768/1024/1280px layouts. Search submission, filter-only queries, reset,
  legacy redirects, new-tab/reload return context, active menu, deletion cancellation,
  history, annotations and draft reset pass.
  Korean-locale Chromium checks also pass for English date/time/file controls,
  calendar selection and viewport bounds, login/logout, logout after reload,
  cross-tab logout and expired-session redirects. No application Korean labels
  remain in the source audit; Korean user-content fixtures remain intentional.
  This UI check does not establish actual DB/storage integration.
- Actual local HTTP/S3/worker checks passed with a 512 MiB synthetic ZIP and a
  494 MiB owner archive in isolated schemas. Original hashes, search counts,
  reimport uniqueness, visible progress, and synthetic worker-kill recovery passed.
  Worker peak RSS was about 119/211 MiB respectively; these are local measurements.
  Test objects/schemas were removed.
- Phase 2.2 real HTTP/SeaweedFS synthetic Markdown/shared-ZIP deletion checks
  passed in an isolated transaction/schema: blocked downloads, removed objects,
  retained sibling text, and rollback cleanup. Actual AWS purge is unverified.
- GitHub Actions checks for migrations, backend/frontend tests, generated API
  types, and frontend lint/build (remote workflow execution pending).

The learning-through-F3 baseline is marked by Git tag
`learning-complete-f3` at `187b651f9422e901059f238c334d0e5fa885b4f4`.
The project remains a learning project; delivery from here follows the
user-verifiable product slices in `ROADMAP.md`.

## Next

1. First scope consistent AI eligibility for the required Codex/GitHub event
   records, preserving exact primary-text mapping, ownership, record/source
   permissions, deletion, historical versions and usage limits across indexing,
   storage, answer dispatch, historical selection and retrospective selection.
   Do not enable every PROJECT_EVENT body or send personal records merely to
   satisfy coverage; a separately reviewed bounded scope and synthetic egress
   checks come first. Then define a small cross-source Phase 3.3 acceptance check across ordinary
   questions, period review and observed history. Record unsupported conclusions, coverage
   gaps, cost and latency; do not resume broad paid tuning. Owner usability review
   of the retrospective remains pending.
   Current retained-version samples do not establish historical
   reconstruction or general real-answer quality. Do not mark Phase 3.3 complete.
   Paid tuning is stopped; no further OpenAI calls or
   reindexing are authorized by these implementation checks. Preserve all closed
   evaluation protocols, failures and uncertain reservations. Broader quality
   claims need a separately agreed fresh scope rather than reuse of these cases.
2. Confirm GitHub repository browsing in Entries → repository → Commits/Documents
   → reader → return, and Search → Browse repository → return. Existing stored
   GitHub Entries need no reimport for this UI. Repository browsing and the earlier
   authentication/verification follow-up are separate commit checkpoints.
3. Verify Phase 2.4A using `GITHUB_BACKFILL.md`: synthetic Sources/search/evidence,
   private partial preview review, explicit personal apply and same-bundle replay.
   Full source preparation and isolated actual verification are complete. Apply the
   reviewed 415-item preview in the owner terminal; confirm Sources/search/results.
4. Verify the owner-bound private Phase 2.3 apply run status in Sources and
   Codex search/evidence, replay, annotations and disposable deletion/policy checks
   in `CODEX_BACKFILL.md`. Its checkpoint has 33 acknowledgments; completed status,
   target account and selected current versions still require confirmation.
5. Broader source/language and retrospective quality remain unmeasured; selected-
   passage cited answers and local recommendations are implemented in Phase 3.3.
6. Verify Phase 2.2 using `HISTORY.md`: synthetic history, annotations, source
   markers, deletion/reimport block, and Sources permissions.
7. Follow the sequence: Codex/GitHub history → evidence-based answers/retrospectives
   → scheduled collectors → private AWS release.

## Known limitations

- Twenty GitHub questions/evidence are approved and the expanded B1 round is
  measured; broader source coverage and original authoring-set review remain pending.
  The CLI reads the configured local DB and report links assume the app uses that DB.
  Historical-only Entry hits are separate from passage retrieval; no AI answer or
  claim-grounding/abstention test is performed. Exact natural-question substring
  search may have low recall. Missing/invalid/timed-out cases stay visible; synthetic
  corpora do not establish real quality. Very large corpus performance is unverified.

- Repository document lists show the latest retained snapshot by known event date,
  then ID; they do not promise the current GitHub file or selected HEAD contents.
  Unknown dates sort last. Paths renamed in Git remain separate. Counts describe
  retained records, including source-deleted records, rather than source coverage.
  Offset pages can shift during concurrent collection/deletion. Only bounded
  current-version metadata is classified; invalid records remain accessible.
- Legacy assistant phases and missing turn positions stay unknown. Same-time v2
  observations can be retained candidates requiring explicit current selection.
  Session counts describe retained turns, not full source coverage. Session-wide
  deletion/settings are not implemented. JSONB grouping was checked on small
  synthetic data; large-corpus performance is unverified. Concurrent offset pages
  can shift. Owner Codex reading screens are confirmed; mobile-device checks remain pending.
- Owner confirmed the initial and large-ZIP Phase 1.2 flows in the browser.
  Phase 1.3, English UI, and Phase 2.1 owner preview checks remain pending.
  Remote CI execution remains pending; frontend automated tests stub API.
- Refreshed UI owner review is pending. Chromium layout/interaction checks use
  synthetic API responses; other browser engines and actual mobile devices remain
  unverified. Theme is light; a dark theme is not implemented.
  OS file-picker dialogs and browser-owned menus can use the device language.
- Exact phrase is literal case-insensitive substring search. Passages uses local
  simple FTS/lexical ranking; no translation, embeddings, fuzzy matching, attachment
  extraction or LLM answers. Cross-language pilot questions still fail. Backfill is
  required for old records; 8 MiB input/512 passage limits and unverifiable Codex
  mapping surface as partial coverage. Very large corpus performance is unverified.
- Offset pages can shift when records change concurrently. Timezone is initially
  fixed to Asia/Seoul; changing it in user settings is not available.
- Recent job history shows the latest 20 jobs; Entry lists/job results paginate.
- Progress updates at batch commits. Preflight validation initially shows zero
  total; upload byte percentages are not shown. Textless active branches appear
  as EMPTY_CONVERSATION errors and can produce a PARTIAL result.
- Earlier imported Entries/jobs have no reconstructed missing artifact/result
  links. Existing duplicate Markdown rows are preserved separately; future
  identical uploads match their initial canonical byte identity. Explicit document
  IDs and verified source modification times track changed Markdown versions.
- GitHub commit/document ingestion is implemented; owner apply remains pending; full selected actual preparation and isolated
  verification are complete. GitHub discussions are implemented with empty-source
  and synthetic checks; live nonempty/public/private/org discussion access and
  personal-account apply remain unverified. The owner confirmed synthetic discussion
  browsing. Collection is a mutable observation
  window; edited reviews without a source clock need manual current selection.
  Discussion-wide deletion and scheduled collection are not implemented. Codex backfill
  and reading are implemented and owner screen verification is complete; final
  apply run/account/current-version diagnostics remain separate follow-up checks.
  Codex backfill supports installed CLI 0.158.0/0.160.0 with bounded snapshots;
  the separate Phase 2.1 probe remains pinned to 0.158.0.
  conflicts, empty legacy responses and unknown/divergent snapshots remain gaps.
  Other installed CLI versions, private repos, organization SSO,
  and expiring-token access are not verified with real samples. Preview truncation
  and incomplete secret redaction require reports to stay private. Full collection
  volume and deployment cost still need verification.
- The ChatGPT Web extension is experimental and currently unreliable on
  affected pages. Do not use it as the product's dependable capture path.
- Attachment storage does not extract PDF or image content for search.
- Browser access tokens are stored in localStorage for development only;
  review production authentication before internet deployment.
- Queue redrive/DLQ, the crash window between DB commit and AWS SQS enqueue,
  production worker supervision, and broader observability remain follow-up.
- Source deletion confirmation is manual until adapters reconcile source state.
  Missing/equal source modification times require explicit version review.
- Original purge needs the worker; already issued download URLs can work up to
  10 minutes or object removal. Attachment final purge waits 11 minutes because
  upload URLs remain valid after completion. Real AWS version deletion/IAM,
  automatic policy/deletion journaling, backups and 30-day expiry are unverified
  deployment work. Old uploads without known Entry links cannot be safely purged
  by attribution. Restore must apply latest deletion ledger and current denies.
- Worker recovery uses RUNNING age (processing limit + 60 seconds) and owner locks;
  hard process termination is not a wall-clock timeout guarantee.

See `DECISIONS.md` and `CAPTURE.md` for enduring architecture and capture
constraints. Historical step-by-step status is available at the learning
baseline tag.

## Local validation incident

An initial integration script loaded DB settings before its test environment and
misdirected cleanup. The two affected local originals were restored byte-for-byte
from retained SeaweedFS data; one historical job start timestamp was restored
from its previous PostgreSQL row version. The script now verifies the disposable
DB/schema and cleans only object keys created by that invocation. Two September
artifact metadata rows have no verified local original; their availability before
this incident is unknown. No Entry bodies were changed by that script.
