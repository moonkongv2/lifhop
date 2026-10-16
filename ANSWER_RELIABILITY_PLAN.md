# Selected-passage answer reliability plan

Status: local implementation complete; separately approved diagnostic executed
on 2026-10-16 and closed with two passes/one failure. No retry authorized.
Results and next boundary are recorded in `ANSWER_SLICE.md` and `CURRENT.md`.

Follow-up implemented on 2026-10-16: replace the original flat provider schema
with an object root containing a nested supported/insufficient union. Citation
counts are constrained per status; public API output stays flat. This supersedes
the earlier instruction-only schema approach in section 1. Local verification and
a one-case/three-excerpt preview are complete; no new paid call has occurred.

Subsequent owner approval executed that one-case check once. The provider rejected
the request; no answer was returned. The run is closed with one uncertain
USD 0.002267 reservation. Actual schema acceptance remains unverified. Next:
safe provider-rejection diagnostics with synthetic checks; preserve the completed
marker and obtain a separate approval before any future paid attempt.

Safe provider-rejection diagnostics were subsequently implemented and tested
locally: bounded HTTP-error reads, allowlisted metadata, public-code compatibility,
readable local logs, private run-bound sidecars and conservative accounting.
No real retry was made; the old rejection and uncertain reservation remain as
recorded. See the latest section in `ANSWER_SLICE.md` for verification.

## Goal and scope

Complete one observable flow: the owner selects sufficient current passages,
requests an answer, and sees a supported draft with valid source links, or a clear
insufficient-evidence response. If output is rejected, retain enough safe
diagnostics to identify the failing condition without another paid call.

The stopped pilot found registered support at rank six for both supported
questions, outside its fixed top-three context. It also exposed a mismatch
between the transmitted output instructions/schema and stricter server checks.
The precise cause of the real rejected response remains unknown; raw output
was not retained. Preserve this result and its completed run marker.

Keep this slice within manual evidence selection. Automatic ranking/context
assembly, model comparison, new embeddings, historical answers and retrospectives
are separate work. Keep the pinned model, budgets, one-to-five excerpt limit,
14 KiB request limit, policy checks and normal answer-mode default.

## 1. Align the output contract

Files: `app/services/answer_transport.py`, answer diagnostic tests.

- Explicitly instruct: insufficient answers have an empty citation list;
  supported answers have one to five distinct IDs from supplied excerpts only;
  answer text is nonempty and at most 1,500 characters after stripping.
- Keep strict server validation. Never silently drop unknown citations, truncate
  an answer, or convert invalid output into a successful abstention.
- Preserve the existing supported JSON-schema shape initially; do not add
  conditional schema keywords without verifying provider support. Instructions
  express cross-field constraints; the parser remains authoritative.
- Update the configuration hash through its existing derivation. Old protocols
  must fail configuration validation before any provider dispatch. This change
  improves instruction clarity, not a guarantee of semantic correctness.
- Replace tests that freeze the old prompt/schema mismatch with observable valid
  and invalid-output cases. Keep the diagnostic cases as rejection regressions.

## 2. Add bounded, body-free rejection diagnostics

Files: `answer_transport.py`, `answer_call.py`, `scripts/run_answer_validation.py`.

- Introduce an answer-specific error compatible with `EmbeddingError` and keep
  its public string `ANSWER_OUTPUT_INVALID`. Attach only an enumerated reason:
  response shape/status, refusal, JSON shape, answer length, citation type,
  duplicate/unknown citation, or status/citation mismatch. Malformed shapes must
  also yield a controlled error, never a parser exception or raw provider text.
- Emit one structured local log record with reason and existing opaque run ID
  after parsing fails. Log no questions, answers, passages, provider payloads,
  credentials or exception repr. Leave the public API error and frontend contract
  intact. In the pilot CLI, `captured_answer` catches the answer-specific error,
  exclusively writes a private `{run_id, reason}` sidecar and re-raises the original
  error. The result assembler joins it by run ID; it does not scrape application
  logs or expect the private reason in the HTTP response. A failed diagnostic write
  must preserve the original error and existing ledger settlement.
- Preserve valid usage settlement before output validation: rejected output can
  still be charged. Diagnostics must not rewrite spent usage, release a spent
  attempt, or trigger a retry. Unknown usage stays conservatively reserved.
- Keep raw provider capture restricted to the explicitly approved private pilot
  tool; normal product calls do not persist raw responses. Verify that capture
  failure cannot lead to a second dispatch and remains conservatively accounted.

## 3. Prepare a sufficient-context diagnostic check locally

Files: `app/evaluation/answer_preflight.py`, `answer_run.py`, preparation/run CLIs,
their tests. No paid calls in implementation or preparation.

- Add an explicit selection manifest mapping each case to one-to-five saved
  Semantic hit IDs in order. Resolve IDs only against that case's saved capture;
  retain owner/database/current-version/hash/policy checks for every slice.
  Reject duplicates, missing/foreign/stale IDs and oversized requests.
- Use the existing two supported questions with manually selected supporting
  slices and the existing insufficient-evidence question. Label this as a
  diagnostic answer check with known sufficient context, not independent search
  or end-to-end validation. Expected answers never enter the model request.
  For the insufficient case, explicitly freeze its existing saved top-three hit
  IDs in the manifest and review that they do not answer the question. Do not
  substitute new excerpts after approval.
- Freeze selection mode, manifest digest, exact ordered slice IDs/hashes, question
  hashes, configuration, policy revision and per-case maximum cost in a new
  protocol. Reconstruct exactly the same selection during run preflight.
  Old top-three protocols remain immutable and cannot be resumed or overwritten.
- Produce a private HTML preview showing exact questions, excerpt text and source
  links/anchors. Display the supported/insufficient intent, total counts, one-run
  cap, no retry, and conservative cost estimate. Intent/gold are review metadata
  only. No automatic selection based on gold during dispatch.
- Review output locally before requesting new transmission approval. Proposed
  ceiling remains three calls / USD 0.03, but exact excerpts/counts and estimate
  must be supplied with that request. Earlier approval is exhausted.
  Approval must name the new exact protocol digest and the closed prior pilot;
  changing selection/order/config invalidates that approval. This is an operator
  authorization boundary: the CLI cannot authenticate consent expressed in chat.
- Validate equal protocol/review case counts, unique case IDs and exact order
  before creating a run marker. Stop after any non-200 result; a lost connection
  or process crash must not permit an automatic rerun. Mark unsent cases clearly.

## 4. Verification and completion gates

Synthetic tests must cover both Semantic and local Passage answer paths,
supported/insufficient success, every reason category, malformed response shapes,
no raw text in logs/API diagnostics, spent cost after rejected output, revoked
policy and replay prevention. Test private capture write failure, multi-case
stop after failure, changed config/selection and stale/foreign source rejection
with zero dispatch. Confirm preflight reserves no usage and sends nothing.
Verify a rejected output writes only the safe reason/run-ID sidecar; failure to
write it must preserve the original HTTP error, ledger state and one-dispatch cap.

Run focused answer/preflight/runner tests, then the full backend suite. No new
dependency, schema migration or UI feature is planned. Frontend checks are needed
if implementation reveals a necessary frontend change. Check both CLI help
commands, private file permissions and `git diff --check`.

Implementation is complete when these local gates pass and a concrete new
transmission preview is ready. Report setup, exact preview path, reviewed counts,
estimated cap and known limits directly to the owner. Do not count local tests
as proof of real-model answer quality.

Only after a separate approval, run once and inspect factual claims/citations:
both supported cases must answer from selected evidence; the insufficient case
must avoid inventing an answer and return no citations. Preserve HTTP/parse
failures, latency and actual/uncertain costs. A successful run demonstrates this
small selected-context flow only. A failure closes the run and returns to local
diagnosis; do not start model sweeps or repeat until passing. Automatic context
selection needs its own plan and fresh evaluation if these cases guide tuning.

Before approval, the private preview must include a short claim checklist derived
from the already owner-reviewed expected answer (review metadata only). Per-case
pass requires HTTP 200; supported status, coverage of every required claim and a
citation that actually supports each claim, with no unsupported factual additions;
or insufficient status with empty citations and no invented answer for the negative
case. Record pass/fail and the reason for each case; unsent cases remain untested.
Parser success alone cannot satisfy this checklist.

## Delivery checkpoints

1. Commit contract clarification, safe diagnostics and tests after local checks:
   `fix: align cited answer instructions and expose safe diagnostics`.
2. Commit explicit evidence-selection tooling and tests after preview review:
   `feat: prepare answer checks with explicit evidence selection`.
3. Record a separately approved real run in documentation after reporting results.

These are recommended future checkpoints, not permission to dispatch paid calls.
Update `CURRENT.md` as each stage actually completes; preserve the failed pilot
in `ANSWER_SLICE.md`. No roadmap or architectural decision change is needed.

## Plan review

Antigravity compact review completed once on 2026-10-15. Accepted the private
diagnostic-sidecar path and explicit negative-context/per-case quality criteria.
Accepted the need to bind new approval to the exact new protocol and identify the
closed prior run. Declined a dataset-wide block across all future protocol digests:
it would also block separately authorized future work and would not authenticate
consent. Keep per-protocol durable replay guards and the explicit approval boundary.
