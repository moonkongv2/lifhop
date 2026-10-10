# Phase 3.2B1 — Local semantic retrieval experiment

The experiment CLI is implemented. The first real comparison was measured on
2026-10-09; it did not meet the retrieval-benefit checkpoint.
The browser still offers Exact phrase and Passages. B2 adds persistent vectors and
Semantic/Hybrid browser modes only after the B1 checkpoint is reviewed.

## What is implemented

- Body-only current passages, live source AND record AI permission, explicit query consent.
- A durable shared USD ledger with run/month limits, uncertain exposure and reconciliation.
- Same-corpus lexical, cosine and RRF comparison with exact version/offset gold coverage.
- Body-free immutable manifests/reports. Experimental float32 vectors are memory-only.
- Defaults: provider off, USD 0.25/run, USD 1/month, 300 seconds, 256MiB,
  5,000 passages, 16 inputs and 16,000 UTF-8 bytes/request. No automatic retries.

No embedding worker is required for B1. The CLI needs PostgreSQL; existing browser
inspection uses the ordinary backend/frontend. The development migration is already
applied. On a different checkout/database, run `.venv/bin/alembic upgrade head` first.

## Dry-run without sending data

```bash
.venv/bin/python scripts/check_semantic_retrieval.py --dry-run --email b@test.com --set .local/evaluation/pilot-c9b91fbf392d477989eaeb6ce4a5b44e
```

Enter the local account password in the terminal. The pilot identifies the repository
scope automatically. `--scope`, `--provider` and `--entries 1,2,3` can restrict another
approved dataset. The manifest pins actual IDs, policy/content state and configuration.
No source/query body is printed, and no API key is needed for dry-run.

Initial preparation found 43 documents and 267 body passages, all denied. On
2026-10-09 the owner approved their transmission plus the three pilot questions;
the repository source policy and those 43 record AI permissions are now enabled.
Other record permissions were not changed. The grant persists after the experiment.
`proposed_max_micro_usd: 7779` estimates USD 0.007779 if all candidate documents and
three questions are sent, with conservative per-input rounding. This is not approval.
The original 20-question set is still draft; this pilot has three approved questions.

## First real result — 2026-10-09

Private report: `.local/evaluation/pilot-c9b91fbf392d477989eaeb6ce4a5b44e/semantic-runs/b438d06014304c9ea8c5ddb6dc2b5741.json`.
The owner-authorized development runner used an exact 43-Entry allowlist and the
existing owner/database checks, live passage gates and durable accounting. No
account password or API key was printed. The public CLI still requires local login.

| Case | Language | Lexical gold rank | Semantic gold rank | Hybrid gold rank |
| --- | --- | --- | --- | --- |
| pilot-01 | Korean | Missing in top 20 | Missing in top 20 | Missing in top 20 |
| pilot-02 | Korean | Missing in top 20 | Missing in top 20 | Missing in top 20 |
| pilot-03 | English | 1 | 19 | 4 |

All 28 requests succeeded: 25 document batches and three query calls, 81,572
tokens, 16.13 seconds total. The app ledger records USD 0.001643 with per-call
rounding; provider billing may differ slightly. No uncertain attempts remain for
this run. There were 171 non-gold groups, but no Korean recovery, so
`b2_gate: criteria_not_met`. These are three questions about one README and do
not establish broad model quality. Browser semantic search is not enabled.

Metadata-only inspection found each gold span fits in a single indexed chunk;
the failed cases did not return that chunk or its verified group aliases. Semantic
hits included other chunks from the same gold Entry. Next inspect chunk selection,
duplicate grouping and ranking limits; do not weaken gold coverage or silently
repeat paid calls. Vectors were not retained, so complete pre-quota vector ranks
cannot be recovered from the persisted report.

## Ranking diagnosis — 2026-10-09

The comparison now reports `diagnostics.lexical` and `diagnostics.semantic` for
each case. Stages are `raw`, `grouped`, `entry_quota`, `candidates`, and `top20`.
Each stage contains result counts and complete gold-span coverage ranks only.
Gold is inspected after candidate selection and never changes ordering. No body,
question, answer or vector is added to the report. Existing method scores retain
their original top-20 semantics; larger diagnostic ranks are not passing scores.

The same approved 43 documents, 267 passages and three questions were sent once
more using the same manifest/model under the existing USD 0.25 allowance. Report:
`.local/evaluation/pilot-c9b91fbf392d477989eaeb6ce4a5b44e/semantic-runs/e5487232da5b43daaeac88f2794ece14.json`.

| Case | Raw semantic rank | After exact grouping | After Entry quota | Outcome |
| --- | --- | --- | --- | --- |
| pilot-01 | 46 | 25 | 24 | Below top 20 |
| pilot-02 | 61 | 38 | Removed | Quota removes an already low-ranked chunk |
| pilot-03 | 27 | 19 | 19 | Within top 20 |

Both Korean gold chunks were absent from lexical candidates altogether. All
method scores and final passage lists matched the first run. The two gold spans
fit in individual chunks: 138 characters within a 1,230-character chunk, and 145
within a 1,244-character chunk. There is no split-span defect. Dropping the Entry
quota alone would leave the gold at grouped ranks 25 and 38, so it cannot satisfy
the checkpoint. Mixed topics within chunks and near-duplicate snapshot content
are hypotheses to examine in a smaller, section-aware chunking experiment.

The diagnostic repeat completed 28 successful calls/81,572 tokens in 12.17s,
ledger cost USD 0.001643. Both runs together cost USD 0.003286 in the app ledger;
there are no uncertain attempts in either report. This diagnosis does not establish
that different chunking will improve retrieval, and B2 remains gated.

## Smaller-section experiment — 2026-10-09

Use `--chunking sections-600-v1` on a fresh dry-run to compare smaller exact
slices. The default `indexed` keeps the original behavior. Paragraph and Markdown
heading boundaries are preferred; long blocks are split at line boundaries or
600 characters. Splits stay inside existing parent passages, without overlap or
added titles. Only already eligible, AI-allowed parents are split. The experiment
retains the 5,000-input/256MiB/time/cost limits and does not rewrite the live index.

Before dispatch, the existing owner lock protects revalidation of parent
currentness/hash, permissions, subrange bounds and slice hash. No other parent
text is sent. Questions, model/dimensions and gold spans remain unchanged. The
manifest pins the chunking configuration and contains parent metadata plus
body-free `chunks`. Exact child text from verified identical repository/path
identities groups together. PostgreSQL simple FTS scores these same slices for
the lexical comparison. Denied/oversized counts refer to original parent passages;
`allowed_passages` counts the actual smaller embedding inputs.

```bash
.venv/bin/python scripts/check_semantic_retrieval.py --dry-run --email b@test.com --set .local/evaluation/pilot-c9b91fbf392d477989eaeb6ce4a5b44e --chunking sections-600-v1
```

The existing run command takes the new manifest; it restores the pinned chunking
choice from that manifest. A dry-run does not transmit anything. Experimental
result IDs have the form `parent_id:start:end` and are not browser passage IDs.
To inspect a result, open `/passages/<parent_id>` and use the manifest's exact
start/end positions within the pinned version. The browser shows the parent
passage, so it may include surrounding text outside the embedded child slice.

Report: `.local/evaluation/pilot-c9b91fbf392d477989eaeb6ce4a5b44e/semantic-runs/715294e643b14fe99f7baa74fb53f29f.json`.
The same 43 documents/267 parent passages yielded 1,031 small chunks; the frozen
three questions were unchanged. The estimate was USD 0.008121.

| Case | Indexed semantic/hybrid ranks | Small-chunk lexical | Small-chunk semantic | Small-chunk hybrid |
| --- | --- | --- | --- | --- |
| pilot-01, Korean | Missing / missing | Missing | 16 | Missing |
| pilot-02, Korean | Missing / missing | Missing | 11 | 15 |
| pilot-03, English | 19 / 4 | 1 | Missing | Missing |

Missing means complete gold coverage was absent from the top 20. All gold spans
still fit within individual child chunks. English evidence ranked 14 after exact
grouping but was removed by the two-results-per-Entry quota in the semantic lane.
Its lexical rank-1 candidate was not retained in the final hybrid top 20 either.
The smaller representation recovers Korean semantic retrieval, but the frozen
B2 gate fails because hybrid does not preserve the English success. Inspect
candidate quotas/fusion next; do not relax the gate or rewrite approved gold.

The run completed 68 calls (65 document batches/3 queries), 81,584 tokens in
33.86 seconds. All calls settled as spent; ledger cost USD 0.001668. Total across
the three experiments is USD 0.004954. Vectors remain memory-only. Backend checks:
369 passed, including 30 semantic/chunk tests; CLI help and whitespace passed.

## Explicit live experiment

1. Review the scoped document IDs in the manifest. Source AND individual record AI
   permissions must be enabled for the selected documents; no CLI silently changes them.
   The current Codex's development read authorization does not enable transmission.
2. Set `EMBEDDING_MODE=openai` and `OPENAI_API_KEY` locally in ignored `.env` or the shell.
   Never send the key in chat. Use a dedicated application project and keep its stable
   `EMBEDDING_BILLING_SCOPE` across key rotation. The monthly ledger covers app calls,
   not unrelated usage made with the same key elsewhere.
3. Re-run dry-run after permission changes. The earlier denied manifest is stale.
4. Review the new manifest and explicitly run:

```bash
.venv/bin/python scripts/check_semantic_retrieval.py --run --email b@test.com --set .local/evaluation/pilot-c9b91fbf392d477989eaeb6ce4a5b44e --manifest MANIFEST_PATH --max-cost-usd 0.25 --confirm-external-ai
```

`--confirm-external-ai` authorizes transmission of the selected allowed passages and
approved natural questions for that invocation. Expected answers/claims are never sent.
Every batch rechecks current permissions and source slices. Changed manifests require a
fresh dry-run. Off/zero budget/missing key stops paid dispatch. With no allowed corpus,
the report says `no_allowed_corpus` and does not send even the questions.

## Reading results

Open the generated private JSON report. It includes every reviewed case's status and
lexical/semantic/hybrid gold recall@5/10/20, all-groups@20, MRR@20 and passage IDs.
Find sources through the existing authenticated View passage reader. Reports contain
no source text, questions, claims or vectors. Source/policy changes during the run
invalidate its quality comparison while preserving usage charges.

The B2 checkpoint requires at least 20 distinct non-gold distractor groups, real
approved cases, Korean recovery, preserved English baseline success and owner review.
Synthetic fixtures cannot satisfy real quality acceptance. The 3-question pilot does
not establish diverse-source or broad multilingual quality. No answers are generated.

## Usage and interrupted calls

```bash
.venv/bin/python scripts/check_semantic_retrieval.py --usage --email b@test.com
```

Amounts are integer micro-USD (1,000,000 = USD 1). Possible transmitted calls remain
`uncertain` after timeout/process interruption and count against new months until
settled. A rerun uses a new run ID and may pay again because vectors are not retained.

After checking provider billing and confirming dispatch has stopped:

```bash
.venv/bin/python scripts/check_semantic_retrieval.py --settle-max ATTEMPT_ID --email b@test.com --confirm-settlement
```

This conservatively charges the maximum reservation to its original month. Use
`--confirm-no-charge ATTEMPT_ID --confirm-settlement` only when no transmission/charge
is verified. Reconciliation cannot run during an active app provider call. It never
retries a request. Never clear uncertain entries merely because they are old.

The application budget is conservative accounting, not control over all provider
billing or the release's complete hosting/backup/API budget. Check current model
pricing before live runs. Actual provider behavior and B2 remain unverified.
