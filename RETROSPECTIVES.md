# Bounded period retrospectives

Implemented 2026-10-17. Synthetic HTTP/browser verification passed. Owner usability
review and real-provider classification/summary quality remain unverified.

## Product flow

Search → **Period retrospective** → choose source/type, date basis and range →
**Review period**. The preview is local and shows selection/coverage and exact
originals. After explicit transmission consent, **Summarize this period** makes
one bounded answer request. Each supported item has a source link and one of:
Recorded activity, Proposal, Decision, Completed work, or Unclear.

Source/event date is the default. Added date means collection time; it cannot
establish when an activity happened. Dates use Asia/Seoul, include the final day,
and require an ordered range of at most 92 days. Event-date filtering excludes
unknown event dates. The unknown-date count is across all dates for the selected
source/type, not an assertion that those records belong to the chosen period.

## Local selection and coverage

`GET /retrospectives/preview` applies current ownership, source/type and dates.
It reports all matching records, AI-eligible records, records with a current body
passage, grouped representatives, sampled candidates and selected records.
Eligibility uses both source and record AI permission and the existing allowed
record types; work-only passages, source deletions and stale projections are
excluded. No Semantic vector or paid question embedding is required.

Keep the first eligible body Passage per record. Group identical validated
GitHub document parents before temporal sampling, retaining the latest in-range
representative. Select at most twenty representative positions spread evenly
across chronological rank (including endpoints). Prioritize five spread positions
from those candidates; if a whole parent cannot fit, try remaining candidates.
Choose at most five complete Passages within the actual serialized retrospective
answer payload. Never truncate a parent. Sort the selected set chronologically
for review/dispatch. Dates, source kind and completeness accompany each excerpt.

The UI always says **Partial view**. Unselected records, later body sections,
missing local indexes, repeated snapshots, byte skips, partial projections and
unknown source dates are disclosed. A chronological sample is not a relevance
ranking or proof that the most important events were selected. Complete time
coverage of an upstream service is not established by these local counts.

This first retrospective uses current retained versions attached to records in
the date range. It does not reconstruct what was known at that time, compare
changes between versions, or infer that snapshot content was changed during the
period. Historical-version selection remains a Phase 3.3 follow-up.

## Dispatch and answer contract

The preview digest binds owner, scope, policy revision, counts, selected exact
version/range/hash/date metadata and current answer configuration. `POST
/retrospectives` requires that digest and explicit consent, recomputes the preview
under the shared owner lock and five-second local search budget, and rejects any
change before calling the existing `/answers` implementation. Empty selection
never sends. It uses a fresh action ID and the existing answer-domain one-call
ledger cap; there is no new persistent workflow or provider purpose.

The common caller rechecks source policy/current text/date metadata under the
existing dispatch lock and checks current context before returning citations.
Limits remain one call/USD 0.01, 14 KiB serialized input, up to five 2,000-character
Passages, 512 output tokens, 1,500 answer characters and the shared monthly limit.
Normal `ANSWER_MODE=off` and all keys/permissions remain unchanged. There is no
automatic retry, query embedding, reindexing, new database migration or dependency.

Retrospective mode adds task instructions to the existing Responses envelope.
The model must distinguish proposals from adoption/completion, avoid treating a
commit or prior assistant statement as proof of testing/deployment, and separate
source time from collection time. A supported response has one to five lines:
`[ID] Category: statement`. Every line cites one allowed integer ID, and the
returned citation set must exactly match the line IDs. Insufficient output has
no citations. Invalid format is rejected after known provider usage is settled;
unknown usage remains conservatively reserved. No second call repairs bad output.
The common configuration hash includes these instructions/format, so older
approval manifests cannot silently authorize this configuration. Ordinary answer
payloads retain their existing instructions/output rules.

Format checks do not prove factual support or correct classification. A labeled
Completed work item is still a draft requiring evidence review. The synthetic
provider is deliberately canned and does not measure real model quality.

## Stop, reset and verification

Scope edits (including calendar buttons), account or policy changes invalidate
reviewed consent and old output. The browser aborts on unmount/Stop and rejects
late results even if a fetch resolves after cancellation. Its deadline is 60
seconds. An already sent provider call may finish/be charged; its accounting is
retained. Reload and citation return perform local preview reads only.

Executed checks:

- Full backend: 613 passed; full frontend: 162 passed; frontend lint/build passed.
- FastAPI OpenAPI and generated TypeScript types match; whitespace check passed.
- Synthetic tests cover Seoul date boundaries, missing/invalid/overlong ranges,
  source/event vs added dates, temporal spread, grouping, partial/byte omissions,
  no-vector operation, owner/permission/deletion/work-only isolation, changed
  preview rejection, one-call replay and charged invalid-output rejection.
- UI tests cover local-only preview, consent, per-item source links, insufficient
  output, scope/account/policy changes, stopped late responses, calendar changes
  and citation return without re-execution.
- Real local Chromium verified four selected synthetic records, proposal and
  completion labels, dated originals, one mocked summary call, citation return/
  reload without replay, and an empty January result when switching to Added.
  Private screenshot: `.local/verification/retrospective-flow.png`.
- The in-app browser tool failed because required sandbox metadata was missing;
  standalone local Chromium verification passed. Early UI test selectors matched
  both original/summary text and both calendars; scoped selectors corrected them.

Large-corpus performance and fresh personal-record/model quality remain
unmeasured. Any real-provider check requires a separate fixed data/call/cost scope.
This implementation made zero actual OpenAI calls and preserves old uncertain
reservations. Do not mark all of Phase 3.3 complete from this synthetic check.

## Owner review: exact steps

The synthetic API and frontend were left running; no normal API or worker is
needed. Open `http://127.0.0.1:5174/login`, then use
`demo@example.test` / `demo-password`.

1. Search → **Period retrospective**.
2. Keep **Source/event date**; enter **2026-01-01** to **2026-01-31**; choose
   **Review period**. Expect four eligible/selected synthetic originals and a
   Partial view notice. Preview makes no AI call.
3. Check the transmission consent; choose **Summarize this period**. Expect a
   draft with four items, including a **Proposal** and **Completed work**, with
   original-passage links. These statements come from synthetic fixtures, not
   actual work executed by this preview. The provider is mocked; no OpenAI charge.
4. Expand **Review 4 selected original passages**. Source/event dates are in
   January, while Added dates reflect creation of this disposable preview.
5. Open a citation, return and reload. No summary repeats automatically.
6. Change Date field to **Added**, keep January and choose **Review period**.
   Expect no selected originals: the demo records were collected later. This
   illustrates the difference between activity time and collection time.

The agent performed the mechanical checks. Owner review can focus on whether
coverage/date explanations and item-to-source links are understandable.

If stopped, start the API from the repository root:

```bash
.venv/bin/python scripts/preview_semantic.py --database-url postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test --port 8002
```

Start the frontend from `frontend` in a separate terminal:

```bash
LIFHOP_API_PROXY_TARGET=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Reuse matching running previews instead of binding their ports twice. The demo
now contains four dated records; earlier two-record Semantic examples are an
older fixture description.
