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
