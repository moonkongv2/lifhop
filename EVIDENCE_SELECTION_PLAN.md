# Automatic evidence recommendations for cited answers

Status: implemented after the passing local gate, 2026-10-17. The owner authorized
the checkpoint commit after discussing the interim UI; a separate owner browser
check was not reported. No new real-provider transmission was authorized or performed.

The subsequent unified answer flow now runs this recommender internally after
Semantic retrieval; ordinary users do not need to invoke the steps below.
Separate recommendation/review is retained under optional advanced controls.
See `UNIFIED_ANSWER.md` for the current one-action flow and consent boundary.

## Implementation result

- Local `POST /answers/recommendations` accepts one to twenty ordered unique
  Semantic IDs, the question and observed policy revision; existing source/type/
  date filters are query parameters. The shared owner read lock and five-second
  search budget protect the entire read. Any missing/foreign/stale/filtered or
  AI-denied candidate rejects the request before returning source text.
- Choose at most five complete parents in original rank order, deduplicating
  verified document parents. The actual serialized answer request must fit
  14 KiB; duplicate, count and byte-limit omissions are returned visibly.
  There is no recommendation table, ledger reservation or external request.
- In Semantic results, choose **Review original passage recommendations**, then
  **Recommend passages**. Full original text is shown with editable checkboxes.
  Generating an answer still requires separate consent. Choosing an individual
  search match returns to the embedding-ID path and clears the proposal/consent.
  Account/filter/result/policy changes unmount the prior proposal; pending local
  requests are canceled and cannot repopulate another selection. Reload never
  repeats a search, recommendation or answer automatically.
- `scripts/check_answer_evidence.py` reproduces the local comparison from an
  authenticated read-only snapshot and saved candidate captures. Questions/gold
  do not influence ranking; gold is used only to score selected current spans.

### Local gate result and limits

Saved ten-case product retrieval, eight supported cases: complete required-span
coverage increased from 3/8 with the first three exact Semantic slices to 6/8
with parent recommendations. No previously covered evidence group was lost.
Cases 02, 03 and 08 gained complete coverage; 01 and 07 remain incomplete.
Two negative cases remain diagnostic and are excluded from that denominator.
Requests were 7,725–12,047 bytes, within 14,336 bytes. Provider calls: zero.

The private, body-free report is the validation set's
`evidence-selection/implemented-parent-gate.json`. These are previously inspected
cases. This measures context assembly, not generated-answer quality or independent
retrieval quality. Parent expansion can consume more bytes and can lose useful
lower-ranked parents on other inputs; visible omissions and the manual selection
path remain necessary. A synthetic regression test proves that such a coverage
loss fails the diagnostic gate.

Agent browser verification passed using the disposable Semantic demo: recommendation,
selection adjustment/consent reset, Passage-ID answer submission, switching back to
individual matches and reload without replay. The provider was mocked. Owner
review is about the usefulness of this interaction; no new paid evaluation is needed
to accept this functional slice.

Final checks: 581 backend tests, 131 frontend tests, frontend lint/build and diff
whitespace passed. PostgreSQL checks used an isolated migrated test schema; the
initial sandbox DB connection was blocked and passed when run on the host. An
early frontend test needed to wait for availability before clicking; its remaining
TypeScript locator-option error was corrected, and final tests/build passed.

## Observable flow and boundary

Search with the existing Semantic mode, then choose **Recommend passages**.
The application proposes up to five exact current passages locally. The owner
reviews full proposed text, adjusts selection if needed, and uses the existing
separate consent/action to generate a cited answer. Recommendation itself sends
nothing to a provider. No second query embedding, paid reranker or automatic
answer request is introduced.

The stopped top-three pilot omitted supporting text already found at rank six.
This slice improves how available context is assembled; it does not promise to
recover evidence outside the retrieved candidate set. Keep existing Semantic
ranking, embedding model, source filters and manual selection available.

## 1. Check a bounded local proposal before building UI

- Start from the existing, ordered maximum twenty Semantic hit IDs. A local
  authenticated recommendation request carries those IDs, the current question,
  filters and the observed policy revision. The question is used only for local
  payload-size checks. It carries no query vector or source bodies.
- Resolve each candidate's retained parent Passage using the existing
  `PassageEmbedding.passage_id` and current owner/policy checks. Parent content
  is already bounded at 2,000 characters. Expanding to a parent can retain useful
  nearby source context without inventing text or new free-form ranges.
- Compare saved hit ranges with parent ranges and current gold coverage locally.
  The proposal must not assume that title and answer sections share a parent.
  Record cases where support remains outside the proposed context.
- First candidate rule: visit the original rank order, deduplicate identical
  verified document parents, and choose up to five complete eligible parents
  within the actual serialized answer-payload byte limit. Use the existing
  `answer_transport.payload` bound rather than a character-only approximation.
  A candidate that cannot fit is skipped visibly; do not silently cut source text.
- Use inspected cases only as diagnostics. Compare complete supporting-span
  coverage against the frozen top-three-slice baseline across saved supported
  cases. Do not hardcode known Entry IDs, rank six, question phrases or gold.

Gate: implement the bounded rule only if it has a useful, non-regressing local
coverage result and does not inflate omitted/truncated evidence invisibly. If
parent expansion does not help, report that concrete result and revise this
proposal before building another selector or starting paid experiments.

## 2. Implement an owner-scoped local recommendation endpoint

- Add explicit request/response schemas and a bounded POST for recommendation.
  This POST makes no external request and reserves no AI usage. It only derives
  the user's proposed selection from current eligible candidates.
- Use `current_read`, `search_budget`, current semantic eligibility and the
  existing owner lock. Reject foreign/missing/stale candidates, changed policy
  revisions and work-only/deleted sources. Apply the same source/date/type
  filters to every candidate and proposed parent.
- Return ordinary Passage IDs, exact text/source ranges, current policy revision
  and safe omission reasons. All proposed text must be AI-eligible, because it
  is being offered for an external answer even though recommendation is local.
- Do not persist recommendations or add tables. `POST /answers` rechecks policy,
  ownership/current version and exact source text immediately before dispatch
  and after the response, using its existing `passage_ids` path.
- Treat proposal selection as ephemeral and editable; membership in a proposal
  does not assert factual sufficiency or authorize transmission.

## 3. Add the reviewable browser action

- Keep Semantic result browsing unchanged. Add **Recommend passages** after
  results are available; show complete proposed text with source links and any
  omitted-context notice before the answer action.
- Feed proposed Passage IDs into the existing SelectedAnswer local-Passage path.
  The proposal replaces the prior selection only on an explicit action; no mixed
  Passage/embedding-ID request is generated. Preserve the question and filters.
- Reset proposal, answer and consent when the question/results, filters, account,
  source selection or observed policy revision changes. Cancel/ignore stale
  recommendation responses and suppress stale answers using current guards.
- Failed recommendation keeps manual selection usable. No recommendation or
  answer is automatically sent on reload, back navigation or status refresh.

## 4. Tests, handoff and stop criteria

Backend: grouping and rank order, complete parent text, byte-budget skips,
ownership/filter/policy/version guards, no usage reservation/egress, both answer
success and insufficient output, source revocation/deletion and stale links.
Frontend: explicit recommendation/review, selection adjustment, separate consent,
switching evidence kinds, stale response suppression, account/filter changes,
reload and empty/error paths. Keep OpenAPI/generated types aligned.

Run focused and practical full backend/frontend tests, lint/build and a synthetic
browser flow. The agent performs mechanical and evidence checks; owner review
focuses on whether the recommendation/review interaction is useful. Provide the
exact URL/actions/expected behavior directly in the handoff.

Complete this slice after local coverage, isolation and browser gates pass. A
real quality evaluation, if later needed, uses a separately reviewed fixed scope
and fresh cases for claims beyond these diagnostics. Stop on failure rather than
repeat paid tuning. Commit implementation after verification; record actual
limits in CURRENT.md and ANSWER_SLICE.md.

## Embedding decision

Keep `text-embedding-3-small` at 1,536 dimensions during this slice. The official
alternative `text-embedding-3-large` has higher benchmark/multilingual capability
and default 3,072 dimensions (it also supports reduced dimensions). It costs
USD 0.13 per million input tokens versus small's USD 0.02. Higher benchmark
scores do not establish a benefit on lifhop's records.

Changing embeddings requires document and query vectors from the same model;
even equal-dimensional vectors from different models cannot be mixed for cosine
ranking. The current store's model/config eligibility guards and vector(1536)
schema must be considered, not bypassed. Any large-model comparison should use
an isolated approved corpus, fixed dimension/model, old baseline and a separate
transmission/cost preview. Reindex only after measured retrieval benefit justifies
the cost and storage/lifecycle change. No embedding call or reindex is part of
the answer-model migration or this recommendation plan.

Sources: [embedding guide](https://developers.openai.com/api/docs/guides/embeddings),
[large model](https://developers.openai.com/api/docs/models/text-embedding-3-large).
