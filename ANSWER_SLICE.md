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

### Selected-context reliability implementation (2026-10-15)

The instructions now explicitly describe the parser's citation/status/length
contract. Parsing keeps strict rejection and identifies bounded local reasons:
response shape/status, refusal, JSON shape, answer length, citation type,
duplicate/unknown citation and status/citation mismatch. Structured local log
records contain only a reason and opaque run ID; the HTTP response still exposes
only `ANSWER_OUTPUT_INVALID`. Normal product requests persist no output bodies.

The pilot capture wrapper moved into `app/evaluation/answer_run.py` so synthetic
integration tests exercise the same capture/accounting path as the CLI. It saves
a private reason sidecar after a settled parse rejection. A failed sidecar write
does not replace the rejection; a failed raw capture after dispatch leaves usage
conservatively uncertain and cannot initiate another call. Reason sidecars are
joined to reports by verified run ID. Run reports list unsent cases explicitly.

`prepare_answer_validation.py --selection PATH --closed-protocol DIGEST` accepts
a private JSON object mapping each case to ordered saved Semantic hit IDs. Each
list contains one to five unique IDs; exact current source/policy checks still
apply. The protocol freezes the selection, configuration and prior closed digest.
The run CLI reconstructs that exact manifest and requires `--closed-protocol`
as well as `--approve-digest`. Old protocols and completed markers are preserved.
New configuration/selection requires a new concrete approval; CLI arguments alone
cannot authenticate consent expressed in chat.

New private preview, prepared without provider calls or DB writes:

- Protocol: `ddfd55c3054e58123361d80b0b65bba9c22f68439a714cfae2b05995097d11b1`.
- Same validation dataset, under `answer-preflight/<protocol>/review-complete.html`.
- holdout-03: explicitly selected slice 34; holdout-02: slice 187. Both include
  the registered supporting text. holdout-10 keeps its saved top-three slices.
- Three questions/five excerpts, estimate USD 0.005896, one run with at most
  three calls/USD 0.03, no retry. No new paid attempt has occurred.
- Required claims and pass criteria appear in the private HTML for owner review;
  they are not transmitted. Files use mode 0600 and contain no remote resources.

The preview tests answers with known selected context. The inspected questions
are diagnostic cases and cannot validate a tuned automatic selection algorithm.
Owner action: open the HTML locally (no server needed), check both supporting
claims against their displayed excerpts and check that the third question lacks
an answer. Any new paid run needs explicit approval naming this protocol and
acknowledging the closed pilot `e2c9f60c69552f2a548b5876884a9c66f7e1ff0011f64fa74a742444b691b69d`.

Final checks: full backend suite **532 passed**; both CLI help commands and
`git diff --check` passed. HTML structure, protocol digest, private permissions
and absence of a new run marker were verified locally. Initial sandbox DB access
was blocked; tests passed after host access was authorized. An initial new-test
import path failed collection and was fixed by testing the shared evaluation
capture helper. Frontend was unchanged and its checks were not rerun. No real
model-quality claim follows from these synthetic checks. Recommended checkpoints
remain contract/diagnostics first, explicit-selection tooling second.

### 2026-10-16 approved selected-context run: closed, gate failed

The owner explicitly approved the reviewed three questions/five excerpts.
Protocol `ddfd55c3054e58123361d80b0b65bba9c22f68439a714cfae2b05995097d11b1`
was rebuilt against a read-only current DB snapshot and required exact equality
before dispatch. The application endpoint then rechecked current source policy
and text as usual. The previous pilot stayed closed. Three calls sent precisely
the approved five excerpts; no new question embedding or indexing was needed.

| Case | Result | Agent assessment | HTTP time | Actual micro-USD |
| --- | --- | --- | --- | --- |
| holdout-03 | HTTP 200, supported, citation 34 | Pass: vehicle follows live timer progress and does not jump to start; matches the selected plan text and required claim. | 3.420s | 230 |
| holdout-02 | HTTP 200, supported, citation 187 | Pass: playback failures are non-fatal and logged with debugPrint; the answer keeps the plan context. | 1.238s | 240 |
| holdout-10 | HTTP 503, ANSWER_OUTPUT_INVALID | Fail: model correctly abstains about composer, but supplies three citation IDs with insufficient status. Raw capture and safe reason confirm status_citation_mismatch. | 1.113s | 256 |

All three ledger attempts are spent; total **USD 0.000726**, zero uncertain
attempts, zero retries. Valid usage was charged even for the rejected output.
The run marker, approval, raw outputs, bounded diagnostic sidecar, individual
HTTP results, ledger, body-free report and agent assessment are saved privately.
`run/results-review.html` shows returned answers, citation text and the rejected
raw output with a link to approved input. Files remain mode 0600. The agent
directly checked answer support; asking the owner to repeat that check is optional.

The complete gate failed. The negative case had correct semantic abstention but
violated the output contract; this cannot count as a successful API answer.
This time the diagnosis is conclusive for the new negative attempt. It does not
reconstruct the previous pilot's missing rejected response or prove a common
cause. Two supported successes demonstrate the small selected-context path only,
not search quality or general model reliability.

Next: prepare a focused structural output-contract plan so insufficient status
and citations cannot conflict in schema-conforming output, while retaining strict
server validation, valid usage settlement and the no-retry boundary. Avoid further
prompt-only paid repetition. Any new implementation/configuration and real check
needs its own preview and approval. No product implementation or ranking was
changed during this run; the previous 532-test local verification still applies.

### 2026-10-16 structural output fix

The provider schema now requires `{"result": {...}}`, where the nested object is
one of two branches: supported status with 1–5 citation IDs, or insufficient
status with zero citation IDs. No schema-conforming insufficient result can
contain citations. An object root and nested `anyOf` with array bounds follow
the [official Structured Outputs subset](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Refusal, incomplete output, invalid citations, duplicate IDs and answer limits
remain subject to strict server checks; schema enforcement does not establish
factual support. The parser returns the original flat internal/public result.
No new dependency, public schema change, migration or frontend edit is required.

The prompt, schema and configuration hash changed. Previous captures remain
immutable in the earlier flat provider format, and old protocols fail the current
configuration gate before dispatch. Mock responses and `preview_semantic.py` were
updated for the new wrapper; the public API remains compatible for both Semantic
and local Passage evidence. Invalid insufficient/citation combinations remain
rejected after valid usage is spent, without another dispatch.

The agent prepared a new private protocol without sending data:
`8954d9ec5080887d68301b84be1dc5adbe2859680f066f432ccd5e8d7b08492e`.
It selects only holdout-10 and its same three saved excerpts. The previous
`ddfd55c3…` run remains closed and is named as the acknowledged prior protocol.
The private HTML is `answer-preflight/<new-protocol>/review-complete.html` under
the same validation dataset. Estimated maximum USD 0.002267; hard ceiling one
call/USD 0.01, one run, no retry. Expected result remains HTTP 200 with insufficient
status, empty citations and no invented composer. This is a regression check of
a known failure, not independent model-quality validation.

Current source ranges/policy were rechecked in a read-only transaction. The agent
already verified that the excerpts do not name a composer; owner evidence review
is optional. No paid run is created. Any real call requires new explicit approval
for this protocol. Official documentation and local schema/API tests establish the
implementation intent; actual provider acceptance of this schema with the pinned
snapshot has not yet been measured. A rejection must close the run, retain usage
evidence and avoid automatic retries or a model substitution.

Verification: 55 focused answer tests and the final full backend suite of **538
tests passed**. Both CLI help commands, the synthetic preview provider's new
format, old/current configuration mismatch, protocol digest, private HTML/file
permissions, no-dispatch marker and `git diff --check` were checked locally.
No failures remain. Frontend files are unchanged, so frontend checks were not
rerun. Real API acceptance/answer behavior remains pending separate approval.

### 2026-10-16 approved one-call contract check: provider rejection

The owner approved one question/three excerpts, at most one call/USD 0.01, for
protocol `8954d9ec5080887d68301b84be1dc5adbe2859680f066f432ccd5e8d7b08492e`.
Read-only preflight rebuilt the exact same protocol and confirmed no previous
attempt for its deterministic ID. One request used the actual product endpoint
with the private capture wrapper; no retry or additional embedding occurred.

The request returned **lifhop HTTP 503, `ANSWER_PROVIDER_REJECTED`**, after
0.707 seconds. This means the fixed-origin transport received a non-200 upstream
response. It does not identify the upstream HTTP status or the reason, because
the current transport discards that status/error body before the successful-raw
capture hook. No provider answer exists to grade; schema acceptance and the
insufficient/citation contract are still unverified with the actual provider.
Do not infer a schema, model-access or billing root cause from this generic code.

The single ledger attempt is **uncertain**, with USD 0.002267 reserved and USD 0
settled. Token usage and actual billing are unknown. A zero settled amount must
not be reported as a confirmed zero charge, and the reservation must not be
released without authenticated reconciliation. It remains within the approved
USD 0.01 ceiling. The approved run is closed; a retry would need new approval.

Saved privately under this protocol's `run/`: exclusive approval/run marker,
HTTP result, body-free report, ledger, assessment and `results-review.html`.
There is no successful provider-output capture or parse-diagnostic sidecar for
this request because it failed before those stages. The agent verified the
report and ledger locally; owner repetition is optional and requires no server.

Next: retain bounded safe upstream rejection diagnostics (HTTP status and
allowlisted error type/code/parameter, without raw source-bearing messages) and
test those paths with mocked responses. This is needed before another real
request can be diagnosed. Do not initiate paid retries to discover the missing
reason. No product code changed during this execution; the previous 538-test
implementation verification remains the latest. Documentation whitespace and
private report checks pass; frontend was unchanged and not retested.

### Safe upstream-rejection diagnostics (2026-10-16)

`AnswerProviderError` keeps the public `ANSWER_PROVIDER_REJECTED` string and
retains only upstream HTTP status, known error type/code and known request
parameter. Explicit allowlists include `invalid_request_error`,
`invalid_json_schema` and `text.format.schema`, alongside known access/quota/server
codes and request fields. Unknown values become null. Do not interpret a null
value as absence of an upstream error. Arbitrary error messages, headers,
request IDs and unknown strings are never logged or written to rejection files.
The [official error guide](https://developers.openai.com/api/docs/guides/error-codes)
describes HTTP errors; the local allowlists are deliberately narrower than all
possible provider responses and are not a provider-wide enum claim.

Rejected responses are streamed within an 8 KiB/two-second diagnostic bound.
Non-JSON, HTML, malformed/deep JSON, oversized output and read failures fall back
to the known HTTP status. No redirects, automatic retries, raw error persistence
or additional provider request are introduced. Successful output retains its
existing bounds and private pilot capture behavior.

The paid caller logs a readable safe status/type/code/parameter record with the
existing opaque run ID after preserving ledger state. Normal public HTTP output
does not include those internal diagnostics. The pilot wrapper exclusively saves
`<case>-rejection.json`, containing only run ID and sanitized metadata. The report
verifies run ID and allowed fields before joining it. A failed diagnostic write
does not replace the original provider error, change uncertain accounting or
allow a retry. The existing reservation remains conservative even for HTTP 400;
an HTTP rejection alone is not treated as billing reconciliation evidence.

Tests use `httpx.MockTransport` through the real HTTP transport and actual test
DB/answer endpoint. They cover structured schema errors, raw-message/secret
removal, unknown fields, HTML/oversized/malformed bodies, partial read failure,
public API compatibility, readable sanitized logs, private permissions, failed
sidecar persistence, report linkage, uncertain reservations and no paid replay.
No actual OpenAI request, model/schema change, DB migration or policy edit was
made. The lost real rejection cannot be retroactively diagnosed by these tests.

Owner verification: none required for this internal change; the agent checks the
observable HTTP/log/file/ledger behavior with synthetic inputs. A future approved
failure will retain metadata in the run report and private rejection sidecar.
The previous closed run and USD 0.002267 uncertain reservation are preserved.
Further real checks need a new concrete protocol and separate approval.

Verification: the final full backend suite passed **549 tests**. The run CLI help
and `git diff --check` passed. All new transport tests mock HTTP; no source was
sent to OpenAI. Frontend files are unchanged and frontend checks were not rerun.
Recommended commit for this unit:
`fix: retain safe answer provider rejection diagnostics`.

### Commit and new diagnostic preview checkpoint

Core answer-format/transport/diagnostic changes were committed as `b3f76ac`.
The explicit selection and private capture/report tooling, related tests and
documented failed runs are a separate commit unit. No private dataset, source
excerpt, provider capture, key or local artifact is included in either commit.

The new prepared protocol is
`d51d005ac86f7f251df0787a706de8320c3f5cd72fc6300b6ac85d2905fb4e73`.
It uses the same holdout-10 question and three saved excerpts, unchanged schema/
model, and acknowledges the closed `8954d9ec…` run. Estimate USD 0.002267, hard
ceiling one call/USD 0.01, one run, no retry. Only questions and selected excerpts
would enter a request; the reviewed claim/checklist and expected outcome stay
local. The agent already checked these excerpts lack a composer answer.
The private `review-complete.html` is in this protocol's answer-preflight directory
under the same validation dataset. No run marker or new usage attempt exists.

This is a new, separately proposed diagnostic attempt with safe rejection metadata;
it is not a restart of the completed run. Explicit new transmission approval is
required. Expected success is HTTP 200, insufficient status, empty citations and
no invented composer. If rejected, preserve available safe HTTP/type/code/parameter
fields and stop. The preceding uncertain reservation remains pending reconciliation.

Checkpoint verification: 28 focused preflight/capture/replay tests passed; the
unchanged implementation's latest full backend run passed 549 tests. New preview
digest/configuration/scope, private permissions, inert HTML, Git ignore and
absence of a new run marker were verified. `git diff --check` passed. No frontend
change or external provider request occurred while preparing this checkpoint.
