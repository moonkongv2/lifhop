# One-action answers with sources

## Saved conversations (2026-10-20)

Ordinary **Search & ask → Get an answer with sources → consent → Ask from my
records** now creates an owner-scoped PostgreSQL conversation and saves its result.
Use **Conversations** to list/open it after closing, logout or a server restart.
Opening/refreshing/reopening makes no model call or reservation. Chats remain until
you delete them; provider `store=false` is independent of this app retention.

In an active conversation, enter a new question and grant fresh transmission
consent. The planner chooses reuse, search or clarification. Clarifications are
saved; answer them in the same input. Select **Follow up on this answer** for an
older answer. **Start an independent context** explicitly clears inherited context
for the new question while retaining history. Source/date filters stay fixed;
start another conversation to change scope. No message editing or branching.

Close/reopen preserves messages. Stop unfinished questions before closing.
Unfinished stages after reconnect are shown with state/lease and billing status;
use **Stop unfinished question** immediately or **Clear expired question** after
expiry. There is no automatic resume/retry. Already sent requests can finish and
be charged, but Stop/deletion wins over late answer storage. Deleting a conversation
removes its text/anchors while preserving body-free accounting.

An updated/excluded source leaves an old local answer visible with a badge but
blocks contextual retransmission. A deleted/missing source suppresses derived text;
source deletion redacts dependent stored assistant/resolved text in the same
transaction. Stable version/range/hash citations survive disposable Passage rebuilds.
Opening an original and **Back to conversation** do not repeat paid work.

The new profile allows history16KiB, planner wire24KiB, answer wire64KiB. Original
passages are whole (five maximum,2000 characters each); optional history is dropped
before priority evidence. Context details show actual history IDs and omissions.
Ordinary output remains `part-results-v3`/4096 tokens; planner output1024. Maximal
payload reservations under the code's pinned prices: first/fresh USD0.008745,
follow-up reuse USD0.011776, search USD0.011817, clarify USD0.003072. Actual costs
use validated usage. These bounds are not a paid experiment authorization.

### Setup and verification

1. With PostgreSQL running and the usual local `.env`, apply `.venv/bin/alembic upgrade head`.
   This adds tables; no personal backfill/indexing or source-policy change is required.
2. Start backend `.venv/bin/uvicorn app.main:app --reload --port 8000` and frontend
   `npm run dev --prefix frontend`. Open `http://localhost:5173/conversations` and
   log in. Keep `ANSWER_MODE=off` for local read-only verification: listing/opening
   is available, sending is disabled. The agent has not applied this migration to
   the personal DB or changed the persisted AI configuration.
3. Run `.venv/bin/pytest tests/test_answer_conversations.py -q` for synthetic
   first question→follow-up→new-token restoration→delete, source revocation/deletion,
   clarification, IDOR, once-only billing, live DB concurrency and capacity checks.
   Tests create/drop an isolated schema in the disposable `_test` database and
   mock only provider I/O. `npm test --prefix frontend` includes saved-chat UI,
   first-search routing, citation return and account-change/cancellation checks.
4. Owner browser acceptance with an authorized AI configuration: ask a question,
   see a saved cited answer, ask a contextual follow-up, close/logout/login and
   reopen it. Confirm opening does not dispatch AI, new questions require consent,
   another account cannot open it, and deletion removes it. Any real-provider
   quality experiment still requires its separately frozen scope/cost approval.

Current checks: full backend853 and frontend205 tests, frontend lint/build passed
before the frozen real pilot. The UI includes the abort/Stop refresh-race fix.
Build retains a~500.76kB single-chunk warning.

The in-app browser remains unavailable, but separate installed headless Chromium
now passed synthetic desktop/mobile verification including provider-in-flight
Stop/delete, logout/login restoration and account isolation. Agent-controlled
synthetic browser verification is complete; owner acceptance remains pending.
The separately approved8-question18-call real-model pilot completed once:
all branches matched, USD0.001643 settled, no new uncertain usage. Source review
was partial: T1 omitted some unknowns and T5 did not label arithmetic as derived.
See [reproduction and actual pilot findings](FOLLOWUP_VALIDATION.md). The pilot's
synthetic schema was removed; existing accounting rows/personal sources and off
settings are untouched. Long-context and broad archive quality remain unverified.

The long-history synthetic case measured1000 turns/29,750 anchors:50-turn page
257 queries/22,442bytes/~0.102s; source redaction~0.059s on this local test DB.
This does not establish production performance; flattened dependencies grow with
history and a changed old dependency can require a new independent context.

Legacy `mode=answer`, manual, period and historical flows retain their earlier
contracts; their ephemeral results and dated checkpoints below describe those
flows. The implementation plan is [CONVERSATIONAL_FOLLOWUP_PLAN.md](CONVERSATIONAL_FOLLOWUP_PLAN.md).
Phase3.3 exit acceptance remains incomplete; no scheduled collection was added.

2026-10-18 source coverage update: validated Codex questions/final answers and
GitHub commit/discussion primary text can now qualify as AI evidence. Commands,
patches and unknown assistant phases remain outside this scope. Existing records
need a local projection rebuild and separately approved fresh embedding indexing;
see AI_SOURCE_COVERAGE.md for the exact boundary and Phase 3.3 acceptance gate.

Implemented 2026-10-17. Agent synthetic browser verification passed; the owner
authorized the checkpoint commit. Separate owner browser confirmation was not
reported. No real-provider evaluation or new transmission was performed.

## Earlier independent-answer checkpoint (legacy behavior)

Search → **Search & ask** → enter the question/filters → **Search**. This first
returns local record excerpts and makes no provider/status request for answering.
Choose **Get an answer with sources** to review local answer availability and the
transmission scope. Check consent and choose **Ask from my records** once.
The browser then runs:

1. One question embedding and existing local Semantic search (at most twenty hits).
2. Local recommendation of up to five complete current parent Passages.
3. One answer request using those original Passages, returning versioned citations.

The ordinary result is the draft answer and source links. Exact transmitted
passages can be expanded below the draft. The normal screen hides internal
Passage/Semantic and manual evidence-selection controls. Existing bookmarked
verification URLs retain their earlier readers and guarded workflows; they are
not choices in the normal search form. No new model, vector index,
queue, database table, migration or application dependency was introduced.

## Consolidated search screen (2026-10-18)

The form offers two purposes: **Search & ask** and **Review a period**. No
algorithm/mode selector is exposed. Current searches use the existing local
Passage keyword API; results can include records denied to external AI. Choosing
to ask invokes the existing separate policy-checked retrieval/answer flow, which
may use different allowed records. The answer action is initially closed and
opening it only checks availability; it does not grant transmission consent.
Local results remain usable when AI is disabled or no approved index is ready.
No selected-passage checkboxes or manual recommendation steps appear in this
normal flow.

**Advanced options** contains:

- **Match exact phrase:** uses the existing record phrase search, preserving
  its source-status/date/work-detail behavior. It is local only and hides the AI
  answer action so a semantic answer is not misrepresented as respecting an
  exact-phrase constraint. Clear the checkbox to request an ordinary AI answer.
- **Record version → Observed by a date:** selects the existing historical
  preview and consented answer flow. Source/type filters apply. Current date,
  source-status, work-detail and exact-phrase controls do not apply in this flow.
  Historical selection remains keyword-based; no historical vectors are added.
- Current-source status and optional Codex work details remain explicit filters.
  Normal keyword search defaults to excluding source-deleted records. Exact
  phrase/filter-only browsing can show all locally retained records by default,
  as labelled by its source-status option. AI requests continue to exclude
  source-deleted/work-only records independently.

Period review hides the question input and uses source/type, date basis and
an inclusive date range of up to 92 days, followed by the existing reviewed
retrospective action. It defaults to source/event dates when switching purposes.

New ordinary URLs use `mode=search`, with `exact=true` for phrase search. These
UI parameters are stripped from API requests. Legacy unmoded phrase URLs and
`mode=passages|semantic|answer|historical|retrospective` URLs remain readable.
New submissions use the consolidated form. Citation return paths retain the
purpose, question, filters, exact/version options and page. Answer panels and
results in legacy modes remain ephemeral. Ordinary saved answers now return to
the conversation; returning/reloading never replays paid stages.

Draft or purpose/version changes and closing the answer panel synchronously
abort pending stages; the controller is created on click before mutation work
can begin. Account-specific query keys isolate local/availability caches, and
failed local rechecks hide previously cached bodies. Opening/closing Advanced
options does not change the reviewed filters; its open state persists when
clearing exact phrase matching.

### Verification for this UI checkpoint

Frontend 194 tests, lint and production build passed. The new tests cover local
search with no provider/status calls, AI-off operation, exact-phrase routing,
consent, hidden internal controls, citation/page return, cancellation on draft,
purpose/version/account/panel changes and stale-cache suppression. Existing
reader/legacy workflow tests were adapted to the new user-facing form rather
than removed. A browser-discovered Advanced panel collapse was corrected and
covered by a regression test. No backend code/schema or dependency changed, so
the backend suite was not rerun for this UI-only checkpoint.

Standalone Chromium verified the actual synthetic API flow on desktop and a
390-pixel mobile viewport: local AI-excluded note visibility; no request before
consent; integrated question and citation return/reload without replay; exact
phrase; historical Alpha observation; period summary; no horizontal overflow.
Provider responses were mocked, with zero actual OpenAI calls. The in-app browser
connection failed; standalone Chromium was used. Ignored screenshots are
`.local/verification/search-unified-desktop.png` and
`.local/verification/search-unified-mobile.png`.

Optional visual review uses the already running synthetic frontend at
`http://127.0.0.1:5174` and API at `http://127.0.0.1:8002`. Log in with
`demo@example.test` / `demo-password`; choose Search in the main navigation to
start with the new form. Search `worker`, open **Get an answer with sources**,
review consent and request a mocked answer. Under Advanced options, exact phrase
stays local; Observed by a date with `Deployment history`/`2026-01-31` shows Alpha.
**Review a period** with January 2026 shows the dated retrospective preview.
No mandatory user repetition is needed for functional verification.

## Consent and execution limits

One explicit action authorizes the question for search and answering plus up to
five automatically selected original passages from current AI-allowed records
matching the reviewed filters. Both record and source permissions still apply;
work-only, deleted-source and unsupported record types remain excluded.
Recommendation does not assert that the proposed text is sufficient evidence.
The answer must distinguish support from insufficiency under the existing contract.

Limits reuse the existing backend guards:

- Query: one call, at most USD 0.001.
- Answer: one call, at most USD 0.01; 4,096 ordinary output tokens (512 for period/historical);
  14 KiB serialized request;
  at most five full Passages, each at most 2,000 characters.
- Combined maximum: two provider calls, USD 0.011 for one action. Each backend
  stage also enforces the shared configured monthly allowance. The second stage
  may fail if remaining budget was consumed in between; paid query usage remains.
- One UUID is reused in the separate existing query/answer ledger domains.
  Duplicate requests for either stage cannot spend again after a spent/uncertain
  attempt. Explicitly starting a new action makes a new UUID and can incur a new charge.
- There is no automatic retry, recovery/resume, or paid call on reload/back navigation.
  This slice does not add a server workflow or answer persistence.

The frontend freezes parameters/session/revision and awaits each existing API
before proceeding. Before query dispatch it checks local answer availability;
status reads and recommendation cause no egress or reservation. It rechecks
session, abort state and revision between stages. The answer API accepts an
optional strict `policy_revision` and rejects mismatch before reservation/dispatch.
The automatic flow always supplies it; the earlier manual API remains compatible.
Current exact source checks under the dispatch lock still run before and after
provider requests. No source permission or environment activation was changed.

## Stop, changes and failures

**Stop**, navigation, switching to manual mode, or editing the question/filters
aborts browser work and prevents subsequent stages. Account/revision changes
reset the flow. A 60-second browser deadline also prevents later stages; existing
bounded provider/database deadlines still apply. Aborting a fetch does not
withdraw an already dispatched provider request: it may finish and be charged.
Source changes or policy revocation suppress stale results, and uncertain ledger
reservations remain conservative. No automatic release or replay occurs.

No search hits or no parent fitting the request means no answer call. An
insufficient generated answer has no citation. Stage errors are visible, consent
is cleared after settlement, and re-execution requires a new explicit action.
Query/question/answer bodies remain ephemeral screen state; only the existing
body-free usage ledger persists accounting. Existing URL search parameters retain
the reviewed question/filters and never trigger automatic paid execution.

## Verification

- Full backend: 589 tests passed, including new HTTP checks for stage-domain
  replay protection, optional revision validation, between-stage policy change,
  spent query retention on budget failure, uncertain answer reservations and
  revision changes after authentication but before acquiring the read lock.
- All 150 frontend tests passed, including success, insufficient/no-hit/disabled-index paths,
  every stage failure, stopping during query/recommendation, late responses,
  question/filter/account/manual-mode changes, policy refresh, citation return,
  double clicks and the whole-action deadline.
- Frontend lint/build and whitespace checks passed.
- Real Chromium against the disposable synthetic API: one consent/action produced
  one query, one local recommendation and one mocked answer, with a shared action
  ID and Passage citation. Citation return and reload caused no replay; advanced
  manual mode remained available. Private screenshot: `.local/verification/question-flow.png`.
- Initial sandbox PostgreSQL access was blocked; isolated host DB tests passed.
  In-app browser connection failed because its tool lacked sandbox metadata;
  standalone local Chromium verification passed. Browser tooling is installed
  only under ignored `.local/verification/browser-tools`, outside app dependencies.

This validates workflow and isolation, not accuracy on fresh personal questions.
The prior 3/8 → 6/8 context coverage result is unchanged and does not become a
new independent quality claim. Additional paid evaluation requires a separate
frozen data/cost scope; this implementation makes no new OpenAI request.

## Owner review: exact steps

The synthetic API on 8002 and frontend on 5174 were left running. Open
`http://127.0.0.1:5174/login` and log in as `demo@example.test` / `demo-password`.
These credentials are disposable demo credentials, not a normal account.

1. Open Search; select **Answer with sources**.
2. Enter `Where does the import worker run?` and choose **Review question**.
3. Check the combined OpenAI consent and choose **Ask from my records** once.
4. Expect a `[Synthetic]` draft with a clickable original-passage citation, without
   selecting or recommending passages yourself. Expand the passage review below
   the answer to see the exact context. The demo uses canned provider responses;
   it verifies the interaction and has no OpenAI charge.
5. Open a citation, return to Search, and refresh: the mode/filters remain, but
   no paid flow repeats. **Choose evidence manually (advanced)** opens the earlier
   manual search/recommendation/answer workflow if desired.

Mechanical checks above were performed by the agent. Owner feedback can focus
on whether the consent and source review are clear and the default flow is easy.

If the preview is stopped, from the repository root run:

```bash
.venv/bin/python scripts/preview_semantic.py --database-url postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test --port 8002
```

In a separate terminal from `frontend` run:

```bash
LIFHOP_API_PROXY_TARGET=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

Reuse an existing matching preview instead of starting it again. No normal API,
import worker or embedding worker is needed for this disposable demo.
