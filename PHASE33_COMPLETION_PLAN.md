# Phase 3.3 remaining acceptance

Status: 2026-10-18. The four-call selected-context pass and the separately approved
46-record indexing pass are closed. Phase 3.3 remains incomplete; this plan does
not authorize another provider request.

## Latest result: approved indexing completed

The owner explicitly approved the 43 GitHub documents and three Codex records,
one pass, at most 72 calls/USD 0.01. Exact frozen manifests matched live policy,
versions, selectors and configuration. Both runs completed with follow-changes
disabled: **46 records / 1,060 eligible vectors**, **67 actual calls**, **USD
0.000996 settled**, **zero new outstanding usage**, about **56 seconds**.

Independent readback matched all stored anchors to the manifests, checked
1,536-dimensional nonzero vectors and verified the local status API overall and
by provider. It made no provider calls or new usage reservations. Prior attempts,
old runs/jobs, source versions and permissions were preserved. Question/answer
calls remain zero in this pass; no answer-mode or model setting changed.

An optional run selector now bounds worker claim, expired-lease recovery and batch
processing to the two approved run IDs; an empty selector processes nothing.
Unscoped processing retains its normal behavior. Two scope-isolation regressions
were added. Full backend **696 passed**, focused indexing tests **31 passed** and
diff whitespace passed. No frontend change or browser check was required.

Next prepare step 2 below. Index availability establishes readiness, not answer
or automatic retrieval quality. The approval is consumed; do not rerun it or send
new questions under the indexing permission. The readiness counts below describe
the pre-execution snapshot and are retained as the audit trail.

## What the completed pass establishes

- Two missing-evidence questions correctly declined to invent facts.
- A historical priority answer matched its original evidence.
- The period review separated activity and proposals, but used one UTC day
  instead of the Seoul day. Payload offsets and instructions are fixed;
  two synthetic regressions pass. Actual model compliance after the fix is
  unverified. Preserve the original response and record the failure.
- Four citation reads matched the selected original ranges. This checks the
  selected context, not automatic retrieval or broad answer quality.

## Read-only account readiness audit

The audit used a repeatable-read, read-only transaction. Source-policy and lexical
counts select metadata only. Indexing previews process currently allowed primary
text locally to calculate exact slice anchors and byte bounds; they store no
source bodies. No API call, indexing activation, permission change or new ledger
reservation occurred. Entry/run/job/attempt row counts were unchanged.

| Observation | Result | Meaning |
| --- | --- | --- |
| Current local projections | 480 ready records | Local passage search is ready |
| Currently AI-permitted records | 46 | 43 GitHub documents and three selected Codex records |
| Usable current embeddings | 0 records / 0 slices | Integrated Semantic retrieval cannot yet be evaluated |
| Older indexing jobs | 1,031 stale | Old jobs are not fresh indexing authorization |
| Answer mode | off | No persistent answer-mode setting was changed |

The prior primary-text projection/configuration change invalidated old vectors.
The recent date correction changes the answer configuration, not the embedding
space; it is not itself a reason to re-embed. Keep the existing embedding model.

Keyword matches are discovery counts, not proof of a decision or its reason.
In particular, the existing rental examples contain a desired question, not an
actual vendor/selection reason. Do not turn this negative test into positive
life-memory acceptance or enable additional records to make the set pass.

## Next sequence

### 1. Restore a bounded current index — completed

Prepare fresh manifests for the existing allowed records only. Fix the Entry
selectors, current versions, scope, policy/configuration and exact slice hashes;
follow-changes is false. The reviewed previews contain:

| Source | Records | Pending slices | Call ceiling | Conservative cost ceiling |
| --- | ---: | ---: | ---: | ---: |
| Codex | 3 | 29 | 3 | USD 0.000310 |
| GitHub documents | 43 | 1,031 | 69 | USD 0.008113 |
| Total | 46 | 1,060 | 72 | USD 0.008423 |

Slice occurrences can repeat identical document text. Valid derivative reuse and
batching can reduce actual sends. The call ceilings conservatively use current
slice byte bounds and the worker's 16-input/16,000-byte packing; slices are not
individual API calls. Approval can use a combined USD 0.01 ceiling while keeping
the two stricter manifest budgets. No question or answer call is included.

Keep exact manifests in the private audit directory outside Git. Recheck them
before activation; drift requires refreshed review. Activate and process only the
approved run IDs; stop on failed/uncertain work rather than retrying automatically.
Do not resume older runs or release earlier uncertain reservations. Report actual
spent/uncertain cost and current eligible vector counts after publication. A
successful indexing pass alone does not establish retrieval quality.

### 2. Freeze one small integrated-flow check

After indexing, prepare exact questions, independent expected claims and source
anchors from permitted primary records. Reuse supported evidence deliberately
only as a smoke check, not as a fresh general-quality benchmark. Do not expose
expected answers to the retriever/model or force source diversity at ranking time.

Inspect query → Semantic hits → parent recommendation → answer → original citation
as distinct stages. Separate query/retrieval misses from context-selection and
answer-grounding failures. Prepare the data/call/cost manifest before obtaining
any new question/answer transmission approval. Each integrated action retains
its existing two-call/USD 0.011 cap. No broad tuning or model change is planned.

### 3. Resolve the remaining acceptance scope explicitly

| Gap | Evidence or decision needed |
| --- | --- |
| Cross-source decision and implementation | A genuine linked Codex decision and GitHub primary implementation record; source presence alone is insufficient |
| Reason and later change | An explicit adopted change with its recorded reason, rather than an assistant proposal |
| Positive ordinary-life recall | A real non-project fact and reason present in permitted records |
| Period calendar correctness | Retain the observed failure; include the Seoul boundary in any separately approved final check |
| Automatic retrieval | Integrated-flow results after current indexing |

First inspect permitted evidence locally for relevant cases. If records are absent
or excluded, report that boundary and present a concrete new source/record scope
for review, or ask the owner to accept an explicitly narrower release gate.
Do not silently waive a category, alter permissions or mark Phase 3.3 complete.
Phase 4 scheduled collection begins only after the remaining exit scope is agreed
and its checks are satisfied.

## Verification and handoff

The implementation committed before this audit passed all **694 backend tests**
and `git diff --check`. This follow-up changes documentation and private local
audit artifacts only; no frontend, schema, model or dependency changed. Read-only
database execution and unchanged row-count assertions verified the audit. The
existing indexing-job/Semantic tests were also rerun: **51 passed**. Diff whitespace
checks passed. No new tests or browser steps are required to inspect these findings.

The owner need not repeat either completed paid pass or the local readback. The
next step is preparing an integrated-flow review; its question/answer transmission
needs separate bounded approval after the exact data is reviewable. Preserve
frozen protocols and raw answers. The pending worker change/results can form a
commit checkpoint: `feat: scope embedding processing to approved runs`.
