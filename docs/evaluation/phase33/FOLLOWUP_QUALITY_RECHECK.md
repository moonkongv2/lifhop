# Follow-up quality recheck — executed, semantic result partial

2026-10-20. This is a new finite proposal after instruction correction `8ae1eb8`.
The previous18-call run is closed. Its6 rubric passes/2 partial results and raw
outputs remain unchanged; see [prior findings](FOLLOWUP_VALIDATION.md).

## Observable completion criteria

Use exactly the same three synthetic comparison/booking/cancellation originals
and the same T1/T5/T8 questions. Remove the other five actions. The correction
must preserve recorded qualifications, support each claim with relevant body
quotes, label arithmetic as derived, and avoid attributing Alpha actions to Beta.
This is a targeted compliance check, not Phase3.3 acceptance or archive recall.

The original corpus/questions live in `tests/fixtures/followup_validation.json`;
`tests/fixtures/followup_quality_recheck.json` selects three IDs and tightens their
review rubrics. Preparation copies original question/context/base/evidence fields
without editing them. The JSON proposal contains the complete expanded corpus and
turns, current code/config hashes, pinned prices, billing scope and monthly cap.

## Frozen scope and limits

Proposal: `.local/verification/followup-validation/proposal-quality-v1.json`.

Digest: `5849702fbce2ec97bfec1cbc4dfc4cbd2119c0888b3a5ea770db2aee22129d72`.

| Action | Exact question / purpose | Branch | Max calls | Reservation USD |
| --- | --- | --- | ---: | ---: |
| Document | Three existing synthetic contents, one embedding batch | document |1 |0.000013 |
| T1 | 알파, 베타 순서로 두 업체의 견적과 기록된 예약 진행을 알려줘. | local search |2 |0.008745 |
| T5 | 그 답변의 두 업체 가격 차이를 다시 비교해줘. (explicit base T1) | reuse |2 |0.011776 |
| T8 | 베타 업체의 예약 확정 기록이 있나? (fresh context) | local search |2 |0.008745 |
| **Total** | **3 question actions,3 synthetic documents** | **1 document/1 planner/2 query/3 answer** | **7** | **0.029279** |

Pinned generation model `gpt-6-luna`; embeddings `text-embedding-3-small`.
Reservations use the existing local price constants, not a current provider quote
or predicted actual charge. Actual requests reserve their serialized/input bounds
and settle validated usage through the application's central monthly ledger.
History16KiB, planner wire24KiB/output1024, answer wire64KiB/output4096 and five
whole sources up to2000 characters remain. No retries, fallback, resume or extra
paid question is allowed. Later payloads depend on actual earlier outputs and
therefore are recorded and checked at dispatch, not claimed to be byte-frozen now.

Synthetic data stays in a new disposable loopback `_test` schema. In this
owner-approved live run, at most7 new body-free usage rows use the negative protocol
owner and existing billing scope/slot; prior ledger rows and personal records,
source permissions, embeddings and settings remain unchanged. `ANSWER_MODE=off`
outside the temporary runtime. Drop only the newly created synthetic schema.

## Review against originals

| Case | Pass criteria |
| --- | --- |
| T1 | Recover Alpha30만원/Beta35만원 and Alpha booking request. Preserve the originals' explicit final-choice/confirmation/payment/use limits. Split independently supported assertions. A price quote must not be used as proof that Beta has no booking; a requested outcome missing only from these excerpts belongs in a scoped gap. Do not invent unrequested success requirements. |
| T5 | Resolve the explicit T1 base. Correct5만원 difference, label it in Korean as calculated from recorded prices, show35만원−30만원=5만원 or equivalent, and cite all operands. Do not imply the source directly stated the difference. |
| T8 | Send no earlier dialogue. Bound lack of Beta confirmation to the supplied records. Do not move Alpha booking/cancellation to Beta or turn missing records into a claim that Beta was never booked. Price evidence cannot prove confirmation or non-execution. |

Judge interpretation/branch, required selected originals, per-clause entailment,
qualification completeness, calculation labeling, exact citation identity, fresh
context, time and cost separately. Quote membership/schema acceptance alone does
not pass quality. Use raw outputs plus selected excerpts, not saved prose alone.
Compare with old T1/T5/T8, while recording that removed intermediate turns and
new prior model output mean this is not a controlled estimate of prompt-only effect.
No unrelated reuse/clarify/restoration or long-context regression claim follows.

Unexpected branches stop before the next query/answer call. Provider, transport,
usage, schema/output contract, scope/code/config/policy/version, deadline and
budget failures stop all further calls. Reserved/uncertain billing also stops.
Preserve partial results and central usage; never replace them with expected text
or retry. Required-document omissions are recorded as review failures. Semantic
quality is reviewed after the completed bounded sequence, not automatically
detected by this executor. Any failed rubric keeps the overall outcome partial
or failed and creates no permission to rerun.

Report all7 stage intents separately from actual replies/settled usage, selected
anchors, request bounds, input/output tokens, local-price cost and individual
transport times. Do not report general percentiles or full UI latency from this
small test. Keep raw outputs private and write a separate review.

## Reproduction and dry-run evidence

Preparation is offline and refuses an existing output filename:

```sh
.venv/bin/python -m scripts.prepare_followup_validation --profile quality \
  --out .local/verification/followup-validation/proposal-quality-user-1.json
.venv/bin/python -m scripts.run_followup_validation --dry-run \
  --proposal .local/verification/followup-validation/proposal-quality-user-1.json \
  --out .local/verification/followup-validation/dry-run-quality-user-1
```

The agent's frozen dry-run is `dry-run-quality-v1`:7 stage intents completed,
all7 isolated synthetic usage rows spent, explicit T1 base preserved, T8 dialogue
empty. Fake network responses test the execution boundaries; they do not test
the new prompt's semantic quality. Fallback async HTTP is blocked. No central
accounting writes or real AI requests are involved in dry-run mode.
Post-run checks confirmed that the temporary schema was removed, central usage
for the new protocol owner is0 and configured answer mode remains off. Related
tests45/full backend881 passed; frontend checks were not rerun because no frontend
code changed. `git diff --check` passed.

The runner accepts only the two named full/quality profiles with fixed envelopes;
it cannot authorize arbitrary fixture files or larger call/cost caps. Exact
approval/code/config checks apply before DB access, and stage guards apply again
before each reservation. A protocol lock plus durable prior usage blocks paid
replay through another output directory; spent/uncertain rows survive cleanup.

To review without a browser, read the three questions/rubrics above, the frozen
proposal, and `dry-run-quality-v1/report.json`. Source content is entirely
synthetic. The owner approved this digest,7-call/USD0.029279 envelope and new
central usage rows with “승인할게 실행해줘”. The one permitted live run below is
closed; no replay, retry or new paid request is authorized by that approval.

## Actual result and review

Private original artifacts: `.local/verification/followup-validation/real-run-quality-v1/`.
`report.json` records execution completion and keeps its original `not-reviewed`;
`REVIEW.md` records the subsequent source review, and `audit.json` the independent
accounting/cleanup/quote checks. Outputs were not repaired or overwritten.

All7 calls returned replies and validated usage; all3 branches matched. Central
accounting added7 spent rows for USD0.000693 at pinned local prices, no new
reserved/uncertain usage. Actual reservations totaled USD0.009007, within the
approved USD0.029279 maximum. Existing503 rows were field-identical; the temporary
schema was removed and configured answer mode remains off. No personal record,
policy or existing index changed. Invoice reconciliation was not performed.

| Case | Review | Source-based finding |
| --- | --- | --- |
| T1 | Partial | Correct prices/request and now explicit booking confirmation/payment/use limits. Still omitted the source's final-choice limit. Beta booking absence remained an answered fact backed only by a price quote, instead of a scoped gap; displayed status was supported. |
| T5 | Pass | Explicit T1 base preserved; cited both prices and stated “기록된 금액을 계산하면 … (35만원 - 30만원 = 5만원)”. |
| T8 | Pass | Actual dialogue empty; Beta confirmation unknown scoped to supplied records, no Alpha-to-Beta transfer or assertion that Beta never booked. |

Overall semantic result is **partial:2 passes/1 partial**. Old T5 partial improved
on this rubric; old T1 partial remains.5 citation occurrences match exact original
ranges/hashes and10 raw quote occurrences match supplied bodies, but this cannot
resolve T1's clause-level support/classification defect. All required evidence was
selected. Preserve these failures rather than treating structural acceptance as
semantic success.

Provider-call time sums were T1=7.41s, T5=10.03s, T8=4.88s; document embedding5.02s,
single-call maximum7.56s. Per-stage bounds/tokens/cost/time are in `audit.json` and
`REVIEW.md`. These exclude full API/DB/UI work and do not establish general or
long-context performance. Smaller dialogue and new previous output prevent a
controlled prompt-only causal comparison.

This execution changed only private evaluation artifacts and status documentation.
No tests were rerun: frozen code was unchanged; pre-run full backend881 passed.
Post-run original/quote/explicit-base/fresh-context/accounting/cleanup checks and
`git diff --check` passed. User review requires no browser or extra calls: open
`real-run-quality-v1/REVIEW.md`, compare saved answers with the three synthetic
originals, and inspect `audit.json` for usage/cleanup.

The subsequent minimal contract review is recorded in [OUTPUT_CONTRACT_REVIEW.md](../../design/OUTPUT_CONTRACT_REVIEW.md)
section8. V5 adds field-level explanations and contrasting examples while keeping
the output shape and parser. It cannot mechanically detect the known semantic
misclassification. No v5 real test is scheduled; this closed proposal is stale
against the new code/config and cannot be reused. Broad archive recall,
long-context performance and owner browser acceptance remain open.
