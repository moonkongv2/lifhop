# Saved-conversation verification and real-model proposal

2026-10-20. Implementation baseline `89fc941`; this checkpoint fixes a browser-observed
Stop display race and adds reproducible synthetic verification. Phase3.3 remains open.

## Completed browser verification

The in-app browser still fails before connecting (`sandboxPolicy` metadata missing).
A separate installed headless Chromium was used instead; this did not control the
in-app browser. It connected only to the loopback Vite frontend and a disposable
`conversation_demo_*` schema in the local `_test` database. No personal DB migration,
personal records, indexing, policy changes or real AI requests were involved.

`python -m scripts.preview_conversations` installs synthetic planner/query/answer
transports and blocks fallback async HTTP/AWS calls in that disposable process.
Fixture indexing publishes synthetic vectors locally. Its two demo accounts and
JWT signing key are independent of the real app. Ctrl+C removes its schema.

The browser exercised:
- First Search & ask question → persisted cited answer.
- Stable original → Back to conversation, with no provider calls on viewing.
- Reuse, clarify without query/answer, clarification reply and search follow-up.
- Close/logout/login/list/open/reopen, with no replay.
- Another account denied access; old account text not displayed.
- Mobile390×844 with no document horizontal overflow; desktop1280×1000.
- Stop while the synthetic answer transport is actually waiting.
- Delete while another synthetic answer transport is waiting; no restoration.

Final counters:6 planner +2 query +6 answer =14 **synthetic** calls,14 spent synthetic
ledger rows, no uncertain rows. There were no browser page exceptions or attempted
external page origins. These counters are not provider billing or semantic quality.
Private screenshots and report: `.local/verification/conversations-browser/`.
`failure.png`/`failure.txt` preserve the earlier failing Stop display, while the
latest `report.json`, `desktop.png`, `mobile.png` describe the passing run.

The race was in the frontend: aborting the answer started a `finally` refresh whose
pre-stop GET could overwrite the committed stopped snapshot. Aborted runs no longer
start that refresh, and Stop cancels older detail queries before installing its
terminal snapshot. The browser test waits for the transport counter in the test
harness, so merely stopping before answer dispatch cannot pass this check.

Checks after the fix: frontend205 tests/lint/build passed; build retains its
~500.76kB single-chunk warning. Backend saved-conversation regression and offline
proposal checks are recorded in CURRENT.md. Actual owner acceptance is separate
from agent-controlled synthetic browser checks.

## Reproduce locally

Use the existing local PostgreSQL `_test` database. No product runtime dependency
was added. The browser checker uses the already installed Playwright tooling under
`.local/verification/browser-tools/node_modules`; supply the matching installed
headless Chromium path with `LIFHOP_CHROMIUM_PATH` on other machines.

```sh
.venv/bin/python -m scripts.preview_conversations --port 8003
LIFHOP_API_PROXY_TARGET=http://127.0.0.1:8003 npm run dev --prefix frontend -- --host 127.0.0.1 --port 5175 --strictPort
node scripts/check_conversations_browser.mjs
```

Run commands in separate terminals from the repository root. Open
http://127.0.0.1:5175/login. Credentials for this synthetic environment only:
`demo@example.test` / `demo-password`; second account `other@example.test` with
the same demo password. It contains no real records and incurs no provider charges.
Start a fresh demo server/schema for each automated browser run (counters and
expected empty list begin at zero). Stop the demo server with Ctrl+C to clean up.
The browser checker requires a localhost origin and aborts external page requests.

## Frozen real-model proposal — approved and executed once

The exact synthetic text/questions/rubric live in
`tests/fixtures/followup_validation.json`. Offline preparation command:

```sh
.venv/bin/python -m scripts.prepare_followup_validation \
  --out .local/verification/followup-validation/proposal-user-current.json
```

It exclusively creates a private JSON proposal, refuses to overwrite it, reads no
DB, and calls no provider. Use a new output filename each time. The closed real-run proposal was:
`.local/verification/followup-validation/proposal-v4.json`.
Digest: `40b21995a9ee1a77d52f7e42cd06639dfd1d4cbc4a9795ff7af2abe955172598`.
Earlier proposal/dry-run revisions remain preserved and are superseded for execution.
The proposal pins the fixture, generation config/prices, relevant product code,
limits and this preparation script. Verify its digest/hash set again before use;
subsequent code, scope or fixture edits require a new proposal and approval.

Proposed execution uses one isolated test account and only the three frozen
synthetic comparison/booking/cancellation documents. It uses real
`text-embedding-3-small` for one batch of three short documents and query embeddings,
and the code's pinned `gpt-6-luna` for planner/answers. It changes no personal source
permissions, indexes, prior results or existing accounting rows. Any separately
approved real call adds body-free attempts to the existing application usage ledger
under a negative, protocol-derived synthetic owner ID; this keeps monthly budget
and concurrency checks shared with normal app use. Synthetic source data remains
in the disposable `_test` database. Dry-run usage stays entirely in the test schema. Synthetic results validate wiring;
this proposed real run would measure model behavior on synthetic ground truth,
not personal-archive recall or broad quality.

| Turn | Purpose | Expected branch | Max calls | Reservation USD |
| --- | --- | --- | ---: | ---: |
| T1 | Alpha/Beta prices and recorded booking progress | local search |2 |0.008745 |
| T2 | First company's booking progress | reuse |2 |0.011776 |
| T3 | That company's later cancellation record | search |3 |0.011817 |
| T4 | Cancellation progress after logout/login restoration | reuse |2 |0.011776 |
| T5 | Explicitly follow up on T1's price comparison | reuse |2 |0.011776 |
| T6 | Explicitly unresolved Alpha/Beta reference | clarify |1 |0.003072 |
| T7 | Clarification reply asks for Alpha cancellation | search |3 |0.011817 |
| T8 | Fresh independent question about Beta confirmation | local search |2 |0.008745 |
| Initial synthetic document embedding | Three contents in one batch | document |1 |0.000013 |
| **Total** | **8 question actions** | **6 planner/4 query/7 answer/1 document** | **18** | **0.079537** |

Amounts use local pinned price constants and conservative bytes-based reservations,
not a current provider quote or an average-cost prediction. Verify model/pricing
compatibility before execution. Actual reservation uses serialized payload size;
actual charges use validated usage. Output/history/wire caps remain1024/4096 tokens
and16/24/64KiB. Retry/resume/fallback count0. No additional experiment is implied.

Judge interpretation, branch, required selected evidence, citation entailment,
recorded request versus completion, fresh-context isolation and missing-proof
refusal separately. Each rubric names required documents; exact quote/schema
acceptance alone does not pass semantic quality. T5's5만원 difference must be
identified as a calculation from recorded prices. T8 must not borrow Alpha's
booking as Beta confirmation. Reopening and fresh consent are also measured.

Freeze inputs/scope before starting. Later planner/answer requests depend on actual
preceding model outputs: do not claim their complete wire bytes are already frozen.
Before each stage, recheck the approved question/history/source domain and bounds,
record the actual payload hash and selected anchors, and reject unexpected branches
before the next paid call. A branch mismatch or invalid prior answer stops this
sequential pilot; do not replace it with expected/synthetic text to keep going.

Provider/transport/usage/contract failures, uncertain billing, permission/version/
code/config changes, timeout or budget exhaustion stop the whole pilot. Preserve
settled/uncertain usage and failed output; never repair previous results or retry.
Report per-action/stage time, request bytes, input/output tokens, actual cost and
semantic findings; with this small sample show individual values and maximum,
not a general performance percentile.

## Executable pilot and checked boundaries

`scripts/run_followup_validation.py` now executes the same conversation API and
paid stage services. Explicit `--dry-run` or `--execute` is mandatory. Real mode
also requires an exact `--approve-digest` and the configured API key; wrong/missing
approval or stale files/config are rejected before any database is opened. It
creates a new synthetic test schema, records actual requests/responses and stable
selected anchors privately, then drops only that schema. Real accounting remains
in the central ledger even on failure. It never edits old accounting rows.

A per-protocol DB lock and persistent protocol-owner usage prevent simultaneous or
later paid replay through a different output directory. Each output directory is
exclusive-create. Existing spent/released/uncertain attempts all block rerunning
the same live protocol. Run-level counters/budget supplement the ordinary monthly
ledger. Unexpected planner branches stop before query/answer dispatch. Transport,
usage, parse, DB errors and uncertain usage close the pilot without retries.

Dry-run blocks fallback async network requests and uses fake responses solely to
exercise the executor. They are not expected answers substituted into a real run.
T4 verifies restoration with a distinct valid access token, even when issuance is
within one second; actual browser login/logout was checked in the earlier browser
checkpoint. Required-evidence omissions and semantic rubric results are recorded
for review; semantic quality is not automatically declared successful.

```sh
.venv/bin/python -m scripts.run_followup_validation --dry-run \
  --proposal .local/verification/followup-validation/proposal-user-current.json \
  --out .local/verification/followup-validation/dry-run-user-1
```

The final agent dry-run is under `dry-run-v4`:8 turns/18 attempted stages completed,
all synthetic usage spent, no external calls, `semantic_verdict=not-reviewed`.
Request/audit counts are conservative stage intents, not proof that a provider
received a request; raw replies and settled usage are separate evidence.
Guard tests cover approval/code/scope mismatch, input/output bounds, replay/call
limits, uncertain usage, total budget, branch mismatch and shared monthly billing.

The owner approved this exact digest/scope/envelope with “진행해줘” and the pilot
was executed once on 2026-10-20. That approval is now closed; this is not permission
for replay or another paid experiment. `ANSWER_MODE=off` remains configured outside
the isolated runtime. No browser access is needed for artifact review.

## Actual result and semantic review

Private artifacts: `.local/verification/followup-validation/real-run-v4/`.
`report.json` records executor completion; its `not-reviewed` field is preserved.
Separate `REVIEW.md` records the subsequent original-source review and metrics;
`audit.json` records independent post-run accounting/cleanup checks. Raw provider
outputs and saved turns were not repaired or overwritten.

All8 branches matched. All18 calls returned validated usage:1 document embedding,
6 planners,4 query embeddings,7 answers. Central accounting added18 spent rows,
USD0.001643 at the pinned local prices, with no new reserved/uncertain usage.
The sum of actual per-stage reservations was USD0.023582, below the approved
USD0.079537 envelope. This is application usage accounting, not invoice verification.
All485 pre-existing ledger rows were unchanged. The disposable schema was removed;
personal sources/policies/indexes were unchanged and configured answer mode is off.

| Turn | Review | Finding |
| --- | --- | --- |
| T1 | Partial | Prices/request progress correct; omitted explicit final-choice/payment/use unknowns from the rubric. Beta-progress absence shares a fact with only a price quote, which does not itself prove that absence. |
| T2 | Pass | First company resolved to Alpha; request distinguished from confirmation/payment/use. |
| T3 | Pass | Searched Alpha cancellation; request distinguished from completed cancellation/refund. |
| T4 | Pass | New access token restored identical prior turns with0 calls; cancellation unknowns retained. This is API token restoration, not a new live browser login test. |
| T5 | Partial | Explicit T1 base respected and5만원 difference correct, but not explicitly labeled a calculation from recorded prices. |
| T6 | Pass | Asked Alpha or Beta; no query/answer call. |
| T7 | Pass | Clarification reply resolved Alpha and retrieved cancellation evidence. |
| T8 | Pass | No prior dialogue in planner/answer context; no Alpha booking attributed to Beta; confirmation unknown bounded to supplied records. |

All required documents were selected and all10 returned citation occurrences
match original ranges/hashes. This establishes citation identity; it does not
erase the T1 clause-level support issue or the T5 derivation-label omission.
Overall semantic acceptance is **partial**, not8/8 passed.

Per-question provider-call time sums were T1=6.25s, T2=6.09s, T3=6.45s,
T4=5.57s, T5=5.07s, T6=2.18s, T7=5.22s, T8=5.25s. Document embedding was3.62s;
the longest single call was5.12s. These exclude DB/HTTP/UI work and do not measure
complete action latency. The18 individual input bounds, usage tokens, cost and
provider durations are in `audit.json`/`REVIEW.md`. No general percentile or long
history performance claim follows from this small fixture.

Review without a browser: open `real-run-v4/REVIEW.md`, compare each saved
`T*-result.json` with the three originals in `tests/fixtures/followup_validation.json`,
and inspect `audit.json` for accounting/cleanup. No setup or extra AI calls needed.
Existing backend853/frontend205 tests and frontend lint/build passed before this
unchanged frozen run; this turn added only documentation/private review artifacts.
The offline correction below now addresses instruction delivery and result
preservation; separately scope a new proposal if real-model retesting is needed.
Broad archive recall, long-context behavior and owner browser acceptance remain open.

## Offline correction after the closed pilot

`answer_claims` v4 strengthens instructions for relevant explicit source limits,
independently supported facts, scoped missing-proof gaps and arithmetic labeled
with its recorded operands/operation. It keeps the JSON schema, output/context
caps and deterministic assembler. No semantic detector, numeric verifier or
keyword-based completeness check was added: quote membership cannot prove
entailment, complete unknowns or arithmetic correctness.

`tests/test_followup_answer_quality.py` uses the same synthetic originals with
constructed provider responses to verify instruction delivery, source preservation,
saved display/status/citations, scoped insufficiency, restoration/replay without
new calls and an explicit-base calculation follow-up. These checks establish
contract plumbing, not actual provider obedience. Historical/period narrative
instructions remain unchanged. No post-correction real-provider call was made.
Checks: full backend861 passed; final quality regression9 passed, including one
explicit-base case added after full-suite collection. `git diff --check` passed.
No frontend code changed in this correction, so frontend checks were not rerun.

The old proposal-v4 and real-run-v4 are preserved as the pre-correction baseline.
They are closed and now stale against the new code/config hashes; do not edit or
reuse their approval. The commands above create a new **unapproved** proposal and
run it offline only. No new paid experiment is prepared or authorized by this change.

Subsequent preparation is now complete: [targeted quality recheck](FOLLOWUP_QUALITY_RECHECK.md)
keeps the3 originals and selects T1/T5/T8, with a new frozen digest and a fixed
7-call/USD0.029279 envelope. After owner approval the live recheck completed at
USD0.000693, no new uncertain usage, semantic2 passes/1 partial. Arithmetic labeling
improved; T1 still omitted final-choice unknown and price-cited booking absence.
That approval is closed. The default full profile and closed prior outputs remain.
