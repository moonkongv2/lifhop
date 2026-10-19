# lifhop Current Status

Last updated: 2026-10-19

## Roadmap checkpoint (2026-10-18)

Active stage: **Phase 3.3, implementation present but exit acceptance incomplete**.
Phase 1 archive and Phase 2 manual collectors/history/policies are implemented;
selected-source coverage and older owner-confirmation notes still need reconciliation.
Phase 3.1 evaluation tooling and Phase 3.2 indexing/search are implemented, with
real quality checks concentrated on GitHub documents and selected known cases.
Phase 4 scheduled Codex/GitHub collection and Phase 5 private AWS daily use remain
unimplemented. Existing import/embedding workers are not scheduled collectors.

The audit's PROJECT_EVENT coverage gap is addressed in code: a shared source gate
now admits validated Codex user/explicit final-answer text and GitHub commit
messages/discussion primary bodies, alongside existing text record types. Exact
canonical ranges exclude unknown assistant phases, commands/results, patches and
source metadata. Full originals remain retained. Both AI permissions and current
owner/version/deletion checks still apply; arbitrary events/logs remain excluded.
The projection/storage configuration changed: existing accounts require local
Passage backfill and separately approved fresh embedding indexing. Old vectors
are unavailable; old follow approvals cannot enroll new-config jobs. The owner
has rebuilt local projections. A subsequent explicit request enabled exactly
three selected Codex records and their source, preserving all other record and
source settings. The subsequently approved indexing pass is complete: exactly
the existing 43 GitHub documents and three selected Codex records now have
1,060 current eligible vectors. It made 67 embedding calls, settled USD 0.000996
and left no new uncertain usage. Prior runs/jobs/reservations were preserved.
The owner-approved four-question/nine-excerpt pass is now closed: four real
calls returned the expected statuses, costing USD 0.000809 with 2.4–4.0 seconds
per action. Four returned original citations were independently read and checked.
Two evidence refusals and the priority answer were grounded. The period review
distinguished proposals correctly but reported one UTC calendar day instead of
the Seoul day. Retrospective metadata and instructions now explicitly use Seoul
dates; synthetic regressions cover the fix, but no further real-model call was
made. The original paid outputs remain unchanged. No new uncertain reservations;
three earlier unresolved reservations remain untouched.
The separately approved integrated smoke pass is now closed: three real questions,
six calls, fourteen automatically selected excerpt occurrences, USD 0.000997
settled, zero new outstanding usage. All expected statuses matched. Direct review
passed priority recall and missing-proof refusal; the GitHub answer is partial:
its child-audience detail exists in selected context but not its sole returned
citation, and a reference checklist detail was omitted. Both returned citations
resolve to exact original text. Answer mode was temporarily enabled in that
process only and restored off. No additional indexing, permission change or retry.
The common citation instructions now require cited evidence for every factual
claim and omit unsupported optional details; insufficient evidence still requires
an empty citation list. Synthetic checks cover delivery and response handling,
not actual model compliance. No real-provider retest was performed.
On 2026-10-19 the owner clarified that recorded progress plus explicit unknowns
is a valid recall result; a final personal decision need not have been reported
back to AI. Stop treating an absent final rental outcome as a source-authoring
blocker. Planning/advice must still not be presented as actual choice or use.
The owner-authorized jy_yamyam investigation found a genuine same-change chain:
Codex policy/implementation requests match GitHub implementation `62f20ee` and
documentation follow-up `644e980`, both independently checked remotely. The later
approved bounded import/index pass added four records plus selected ChatGPT
parents: now 52 records/1,097 eligible vectors. Its first integrated query hit a
DB search timeout; all seven answers were left unsent and that approval is closed.
The common output contract now includes cited partial answers with
explicit unknowns; real-model compliance remains unverified. Collector
compatibility and exact source/evaluation preparation precede a paid proposal.
The earlier three source-filtered known cases establish bounded integrated
wiring only. Their citation defect remains a failure, not a newly valid partial
answer. Broad automatic recall and corrected real-model behavior remain unverified.
Private results and permission audit remain under `.local/evaluation/phase33/`.
Phase 3.3 is incomplete; do not start scheduled collection yet.
See AI_SOURCE_COVERAGE.md for scope and completion gates.

## Current product slice

**2026-10-19 ordinary claim/evidence contract locally implemented, 4096 candidate:**

The owner explicitly chose ordinary output 4096 as a local implementation candidate
following the initial 512 capacity stop. Ordinary answers now generate bounded
parts/claims/exact supplied-body quotes/unknowns and deterministically assemble
public text and citations. Validate all fields, including background, without
truncation or repair; incomplete parts need one unknown and complete parts need an
answer claim. Only rendered answer/progress claims contribute citations. Background
alone yields insufficient with empty citations. A fixed insufficient notice is
Korean for Hangul questions, otherwise English; other fixed-notice languages remain
unsupported. Quote existence and declared coverage do not prove entailment,
classification correctness or recovery of all requested facts.
Period/historical requests retain their previous schema/instructions and 512 cap,
with explicit parser modes. Ordinary status reports 4096, generated API docs agree,
and the UI preserves assembled line breaks. Reservations and usage checks use each
actual request cap; old stored prices/reservations remain unchanged. The answer
config hash changed; closed approvals cannot authorize new requests.
All five original ordinary inputs remain byte-for-byte unchanged, with full request
sizes **8075–14230 bytes**. Both period/history full requests equal the closed ones.
The offline seven-request reservation sum is **USD 0.019314**, not an approved paid
scope. A finite executor/digest binding and stop rules remain to be prepared before
seeking separate approval. Actual schema acceptance, target-model output capacity,
semantic quality and automatic retrieval acceptance remain unverified. The original
512 capacity report remains historical; reference tokenizer counts were never
promoted to actual Luna counts. No project dependency or DB migration added.
Full backend **818 passed**; four related frontend files **61 passed**; frontend
lint/build and diff whitespace passed. Initial combined-shell test invocation
could not connect to the local test DB; the standalone pytest invocation and final
full suite succeeded in disposable migrated schemas. Synthetic behavior checks
are not real-model quality measurements. **524 original files / 471 usage rows**,
permissions/current versions and **1097 anchors** were verified unchanged; uncertain
**3/USD 0.006801** untouched. New AI calls/charges zero, ANSWER_MODE=off.
Phase 3.3 incomplete; Phase 4 unstarted. Local review and frozen request arithmetic:
`.local/evaluation/phase33/claim-local-4096-20261019-v1/report.html`.
Implementation details and initial gate history: ANSWER_EVIDENCE_CONTRACT_PLAN.md.

**2026-10-19 approved model comparison CLOSED:** The owner approved the exact
14-answer/USD 0.30 fixed-context proposal below. Both models completed all seven
cases once: **Luna 4/7, Sol 4/7**. Decision/implementation linkage, reported adopted
fix/reason, Seoul retrospective and historical cutoff passed for both. Rental
progress, README required content/grounding and insufficient-evidence status
remain failed under the unchanged checklist. Luna omitted coupon and booking
progress; Sol recovered booking/ETC progress but omitted the coupon request.
Luna's README still contains audience/vehicle claims absent from its sole returned
citation. Sol's actual README claims are grounded, but omit the required audience,
vehicle-selection and Flutter details. Both treat a tangential code/document
review as partial operational evidence instead of insufficient with empty cites.
Neither fabricated deployment success. Do not equate these failure types.
The questioned Flutter criterion remains separately flagged, never silently waived.

Actual charges: **USD 0.048748 total** (Luna **0.002326**, Sol **0.046422**).
Median whole-action time: Luna 6.17s / Sol 6.40s, including local handling; seven
samples each cannot establish general latency/quality. Sol cost about 20 times
more with no increase in whole-case passes here. Do not switch the product model
or sample repeatedly to obtain passes. The previous A baseline was 2/7, but both
context metadata and instructions changed; their contributions are not isolated.
This is fixed-context diagnosis, not automatic-retrieval acceptance or reliability.

The verifier-only `ffac7ce` adds frozen model/pricing context in an isolated fresh
process per request. It verifies full input before reservation, reserves/settles
with the actual model's stored prices and restores defaults. Public APIs and the
product's Luna/USD .01 action limit are unchanged. Focused synthetic tests **26
passed**, final backend **775 passed**. Initial attempts found a nonexistent test
path, sandbox DB denial, then a missing fixture import; corrected before any
provider dispatch. Normal result/code inspection and diff whitespace passed.

All 14 actual inputs match the frozen requests, every returned citation matches
its original anchor, and model/price/usage/reservation/settlement rows reconcile.
Closure preserved **317 old files / 457 old usage rows**, permissions/current
versions and **1,097 anchors**. New uncertain: zero; old **3/USD 0.006801** untouched.
No query embeddings, new indexing/import, permission changes or retries.
Original outputs, direct reviews and actual-price ledger:
`.local/evaluation/phase33/model-comparison-execution-822b4e9a378041859fedb9e96f2b1e20/report.html`.
This approval is closed. Persistent ANSWER_MODE=off; Phase 3.3 remains incomplete;
Phase 4 remains unstarted. Next review the shared remaining failures, especially
per-claim evidence linkage and relevant-progress coverage, before another paid
experiment. Any rubric alignment change must be explicit and preserve old grades.

**2026-10-19 source-context and evidence-level correction implemented:** Normal
answers now send exact selected text plus allowlisted title/source/source-kind and
GitHub repository/path. No raw payload, author, patch, command or invented SHA is
included. Recommendation sizing and dispatch share `current_excerpt`; input is
rechecked before sending. Frozen preparation digests/review pages include metadata.
The five-parent/14 KiB limits and existing policy/version/ownership checks remain.
Period and historical excerpt shapes are unchanged. Public API/UI is unchanged.
Instructions now first establish the requested evidence level, recover direct
facts/progress, match facts to citations, then distinguish missing direct evidence
from a partial answer. Reported adoption does not require unrequested code proof.
This is an instruction candidate, not a semantic verifier or proof of model quality.
No extra provider calls, retries or automatic status rewriting were introduced.
Code commits: `24b17f0` (source context) and `5d49bcc` (answer criteria).
Focused checks **160 passed**, final full backend **772 passed**. Initial failures
were a missing helper import (fixed) and an old exact prompt-text assertion
(updated for equivalent constraints). Diff whitespace passed; no frontend/schema,
dependency or migration change. Persistent ANSWER_MODE=off, Phase 3.3 incomplete.

**Historical preparation snapshot (subsequently approved/executed above):** Same seven previous A contexts for
`gpt-6-luna` and `gpt-6-sol`, 14 answers, zero new query embeddings, 54 parent
occurrences. Same instructions/schema/input, reasoning none and output limit 512;
only model differs. Sol supports none, whereas newer 6.1 Sol does not; this scope
isolates the model at the existing inference setting, not the best possible
reasoning configuration. Account model metadata GETs succeeded; inference remains
unverified. Proposed cap **USD 0.30**, conservative reservation **USD 0.218247**
(Luna 0.010397 / Sol 0.207850), not an actual cost forecast. Existing acceptance
criteria remain; the README Flutter criterion concern is reported separately.
Request/metadata/cost/stop-rule review:
`.local/evaluation/phase33/model-comparison-review-4e1ef43063694ca9bd928d7e7e848e09/review.html`.
Digest `5193cf17b77de76a7dfe8f8787335fd8d19d2496aa0a88860dd425722b70c92c`.
Read-only preparation preserved 310 old files, 457 usage rows, permissions/current
versions, 1,097 anchors and old uncertain 3/USD 0.006801. New AI usage: zero.
Execution must bind the frozen inputs and use isolated, verified model-specific
reservation/accounting (the product currently prices only Luna and retains its
USD 0.01 per-action limit). Do not run Sol through unchanged Luna accounting.
The finite executor's per-model accounting checks precede any approved dispatch;
the saved proposal/request bundle itself is not an executable sender.
No automatic retrieval acceptance, repeats or model replacement are authorized.

**2026-10-19 failure replan (planning only):** Inspection confirmed normal answers
send only ID/text, losing the selected commit's source identity; all seven outputs
completed in 118–205 tokens, so truncation is not the observed cause. Structural
validation does not establish semantic grounding/completeness. Next prepare source
identity delivery with shared selection/dispatch byte accounting, clearer requested
evidence levels and claim/citation handling, then a separately approved same-input
comparison (seven cases × two model candidates, no new query embeddings). Model
limitations remain a hypothesis. Preserve old grading; flag question/rubric alignment
concerns separately rather than lowering acceptance. See the new replan section in
PHASE33_COMPLETION_PLAN.md. No implementation or paid call occurred in this review.

**2026-10-19 approved staged verification CLOSED: A 2 passed / 5 failed.**
The owner approved the prepared 25-call/USD 0.05 maximum proposal, including
continuing independent quality cases within a stage. All seven A cases executed
once through normal product handlers: four query embeddings and seven answers,
**11 calls / USD 0.002301 settled**, 27 selected parent occurrences. A failed;
B/C were skipped and this approval is closed. No retries, prompt/model changes,
imports, indexing or permission expansion occurred. The internal schema was
accepted in these seven samples, but does not prove grounding or completeness.

| A case | Direct original-source review |
| --- | --- |
| Decision → implementation | Failed: actual commit selected, but omitted from returned commit identification/citation; partial is internally consistent. |
| Reported adopted fix/reason | Failed: correctly recalled the user's adoption report, then unnecessarily required independent code verification and returned partial. |
| Ordinary-life recall | Failed: grounded assistant recommendation and scoped unknowns, but omitted recorded coupon request/booking ETC progress. |
| README citation regression | Failed: sole citation still does not establish child audience; vehicle-selection flow and Flutter omitted. |
| Period retrospective | Passed: Seoul day corrected, recorded activity and unadopted proposals distinguished. |
| Historical cutoff | Passed: user priority order and collection/observation cutoff correctly distinguished. |
| Missing operational proof | Failed: no useful direct deployment evidence, but returned partial with a tangential citation instead of insufficient/empty citations. |

Every returned original citation matched owner/version/range/hash/text. This
anchor check does not erase the README semantic grounding failure. The rental
case failed for omitted known progress, not for an unrecorded final outcome.
Period/date success is one fixed-context sample, not a consistency guarantee.
Read-only closure confirmed old **227 artifacts / 446 usage rows**, permissions,
current versions and **1,097 anchors** unchanged. New uncertain usage: zero;
old **3/USD 0.006801** untouched. Persistent ANSWER_MODE=off. No app code changed;
application tests were not rerun (last full backend: 768 passed).
Private originals, direct reviews, immutable ledger and report:
`.local/evaluation/phase33/staged-execution-4fcc4aea0c0d4947a0da1a582428d918/report.html`.
Next: review these failures, then make a focused local correction to source
identity/context delivery, recorded-adoption/partial/insufficient distinctions,
known-progress recovery and citation coverage. Inspect existing code first;
source metadata must remain untrusted and respect the same size/access guards.
The evidence supports examining these causes, not claiming a proven fix. Further
paid testing needs a newly frozen scope and separate approval. Phase 3.3 remains
incomplete; Phase 4 remains unstarted.

**Historical preparation checkpoint — subsequently approved/executed above:**
The owner requested an efficiency review allowing paid work in the plan and
authorized preparation only. Recommend A: the same seven cases (11 calls), B:
four fixed wording variants (8 calls, only if all A pass), C: two additional
fixed-context answer samples for citation/ordinary-life/period cases (6 calls,
only if all A/B pass). Maximum **25 calls / proposed USD 0.05**; configured-price
reservation ceiling **USD 0.030492**. Basic seven-only alternative remains
11 calls/USD 0.02. Keep models, source permissions and indexing unchanged.
The proposal explicitly requests replacing global first-quality-failure stop:
within each stage retain quality failures and continue independent fixed cases;
a failed stage blocks all later stages. Captured/settled output-validation failure
can count as an individual quality failure. Scope/access/configuration/budget,
uncertain usage, provider rejection and infrastructure failures still stop globally.
No fixing/retry/best-of selection is included. This changed stop rule needs new
explicit approval; it has not been activated by the preparation request.
Exact questions, 52-record/284-parent/1,097-anchor pool, current configuration,
preview bindings, costs, gates and finite 25-slot dispatch blueprint:
`.local/evaluation/phase33/staged-review-final-cbc090ec9267470483d3b155184ca52d/review.html`.
Proposal digest `526326983ac355e56e6f28df468e6950834e8c8f7d71524c37741f5649eec05b`.
Read-only live state matched the previous snapshot; independent parent/slice
hash, cost, question and gate checks passed. Old files 218/usage rows 446 and
uncertain 3/USD 0.006801 remain. New AI calls/charges/mutations are zero; no app
code changed or application tests reran. Repeats measure small-sample answer
consistency on fixed inputs, not new retrieval or statistical/general quality.
Persistent ANSWER_MODE=off, Phase 3.3 incomplete, Phase 4 unstarted. Next is owner
review/explicit execution approval of the concrete staged proposal and stop rule.

**2026-10-19 local evidence-selection and status-contract correction:** For a
question explicitly requesting a commit (Korean/English), local recommendation
keeps the leading retrieved parent and considers the first validated commit
candidate next. Other candidates retain their relative rank; common explicit
exclusion phrases retain the old order. No source IDs, gold answers, provider
quota or additional retrieval is used. The five-parent/14 KiB limits, complete
text, deduplication and owner/policy/version/filter guards remain. This is a
narrow requested-kind preference, not general composite-question decomposition
or proof that a retrieved commit is relevant.
The internal provider result now declares `unconfirmed_aspects`: supported and
insufficient require none; partial requires 1–5 distinct nonblank bounded items.
The strict schema/parser reject contradictions without rewriting the answer or
retrying. All question parts must be assessed, and partial unknowns must also be
explained in the answer. Public API/UI shape is unchanged. Undeclared unknowns,
prose contradictions and factual grounding still need semantic review; this
validator cannot prove completeness. The answer config hash changed; old paid
approvals are closed and cannot authorize this contract. Embeddings are unchanged.
Saved-candidate local replay now selects the commit plus all four policy/decision/
implementation parents, within 9,821 request bytes. Annotated local copies verify
the new status guard; they are not replacement provider responses. Original files
203/usage rows 446, settings/current versions and uncertain 3/USD 0.006801 remain
unchanged. AI calls/new charges/import/indexing/permission changes: zero.
Private replay/limitations:
`.local/evaluation/phase33/local-selection-status-466d7dc67b444472bdd184c2ffe33720/report.html`.
Final full backend **768 passed**; focused answer/selection/period/history **158
passed** and event/run **34 passed**. Initial failures were old synthetic
responses missing the new required unknown declaration; fixtures were corrected
without relaxing the parser. Diff whitespace passed. No public schema/frontend,
dependency or migration change; no frontend checks reran. Review the local report's
selected evidence, annotated-fixture labels and limitations; no user paid replay
is needed to verify this local change.
Implementation commits: `412f08b` (explicit commit evidence preference) and
`47471d3` (declared-unknown/status validation and compatible synthetic providers).
Actual model compliance and the remaining answer/date gates remain unverified;
Phase 3.3 is incomplete, ANSWER_MODE=off, Phase 4 has not started.

**2026-10-19 new 7-case approval executed; closed after first answer failure:**
The owner approved digest
`26652b31d956a98c4c1e8340ae25f5cf70e0110925880e83af74db9ff53d72c1`
for at most 11 calls/USD 0.02 without import/indexing/permission changes. The
first question completed normal Semantic search, automatic parent recommendation
and an actual answer without the previous timeout. The implementation commit
was found at rank 9 but omitted by the five-parent count limit. The selected
policy/implementation-branch passages support the returned known facts; two
citations match exact owner/version/range/text hashes. However the answer could
not identify the requested commit, explicitly said its identifier was unconfirmed,
and incorrectly returned `supported` instead of `partial` for that context.
This is a context-selection miss plus an answer-status defect, not a retrieval
miss, fabricated commit or complete pass. No expected source/citation was inserted.
Stopped under the agreed first-failure rule: **1 query + 1 answer, USD 0.000301
settled, zero new uncertain usage**. Six later cases remain unsent; period/history
previews matched locally but their answers and Seoul-date compliance are untested.
Original raw stages, grounding review and result:
`.local/evaluation/phase33/approved-reverification-5f2796fb41a54179835795d546755379/report.html`.
The 183 earlier artifacts, 444 prior usage rows, all Entry/source settings/current
versions and 1,097-vector corpus remain unchanged. Old uncertain 3/USD 0.006801
and persistent ANSWER_MODE=off remain. No app code changed or application tests
reran; this was actual provider verification plus read-only preservation checks.
The approval is now closed. Next is local design/verification of evidence
selection for a composite question and the supported/partial boundary before
preparing any new paid scope. Do not force this known commit into selection or
weaken the completion gate. Phase 3.3 remains incomplete; no Phase 4 work.

**2026-10-19 approved execution closed after Semantic timeout:** The owner approved
proposal `e29c7c37e1f067ead1c36882acfff7ed7f07b18d3ab2c469a6f2116b20b0727c`.
Normal collection APIs imported exactly four records; their real IDs and current
version/Passage hashes matched the frozen sources. Only the specified six Entry
AI flags and chatgpt/default source permission changed. Three one-shot indexing
runs published exactly 37 slices; all old 1,060 anchors remain unchanged.
The first question's embedding succeeded, but repeated corpus aggregation for
per-hit snapshot counts exceeded the five-second search deadline (SQLSTATE
57014, HTTP 503 SEMANTIC_DATABASE_UNAVAILABLE). Stopped immediately: **4 index +
1 query + 0 answer calls, USD 0.000133 settled, no new uncertain usage**. All
seven answer cases remain unexecuted; no citation/partial/date acceptance is claimed.
Raw requests/responses and closed result:
`.local/evaluation/phase33/approved-execution-ff2e68acd51b4187a0e2d598eaab60b2/report.html`.
The indexing script's final ledger-query ID cast error was reconciled read-only;
the successful provider operations were not repeated. Combined snapshot counts
with the initial rank query, retaining eligibility, exact grouping, ordering and
five-second limits. A saved-vector local check succeeded in about four seconds
with no provider calls/new usage; this is not a real answer retest. Focused
indexing/Semantic tests **66 passed**, full backend **745 passed**. An initial
test command named a nonexistent file and ran no tests; the corrected commands
above passed. No frontend behavior/schema changed in the timeout fix.
All 138 earlier artifacts and 439 prior usage rows remain unchanged. Unrelated
Entry settings/current versions and source settings match the execution snapshot;
three older uncertain reservations/USD 0.006801 remain. Persistent ANSWER_MODE
is off. Next: review this closed failure and a fresh bounded 7-case proposal
(4 queries/7 answers, at most 11 calls/USD 0.02, no reimport/reindex/permission
change). New paid work needs explicit approval; Phase 3.3 is incomplete and
Phase 4 has not started.
Implementation checkpoints: `160afe9` (bounded Passage indexing) and `55858b4`
(Semantic alias scan fix). The proposal subsequently approved/executed above is
`.local/evaluation/phase33/post-timeout-review-543fc83a81da48e3ae369d69cb2bf436/review.html`,
digest `26652b31d956a98c4c1e8340ae25f5cf70e0110925880e83af74db9ff53d72c1`.
It freezes the same questions and complete reviewed source pool/current anchors;
provider calls at preparation were zero. No new frontend checks were needed for
the backend-only timeout fix; the prior indexing checkpoint's frontend results
remain historical checks, not reruns in this execution.

**2026-10-19 supplemental read and proposal, before the execution above:**
The owner granted exactly four further windows/1,043 characters. Read only those
windows; assembling them with earlier granted text reproduced all five ChatGPT
parent hashes. No final rental outcome or personal choice reason was found.
Created a new immutable review package without changing older drafts/results:
`.local/evaluation/phase33/combined-review-085f899bdd1f4881bc8fd8ade7832f96/review.html`.
Proposed scope: import the four hashed local candidates, enable those four records
and ChatGPT Entries 2190/2549 plus chatgpt/default source permission, and index
exactly ten frozen parents/37 slices without follow changes. Permission remains
Entry-level; actual batch inputs are the frozen parent allowlist. All other record
flags remain unchanged. Seven answer cases plus four query embeddings and at most
four indexing calls total at most 15 calls. Configured-price reservation bound
is USD 0.012921; proposed budget is USD 0.02. Official model price pages matched
configured rates. Exact questions, source texts, anchors, hashes, stages and stop
conditions are in proposal.json; digest
`e29c7c37e1f067ead1c36882acfff7ed7f07b18d3ab2c469a6f2116b20b0727c`.
At preparation this was unapproved/unexecuted. Real new IDs and ordinary product manifests must
be resolved after approved import, then match every frozen text/hash before
dispatch; changed scope needs new approval. Persistent ANSWER_MODE stays off;
the proposal explicitly requests process-only answer enablement. No actual
import/policy/index/model action occurred. Scope/hash/arithmetic/budget/private-file
and 138-artifact/ledger/policy preservation checks passed; no app code changed or
app tests reran in this read/preparation follow-up. Three uncertain reservations
USD 0.006801 remained untouched. The subsequent owner approval/execution is
recorded above; this preparation snapshot is not permission to repeat it.

**2026-10-19 minimum source scope and bounded indexing:** Committed collector
compatibility as `97f611e` and partial-case preparation as `02aab6c`. A local
candidate package now contains exactly two previously matched Codex turns plus
the GitHub implementation commit and its policy document: four records, not
the project/archive. They are not imported. Five exact eligible parent candidates
are selected from these originals; five existing ChatGPT parent candidates cover
adoption/reason and rental progress. Original review windows leave four small
boundary gaps totaling 1,043 characters. The subsequent explicit grant/read above
resolved those gaps without expanding to the complete conversations.
Package/7-question scope draft (not executable approval):
`.local/evaluation/phase33/minimum-source-package-d458bc9f9b704aaaa7888f6063415fac/review.html`.
Added optional one-shot Passage selection to indexing preview/activation and CLI
`--passages` with explicit `--entries`. Current owner/policy/version guards remain;
follow-changes is rejected, unselected parents never enter jobs, and legacy
manifest hashes/CLI/API replay remain compatible. AI flags are still Entry-level;
this selector is not range-level authorization. No schema/dependency change.
Final checks: 745 backend, 198 frontend tests passed; frontend lint/build and diff
checks passed. A sandbox-blocked DB setup rerun passed after approved escalation;
initial CLI manifest-default handling and test field selection were corrected.
The 138 earlier artifacts, permissions/selection/usage and uncertain reservations
3/USD 0.006801 remain unchanged; ANSWER_MODE is off. No actual import/indexing/AI
call or permission change. The subsequent proposal above freezes source scope
and conservative call/cost bounds; live new IDs remain a post-approval binding
step and cannot substitute different text or widen the approved ranges.

**2026-10-19 collector compatibility and partial-case preparation:** The manual
Codex collector now accepts exact CLI 0.163.0 with a distinct parser tag, alongside
0.158.0/0.160.0. Unknown patches/future versions still fail closed; old bundles
remain readable. Generated schemas and actual stored reads on the two previously
reviewed jy_yamyam sessions matched 14 primary items and normalized seven relevant
turns. Two turns are complete; five keep partial omissions (command output,
unsupported items, sensitive-content filtering). Original sources/sibling worktree
are unchanged; no real import was performed. The old acquisition PoC is unchanged.
Private counts/hashes: `.local/evaluation/phase33/codex0163-compatibility-detail-f67afd9b5b8348fe88d93aff2b835188/`.
Phase 3.3 preparation now accepts `partial` only with explicit bounded
`unconfirmed_aspects`; their digest binds the review/approval and they are never
sent as model input. `evidence-drafts-v3-partial` rejects old preparations and
still requires fresh review. Missing/denied evidence remains blocked; transport
completion alone never marks grounding or phase exit. Related 68 and full 731
backend tests passed; diff checks passed. No frontend changed in this follow-up.
The 138 prior artifacts, account permissions/selection/usage and three uncertain
reservations/USD 0.006801 are preserved; ANSWER_MODE remains off and new AI calls
are zero. Next freeze minimal import records and eligible passage ranges before
the combined source/index/answer approval proposal. No paid manifest is approved.

**2026-10-19 cited partial-answer implementation:** Added `partial` alongside
`supported` and `insufficient` to the common structured output/parser, current
and historical API schemas, generated types and all four answer displays.
Partial answers require 1–5 distinct permitted citation IDs. Instructions recover
directly relevant recorded progress, attribute assistant advice and distinguish
unconfirmed outcomes/personal reasons within the selected evidence. Retrospective
partial lines retain the exact category/citation format; preview coverage alone
does not determine answer status. Configuration hashing includes this new
contract, so previous paid protocols are not reusable. No migration, dependency,
budget, owner/policy/version guard, retry behavior or AI setting changed.
Local checks and remaining real-model verification are recorded in
PHASE33_COMPLETION_PLAN.md: 712 backend and 198 frontend tests passed, frontend
lint/build and diff checks passed. Prior 138 files, policies/selection/usage and
three uncertain reservations remained unchanged; answer mode is off.
Actual-model citation/date/partial compliance is
unverified; no model call or indexing was performed. The subsequent preparation
update above supports partial cases; exact source scope remains to be frozen.

**2026-10-19 owner clarification and actual cross-source match:** The owner
authorized inspection of jy_yamyam's conversations/repository and clarified that
useful partial recall does not require a recorded final outcome. ROADMAP and
DECISIONS now preserve this distinction without waiving factual/citation guards.
Metadata discovery found 84 project sessions; inspected two selected sessions
through disposable snapshots, with locally generated 0.163.0 RPC schemas checked.
Matched 14 primary messages/instructions to immutable Git blobs: optional linked
deletion, default off, already-used rewards retained, implementation `62f20ee`,
and explicit SHA reference leading to guides commit `644e980`. Both commits were
verified with read-only GitHub GETs. One unrelated divergent turn was excluded;
all paired turns passed snapshot consistency. Original rollouts and sibling
worktree are unchanged. Historical test counts are source claims, not tests run
by this investigation. No app code, source policy, ledger or answer-mode change;
zero AI calls, three outstanding reservations/USD 0.006801 preserved.
Private source chain, case drafts, hashes and readable review are under
`.local/evaluation/phase33/jy-cross-source-2ce93bfe70574c81aa7212c638af0749/`.
The subsequent collector update above verifies selected 0.163 reads. Next freeze
exact source/index/answer scope plus citation/Seoul-date regressions for one new
paid proposal. Discovery/normalization is not an import.
Phase 3.3 is incomplete; Phase 4 has not started.

**2026-10-18 additional approved travel review:** Reviewed the four separately
approved conversations in 10 exact ranges/17,847 characters, within the
three-ranges-per-record/2,000-character/24,000-total limits. Found an assistant
OTS recommendation, the user's OTS coupon-search request and a booking-stage
ETC-price question. These do not establish completed booking, actual rental use
or the user's stated final selection reason. Other reviewed material is hotel
information, predeparture checklists and restaurant recommendations. The original
ordinary-life question remains unverified; do not substitute advice for use.
Across both grants, 10 records/26 ranges/49,432 characters were reviewed. The
adoption candidate remains a draft; a matching Codex/GitHub pair is still missing.
Verified all 10 new range hashes, unchanged policy/selection/usage fingerprints,
and all 138 earlier artifacts. Three uncertain reservations remain USD 0.006801;
zero provider calls/indexing/policy changes, answer mode off. Private assessment
and HTML: `.local/evaluation/phase33/chatgpt-travel-review-21dba8589cc749858d3c4bb3f1aba950/`.
No app code changed; source/scope/privacy assertions and diff checks passed.
Next obtain targeted existing-use/reason and linked-source location clues; do not
automatically scan more excluded bodies. No paid acceptance scope is ready and
no completion condition or Phase 4 boundary has changed.

**2026-10-18 approved bounded ChatGPT source review:** Explicit owner approval
covered the six proposed records, at most three 2,000-character ranges each.
Reviewed 16 excerpts/31,585 characters, not whole conversations. Verified every
saved range hash against the retained current version. Found one explicit
user-reported adoption candidate with a preceding symptom/diagnosis/solution;
the recorded reason must remain attributed to the assistant explanation, not
invented personal motivation or proof of testing. Prepared a private question,
claim/anchor checklist and forbidden inferences; owner case review is pending.
Actual ordinary-life use/reason and a linked Codex/GitHub pair remain unverified.
Source/record policies, current selections and usage ledger were unchanged;
zero provider calls/indexing, answer mode off. Private evidence/report is under
`.local/evaluation/phase33/chatgpt-source-review-d7451c6e67bb482ab7fc8a927239ef00/`.
No app code changed. Range/scope/state assertions and diff checks passed.
Next resolve remaining evidence scopes; no paid acceptance proposal is ready.
Prepared a separate four-record travel metadata proposal (up to 24,000 related
characters). It was subsequently approved and reviewed as recorded above; the
original unapproved proposal file remains an immutable preparation snapshot.
Existing Entry-level indexing cannot treat this excerpt-only grant as approval
to embed full long conversations. Phase 3.3 stays incomplete.

**2026-10-18 ChatGPT candidate discovery, metadata only:** Following the owner's
request to proceed, searched only job 7's 1,254 owned ChatGPT titles/dates and
version/policy metadata in a repeatable-read, read-only transaction. All record
AI permissions remain off; conversation start dates span February 2023 through
September 2026 and do not establish dates of described events or later messages.
Title matches: life 20, project 44, change/control 32 (overlapping categories).
Prepared six candidate records for a separate bounded source review: at most
three 2,000-character excerpts each, 36,000 characters total. No source body was
read; review permission is pending, not implied by this metadata report. Current
permitted Codex records remain the same three lifhop records; ChatGPT cannot
substitute for the required Codex/GitHub link. Usage/source-policy/record-selection
fingerprints were unchanged, with zero provider calls or permission changes.
Private candidate identities, dates, version hashes and review HTML are under
`.local/evaluation/phase33/chatgpt-title-discovery-55aea244fe504870a1fadf75fc6fd6f6/`.
Next: obtain the exact source-review grant, verify facts/adoption/reasons, then
prepare one consolidated transmission/cost proposal. Phase 3.3 stays incomplete.

**2026-10-18 ChatGPT import recovery:** The owner's `b@test.com` job 7 reached
the normal three-attempt/120-second caps at 807 saved + 18 empty-text failures
out of 1,284. One bounded local continuation used the same preserved ZIP and
cursor 825, with process-only four-attempt/600-second limits. All 1,284 records
were visited: **1,254 saved, 30 EMPTY_CONVERSATION, PARTIAL**, in 599.31 seconds
for the continuation. Empty means no supported user/assistant text on the active
branch, not proof that the source has no other content. No unprocessed remainder.
Previous record selections/AI permissions, source policies and usage ledger were
preserved; no external AI calls. Normal settings remain 120 seconds/three attempts
and ANSWER_MODE=off. Recovery/attempt/owner-lock tests: **4 passed**. Private
metadata-only recovery evidence is in `.local/verification/import-job7-recovery-20261018/`.
The default budget can still be insufficient for large archives; this recovery
does not change general retry behavior or authorize inspection/transmission of
the imported conversations. Do not retry the completed PARTIAL job just to clear
unsupported-text errors: that would replay the entire archive. Phase 3.3 remains
incomplete; no newly imported evidence has been reviewed by the agent.

**2026-10-18 follow-up handoff:** Citation instructions committed as `6a7beda`;
unresolved-report correction committed separately as `9d9eb69`. Reviewed both
changes; focused backend checks **110 passed**, full backend **701 passed**.
Loaded answer mode is off. No new provider request or indexing was performed.
Final read-only comparison preserved all 138 original audit files, usage rows,
source policies and Entry AI/current-version metadata; three outstanding
reservations remain USD 0.006801. Private handoff preservation report is retained.
PHASE33_COMPLETION_PLAN.md now defines required real source pairs, adoption/reason
evidence, positive life facts, private anchor/checklist fields and the preparation
gate for one consolidated model-validation proposal. Actual missing sources are
not yet identified; exact transmission/call/cost approval is not ready. First ask
for record location clues, without reading excluded bodies or changing policies.
Keep every unmet acceptance gate; no narrower exit scope or Phase 4 is adopted.
The previous live citation/date failures and original results remain open.

**2026-10-18 acceptance scope audit and unresolved-report correction:** The local
preflight now reports every case with coverage gaps as unresolved, including
empty/denied corpora and selected context missing a required source. Previously
these could be missing from the summary list. Render that list in the private
HTML; keep candidate readiness separate from factual relevance and acceptance.
Focused preflight/executor tests **29 passed**. Actual read-only discovery stayed
within the existing 46 allowed records/274 parents/1,060 vectors and left Entry,
usage/run/job counts unchanged. Cross-source candidates do not establish a linked
decision and implementation; inspected reason candidates are proposals/priorities
or review checklists; life matches are desired questions rather than actual facts.
No excluded body was read, and no provider call, activation, policy or settings
change occurred. Private discovery/relevance artifacts are retained under
`.local/evaluation/phase33/scope-audit-*/`. Bounded findings do not establish absence
from all original history. Remaining gates now require owner-selected real
evidence or explicit agreement to defer them; no Phase 4 transition or scope
waiver is implied. Citation/period-date corrections remain live-unverified.
Final full backend suite **701 passed**; diff whitespace passed. No frontend
change or browser run. The citation correction is committed separately;
this checkpoint covers the unresolved-report correction and scope audit.

**2026-10-18 citation instructions strengthened locally:** Require the provider's
returned citation set collectively to support every factual claim, include all
needed excerpt IDs, omit unsupported optional details and decline if a complete
answer cannot remain. The shared current/period/history payload receives the
rule. Added a synthetic complementary-facts API test returning two citations from
three selected originals, with no automatic source appending, no paid replay and
one settled attempt; three mode-specific checks verify instruction delivery.
Focused answer/run/period/history tests **81 passed**. This changes instructions
and the answer configuration hash only; the server's structural validator cannot
prove semantic grounding. No actual provider call, prompt-specific golden hint,
model/embedding change, schema/dependency, policy, `.env` change or old-output
rewrite. Original paid protocols remain closed and their partial results remain
failures to resolve; do not infer that instruction changes passed a live retest.
Next settle remaining acceptance scope as one package before seeking any fresh
real-provider approval. Final full backend suite **700 passed**; diff whitespace
check passed. No frontend change or browser verification was needed.
See PHASE33_COMPLETION_PLAN.md and ANSWER_SLICE.md.

**2026-10-18 approved integrated smoke pass closed:** Verified exact frozen
owner/database/revision/configuration and 1,060 vector/274 parent anchors before
dispatch. Existing Semantic → local recommendation → answer handlers processed
the same questions/source filters/action IDs without injecting scoring evidence.
Three query calls plus three answers sent fourteen parent excerpt occurrences,
within six calls/USD 0.033 and five parents per answer. Actual settled cost
USD 0.000997; per-action latency 4.5–5.3 seconds; no new uncertain attempt.
Priority order and missing-proof refusal passed direct grounding review. GitHub
purpose/flow is mostly supported, but its sole citation omits the child-audience
fact supported elsewhere in selected context; reference vehicle-selection detail
was also absent from the answer. Preserve this partial result rather than
claiming full acceptance or rewriting paid output. Two original citation GETs
and the refusal explanation were checked locally with no additional provider
calls/usage rows. Prior reservations, source permissions and versions were
verified unchanged; temporary process settings were restored and answer mode is
off. The approval is consumed. No application code, model, persistent setting,
new indexing or paid retry. Raw stage responses/ledger/grounding review and a
readable results HTML remain private beside the frozen protocol. The next local
work is a narrow citation-coverage correction and acceptance-scope review;
cross-source reasons, positive life memory and period-date retest remain open.
Existing recommendation/Semantic/answer tests rerun: **61 passed**; diff whitespace
passed. No frontend code change or new browser verification in this execution.

**2026-10-18 integrated-flow proposal prepared:** Committed the bounded indexing
worker/results as `e45e74e`. Prepared three known-evidence smoke questions for
Codex priorities, GitHub document purpose/usage and a Codex missing-proof refusal.
Bind exact questions/source filters, owner/database/revision/configuration,
1,060 current vector anchors and 274 eligible parent anchors from the existing
46-record pool. Reference claims and original text are private scoring inputs;
they must not seed paid retrieval or force selection. Proposed caps: three query
embeddings plus three answers, at most six calls/USD 0.033; up to five automatic
parent excerpts per answer, fifteen occurrences total. Exact selected text depends
on actual query results and remains within the frozen pool and 14 KiB request
limit. Answer mode remains off; a future approved run needs a temporary bounded
process override. No real query/answer/indexing call or permission change occurred.
Real-corpus local probes using source vectors exercised ranking/recommendation
and selected reference text; these are structural checks, not question-quality
evidence. Read-only preparation left usage counts unchanged. Existing backend
tests **61 passed**, frontend integrated tests **32 passed**, diff whitespace
passed. No new app code or browser run. Review is private under
`.local/evaluation/phase33/integrated-smoke/`; the proposed pass is unapproved.
Phase 3.3 and the remaining category/period-date checks are still incomplete.
See PHASE33_COMPLETION_PLAN.md for the exact scope and execution sequence.

**2026-10-18 owner-approved current indexing complete:** The one-pass approval
covered 46 existing permitted records, at most 72 calls/USD 0.01. Both frozen
manifests matched the live DB before activation. Completed both exact-selector
runs without follow changes: GitHub 43 records/1,031 slices, Codex three records/
29 slices; 67 actual document-embedding calls, USD 0.000996 settled, zero new
outstanding usage, about 56 seconds. A separate local readback matched every
stored anchor to the approved manifests, checked 1,536-dimensional nonzero
vectors, and verified `/semantic/status` overall/by source reports available.
Readback added no calls or usage rows. Source/record policy, source versions and
all prior attempts/runs/jobs were verified unchanged. No query or answer call,
model/settings change, fresh permission, old-run resumption or paid retry.
The indexing approval is consumed; Phase 3.3 retrieval/grounding acceptance is
still incomplete. Private approval/dispatch/ledger/readback artifacts are retained
beside the reviewed manifests outside Git. Added an optional run selector to
worker claim/recovery/processing so this execution could not consume other work;
empty selectors process nothing and the normal unscoped worker remains available.
Two synthetic scope-isolation regressions pass; full backend **696 passed**,
targeted indexing tests **31 passed**, diff whitespace passed. No frontend change
or browser run. Next prepare the integrated-flow review described in
PHASE33_COMPLETION_PLAN.md without sending new questions implicitly.

**2026-10-18 commits and remaining-readiness audit:** Acceptance tooling committed
as `3639c3c`; Seoul retrospective dates/results committed as `998950d`. A local
read-only audit found 480 current ready projections, 46 AI-permitted records,
zero usable current vectors and 1,031 stale old jobs. Answer mode remains off.
Prepared private indexing previews for only the existing 43 GitHub documents and
three permitted Codex records: 1,060 slice occurrences, at most 72 batched calls,
conservative combined cost USD 0.008423. No provider request, job/run activation,
reservation or policy change; Entry/run/job/attempt counts were unchanged.
The indexing manifests remain unapproved. Next obtain explicit bounded indexing
transmission approval, then prepare a small integrated retrieval/answer check
with separate consent. Resolve or explicitly narrow remaining evidence categories
before Phase 4. See PHASE33_COMPLETION_PLAN.md; no new paid retry or broad tuning.
This follow-up changes docs/private audit artifacts only. Existing indexing-job
and Semantic tests rerun: **51 passed**; diff whitespace passed. No new test or
browser run. The prior implementation's full suite passed 694 tests.

**2026-10-18 approved selected-context pass closed; retrospective date fix:**
Executed exactly four real answer calls within the approved USD 0.04 ceiling.
Current missing-fact and missing-proof questions returned insufficient; period
review and historical priorities returned supported. Status agreement is not full
acceptance: direct grounding review found the period's UTC/Seoul date discrepancy.
Convert retrospective event/collection metadata to explicit +09:00 offsets and
instruct the existing model to use Seoul calendar dates, preserving stored times
and citation anchors. Missing event dates remain unknown. Two regression tests
cover the boundary and missing-date behavior. The run temporarily enabled answer
mode only inside its approved process; `.env` and running server configuration
were unchanged. No new indexing, permission expansion, model change or paid retry.
The consumed protocol cannot be replayed; changed prompt configuration requires
a fresh preflight and separate approval for any future paid pass. No frontend
change or browser verification was needed for this backend slice. Final full
backend suite: **694 passed**; diff whitespace check passed. Real-model behavior
after the date fix remains unverified; no additional user-run paid test is required
to review these results.

**2026-10-18 evidence-based draft revision and guarded execution prepared:**
Retain unsupported cases with explicit deferral reasons and no provider-call
budget. Allow negative questions without treating them as positive category
coverage. Budget only prepared cases and keep unresolved categories visible.
The private revised draft uses four questions/nine excerpts from the three
authorized records; dates/expectations are proposals, not an approved answer key.
The separate one-pass CLI reconstructs live preflight, requires digest approval,
uses existing current/period/history answer APIs and monthly ledger, prevents
replay, stops on HTTP/status failure and preserves uncertain in-flight requests.
The earlier closed pilot is unchanged. Mocked product-API tests exercise all three
routes and settlement; actual model grounding, latency/cost and remaining release
criteria are unverified. No source/record permission change, embedding/model,
schema/dependency change or paid API call in this slice. Full backend 692 passed,
including 20 preflight and 8 execution tests; both CLI help commands and diff
whitespace check passed. No frontend change or browser run in this slice. The
real four-question/nine-excerpt pass awaits separate owner approval; the local
request plan validates four product-API actions and a USD 0.04 maximum.
See AI_SOURCE_COVERAGE.md.

**2026-10-18 owner-authorized permission update and review:** Enabled only the
three requested Codex records and their existing source. Verified target ownership,
current-version identity and the absence of matching active follow-change or
pending indexing work before applying the normal policy-revision/derivative
invalidation boundary. Checked all other record settings and source policies
were unchanged, including collection settings. Read only the expressly authorized
questions/explicit final-answer spans; no commands, tool results or commentary.
Refreshed the private read-only preflight and recorded relevance findings without
approving its provisional expected outcomes. No application code change, paid
provider call or indexing activation. The updated private review remains blocked
by coverage/relevance issues; Phase 3.3 is incomplete. Persistent AI permission
does not replace approval of a newly scoped paid run. No new tests were needed
for this data-only action; transactional assertions and independent readback
verify the requested change. Detailed personal findings remain outside Git.

**2026-10-18 six-case local preflight implemented:** The authenticated read-only
CLI prepares private source excerpts, scoped period/history previews, candidate
limits, coverage gaps and provisional checklists for the six acceptance categories.
Only currently AI-permitted primary text enters candidates; denied/deleted/foreign
sources are excluded. Bind exact owner/database/policy/configuration and source
anchors, escape source HTML and keep artifacts private outside Git. No provider
calls, usage reservations, jobs, indexing activation, permission change or new
embedding occurs. Defaults are editable drafts, not owner-approved gold answers.
The deliberate local keyword selection does not measure product Semantic recall
or authorize a paid run. The owner's actual draft was found and inspected through
metadata only: coverage gaps remain, permissions are unchanged, and no prohibited
body was read. Added projection/source permission inventories and per-case counts
to distinguish AI exclusion from missing local keyword projections. Counts include
only the owner; record/source denials can overlap. Real-case relevance/expected
outcomes, fresh retrieval/indexing and one approved model pass remain outstanding.
Full backend 681 passed, including 17 preflight tests and the authenticated CLI
round trip; CLI help and diff
whitespace checks passed. No frontend/schema change or browser check in this
slice. See AI_SOURCE_COVERAGE.md.

**2026-10-18 primary event evidence implemented:** Seven Codex/GitHub event payload
kinds share eligibility in indexing, vector reads, exact answer egress, period
review and observed history. GitHub ranges require matching repository/object
identity and canonical retained content; event egress verifies primary containment
again under the owner lock. Empty/unavailable discussion bodies never substitute
placeholder evidence; root titles can qualify alone. Codex unknown phases are
work-only and period review prefers explicit final answers over user questions.
Legacy whole-version AI dispatch rejects events. New projection/config makes old
Passages/vectors unavailable to current search until rebuilt; fresh indexing
approval is required, including for previously indexed documents. No schema,
dependency, model or source-content change. Agent checks use isolated synthetic
databases and mocked providers; no actual OpenAI call or private-data inspection.
Full backend suite: 664 passed, including 23 new event-evidence tests; diff
whitespace check passed. No frontend/API schema changes; browser checks were
not repeated for this backend slice.
Local application upgrade and bounded real-model acceptance remain outstanding.

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

The owner-selected ordinary 4096 candidate is locally implemented and tested.
Review the private claim-local-4096 report and unchanged-v1 checklist. Next bind a
finite seven-request verifier and stopping rules to the exact new requests before
seeking separate paid approval. No real-model schema/capacity/quality acceptance
has been established; keep ANSWER_MODE=off and do not reuse closed approvals.

1. Review the closed comparison: both models 4/7, with shared progress-omission and
   insufficient/partial boundary failures. Do not adopt Sol from these results.
   The small claim/source and requested-fact/progress contract is now locally
   implemented; actual recovery and operational evidence classification need
   fixed-context model revalidation.
   A structural claim/source link cannot prove entailment; semantic checks remain.
   Separately review question/checklist alignment (e.g. Flutter) before proposing
   changes; do not regrade closed runs or silently lower completion conditions.
   No more import/indexing/permissions are needed. All paid approvals are closed;
   future experiments require a new frozen scope and separate approval. Automatic
   retrieval acceptance remains pending. ANSWER_MODE=off; no Phase 4 yet.
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
