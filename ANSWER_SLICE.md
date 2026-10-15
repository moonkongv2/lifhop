# Phase 3.3 selected-passage answers

After a Semantic or local Passages search, select up to five displayed passages.
The screen shows exact text and source/version links before a separate answer
consent. The answer request sends the question and those passages to OpenAI, then
shows a draft with links back to the retained text. It may say evidence is
insufficient. Passages mode searches locally and does not need a stored vector or
a paid question embedding; Semantic mode still needs one paid question embedding.
This is a first answer flow, not a complete date-range retrospective or general
automatic RAG answerer. The owner must check whether each cited passage supports
every claim.

## Boundaries

- `ANSWER_MODE=off` is the default. The existing `.env` OpenAI key and Semantic
  indexing approval do not enable real answer generation. The separate checkbox
  and button are required for each paid answer.
- `POST /answers` accepts a question of at most 256 characters, one to five
  distinct current Semantic slice IDs **or** local passage IDs, a fresh request
  ID and explicit consent. Only the selected exact text is sent. Work-only text,
  title matches, source-deleted records, old versions and AI-excluded records
  fail the current policy check. A local passage can be up to 2,000 characters;
  the combined request is capped at 14 KiB, so a long selection may need fewer
  passages.
- The server holds the owner policy lock through the provider call and rechecks
  citations afterward. A stale or revoked citation suppresses the answer even
  when the provider call has already been charged.
- The pinned model is `gpt-4.1-mini-2025-04-14`; each Responses request uses
  structured output, no API-side storage, at most 512 output tokens, and the
  existing monthly AI budget. Its durable request cap is one call and USD 0.01.
  Uncertain charges and invalid responses are not retried automatically.
- Answer text and question vectors are not stored by lifhop. The response remains
  in browser memory while the search result is present. Citations are validated
  references, not a guarantee that the generated claim is true.

The Responses request and structured output shape follow the
[OpenAI text generation guide](https://developers.openai.com/api/docs/guides/text)
and [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).
The pinned model and published input/output rates are listed in the
[GPT-4.1 mini model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

## Verify without external transmission

```bash
docker compose -f compose.test.yaml up -d --wait test-db
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test .venv/bin/pytest tests/test_answers.py -q
```

Expected: ten backend tests pass, including policy refusal, one-call
replay, revocation before/after dispatch, insufficient evidence and invalid
model citations, plus an answer from a local passage without a Semantic vector.
Frontend checks: `cd frontend`, then `npm test`, `npm run lint`
and `npm run build`.

For browser verification, start `.venv/bin/python scripts/preview_semantic.py --port 8003`
in one terminal. In another terminal, run `cd frontend` and
`LIFHOP_API_PROXY_TARGET=http://127.0.0.1:8003 npm run dev -- --host 127.0.0.1 --port 5175 --strictPort`.
These ports avoid older 8002/5174 previews; stop an older process or choose
another matching API/proxy pair if either port is occupied. Open
`http://127.0.0.1:5175/search` and log in with
`demo@example.test` / `demo-password`. Choose Semantic and ask where the worker
runs. Review index, consent to the synthetic search and submit. Select the worker
passage, then consent to the answer and press Generate cited answer. Expected:
one synthetic draft answer and a citation opening the same exact passage. Switch
to Passages and search for `worker`, then select the worker passage and generate
an answer after the separate consent. This route makes no question-embedding
request; its synthetic answer cites the local passage reader. The
demo uses an isolated test schema and mocked providers; normal shutdown drops
the schema. `http://localhost:5173/search` is the real development account,
where answer generation remains disabled by default.

## Next

### Small real answer check

The local-only preparation tool is `scripts/prepare_answer_validation.py`.
It authenticates locally and creates a private HTML review and a body-free
protocol, using saved Semantic results rather than another paid search. It
rechecks exact current ranges and owner/source/record permissions. No usage
reservation, provider call or permission change is made.

The first protocol selects holdout-03 (Korean supported), holdout-02 (English
supported) and holdout-10 (unknown music composer). Each uses the saved top
three Semantic hits, without selecting against the answer key: three questions,
nine excerpts, one run, no automatic retry, at most three answer calls and
USD 0.03. Model/configuration, dataset revision, question hashes, capture hashes,
slice/version hashes and policy revision are fixed in the protocol. Only questions
and selected excerpts are proposed for transmission; expected answers and
outcomes are not sent. Current conservative estimate is USD 0.006260.

Check each returned factual claim against its citations. Both supported cases
must answer the question without unsupported additions and cite the selected
supporting text; the unknown-composer case must return insufficient evidence
without inventing a person. Record output failures, latency and durable charged
usage. Report a failed case and stop this pilot after one run; do not tune or
repeat it to manufacture a passing result. These three cases do not establish
general answer quality, cross-source quality or historical/period coverage.

The actual private review is under the validation dataset's `answer-preflight/`
directory. To recreate a preview, use:

```bash
.venv/bin/python scripts/prepare_answer_validation.py --email b@test.com --set .local/evaluation/fusion-review-b7a96801f0474c19901d9f5cdc7159b6/validation --capture-dir .local/verification/semantic-product-20261012/cases --cases holdout-03 holdout-02 holdout-10
```

The owner approved this exact protocol on 2026-10-15. The actual run stopped after
two answer calls without retry. It sent two questions and six selected excerpts:

| Case | Outcome | Interpretation |
| --- | --- | --- |
| holdout-03 | HTTP 200, insufficient; 3.862s | Selected top-three snippets discuss marker SFX and general lifecycle, but omit the requested vehicle-position rule. Abstention fits the sent evidence; the supported end-to-end task fails because context is incomplete. |
| holdout-02 | HTTP 503, ANSWER_OUTPUT_INVALID; 2.405s | Valid usage was settled, but output parsing rejected the response. Raw provider output was not saved in this first run; the precise rejected field is unknown. |
| holdout-10 | Not sent | Failure stopped the run; insufficient-evidence behavior for this question was not tested. |

The ledger confirms two spent attempts (291 and 237 micro-USD), total
USD 0.000528, no uncertain attempts and no third attempt. The quality criteria
were not met. An initial ledger-summary field-name error occurred after the
saved results; a separate read-only lookup completed cost reporting without
retransmission. These results show that top-20 retrieval success does not imply
top-three answer context is sufficient. Do not reinterpret the first abstention
as an end-to-end supported-answer success.

`scripts/run_answer_validation.py` now authenticates locally, revalidates the
fixed preview and approval digest, uses the product answer endpoint with a
process-local answer setting, and creates an exclusive durable run marker before
HTTP. Deterministic request IDs and the existing one-call ledger block paid
replay. Failed responses stop the run. Future runs also retain bounded private
provider output before parsing so rejected output can be diagnosed. This capture
was added after the first run and cannot reconstruct its rejected response.
Do not rerun the completed protocol. The CLI was checked with synthetic clients
and help output, not a second real run. Normal `ANSWER_MODE=off` stays in place.

Next: review the context gap and diagnose validators locally, then propose a new
explicit scope if another real check is needed. The used authorization does not
approve another run, more selected text or changed-model comparisons. Automatic
context selection, full historical questions and period retrospectives remain
later work.

### 2026-10-15 local diagnosis after the stopped run

Compared saved hit anchors against the reviewed gold anchors without a database
write or provider request. Both supported cases have complete same-version,
same-field gold coverage at rank **6**, outside the fixed top-three context:

| Case | Gold range (zero-based, end exclusive) | Covering saved hit | Rank |
| --- | --- | --- | --- |
| holdout-03 | Entry 1423 / version 1456, content 726–849 | Slice 34, content 573–1097 | 6 |
| holdout-02 | Entry 1428 / version 1461, content 861–922 | Slice 187, content 585–978 | 6 |

The first-ranked hit in both cases belongs to the right document but does not
contain the answer. Increasing selection from three to five would still omit
the registered evidence. This identifies a context-selection gap in this pilot;
the product currently lets the user select passages and does not automatically
apply this pilot's top-three rule. No ranking, index, gold or model setting was
changed. These inspected cases are now diagnostic examples, not fresh validation
for a context-selection change.

The transmitted JSON schema accepts several values that the application parser
rejects: an insufficient answer with citation IDs, a supported answer without
IDs, unknown/duplicate IDs, and empty or over-1,500-character answers. The prompt
does not explicitly require empty IDs for insufficient answers. Synthetic tests
reproduce each rejection and also cover incomplete responses, refusal content
and malformed JSON. Valid supported and insufficient responses still pass.
All failures share `ANSWER_OUTPUT_INVALID`; the lost real response prevents
choosing one of these explanations for holdout-02. Its valid token usage proves
settlement, not successful output validation or factual quality.

Recommended next implementation: align the prompt/output contract with existing
parser requirements and add body-free rejection diagnostics while keeping strict
citation validation. Keep the private capture already added for approved pilots.
Then verify answer generation using explicitly selected, reviewed supporting
passages; evaluate automatic context selection as a separate task. Do not simply
raise the excerpt count to six based on these two known answers. Changes to the
prompt/schema alter the configuration hash and require a new preview before any
new paid check. This diagnosis made zero provider calls and incurred no API cost.
