# lifhop Current Status

Last updated: 2026-10-09

## Current product slice

Phase 3.2B1 tooling and the first owner-approved real OpenAI experiment are complete.
The provider defaults off; the owner's ignored local configuration enables OpenAI.
A body-only current-passage gate, explicit query consent, durable project-wide
cost reservations/reconciliation and authenticated dry-run/run CLI are available.
Vectors remain in bounded memory; reports/manifests contain no source/query bodies.
Development migration `e26b9c13a842` is applied. Synthetic integration checks cover
durable dispatch, timeout accounting, owner-lock serialization, empty-month budget
races, CLI comparison and stale manifests.

On 2026-10-09 the owner approved transmission of 43 GitHub documents/267 body
passages and three frozen pilot questions for `b@test.com`, `repo:1228467402`.
The repository source policy and those 43 record permissions were enabled and
remain enabled; other record permissions were not changed. A fresh explicit-ID
manifest estimated at most USD 0.007779. Run `b438d06014304c9ea8c5ddb6dc2b5741`
completed 28 calls (25 document batches/3 questions), 81,572 tokens, in 16.13s.
All usage is settled as spent: USD 0.001643 in the conservatively rounded app ledger.
The two Korean questions failed complete gold-span coverage at top 20 in all
three methods. The English gold span ranked lexical 1, semantic 19, hybrid 4.
There were 171 non-gold groups; the B2 benefit gate is `criteria_not_met`.
Existing search remains unchanged. Next: inspect chunk selection, grouping and
ranking against the frozen questions before authorizing another paid comparison.
The private report contains IDs/scores/usage only; vectors remain memory-only.
B1 omits commit diffs, LOGs and work passages by default. B2 pgvector/worker/browser
semantic modes are not implemented and await demonstrated B1 benefit and owner confirmation.
Plan: `SEMANTIC_SEARCH_PLAN.md`; commands: `SEMANTIC_SEARCH.md`.
Final B1 checks: 357 backend tests passed, including 18 focused semantic tests;
migration upgrade, CLI integration and whitespace checks passed. Earlier CLI vector
unwrapping and committed synthetic-fixture cleanup failures were corrected.

Phase 3.2A local passage retrieval is implemented and owner browser checks 1–5
are confirmed, including disposable note create/edit/delete search updates.
The passage reader now has dedicated desktop/mobile inner padding.
Search keeps Exact phrase and adds Passages with current-version source offsets,
bounded original readers, lazy retained-snapshot locations and preserved return URLs.
PostgreSQL simple FTS ranks body matches; identical verified GitHub document chunks
group before representative-Entry quotas and pagination. Source-deleted records are
excluded by default and can be explicitly included locally. No embedding, answer,
external AI request, dependency, queue or worker was added.

Migration `d15e8a02b731` is applied to development. Create/edit/select/reimport and
delete synchronize disposable current passages in the source transaction; historical
versions remain unchanged. The authenticated `scripts/index_passages.py` resumes
bounded owner-scoped backfill. The selected `b@test.com` account has 480 ready records
(448 real and 32 synthetic); backfill took 3.73 seconds and preserved the source/policy
manifest. Existing records in other accounts may still need backfill.

The owner authorized necessary real-record reads by the current Codex for this
development/verification. This does not change application AI policies, authorize
embedding/answer API transmission or share private sources with Antigravity.
The frozen three-question pilot remains revision 2. Same-snapshot literal versus
passage checks found natural-question support in 0/3 versus 1/3 cases; the two Korean
questions still fail. Auxiliary mean recall@20 was 1/3 versus 1, scoring complete
gold spans and verified snapshot aliases for passages. This is one English README,
not broad semantic-search quality. Original dataset/baseline reports remain intact.

Disposable migrated PostgreSQL/HTTP/Chromium checks cover owner/current boundaries,
edit/delete/restore, Codex primary/work mapping, snapshot filters/grouping, pinned
readers and 390/768/1440px returns/layout; no external browser requests occurred.
Plan: `PASSAGE_SEARCH_PLAN.md`; operations: `PASSAGE_SEARCH.md`. In-app browser
connection failed; separate Chromium provided the synthetic browser verification.
Final checks: 339 backend tests, 110 frontend tests, lint/build, migration upgrade,
OpenAPI alignment and tracked/untracked whitespace checks passed. The 42 targeted
passage/evaluation tests include source rollback on projection failure.

Phase 3.1 evaluation tooling is implemented; the real private set is not complete.
Owner-selected account: `b@test.com`. The owner initialized the private set locally;
the original set is now revision 6 with all 20 cases draft. The owner returned
case-04 to draft after its first registration/semantic review; revision 5's reports
remain historical provisional results. A separate three-question private pilot
now has three owner-approved answers in revision 2, each linked to an exact valid
span from one retained README snapshot. Both baselines completed: natural questions
found no results; auxiliary mean group recall@20 is 1/3 (two cases found the target
with one of two queries each, at rank 12; the other case found neither within top 20).
All three scored cases passed evidence checks with no failures. These are a limited
first baseline, not a broad corpus or answer-quality guarantee.
This smaller first check preserves the roadmap's eventual diverse about-20-question target.
The retained
corpus has 415 real GitHub and 33 Codex records;
32 synthetic records were excluded. All records currently deny external AI.
The owner explicitly authorized limited agent reads of case-04's selected claim/span
and selected source excerpts for three pilot questions; source policy settings remain
unchanged. Those were scoped authoring permissions; the later development-read
authorization is described above. Keyword matches do not prove factual support.
The three-question pilot was owner-approved and both fixed baselines were run;
the original 20-case set still needs verified facts and evidence.
No owner password was supplied to the agent. The owner ran the provisional case-04
baseline locally; the pilot was approved after explicit owner confirmation and
scored in a read-only snapshot. Original reports and source AI settings remain intact.
Owner checked case-04: the linked candidate mainly identifies code location and
does not clearly answer the worker's purpose/execution location.
Its old support was removed in revision 3; the tentative insufficient-evidence case
was superseded in revision 4 after the owner reported supporting sentences.
The owner registered revision 5 locally. On explicit one-time permission, the agent
read only that case's entered claim and selected excerpt: the claim does not directly
answer the question, and the selected span does not support all requested aspects.
Hash/owner/version validation passed; semantic approval is not established by those
checks. Case-04 is now draft and excluded from future scored denominators.
Primary retrieval found no result; one of two auxiliary queries hit the evidence at
rank 1, the other found none (mean group recall@20 0.5). These are retrieval measurements.
An owner-only local review sheet shows pinned saved excerpts and up to five other
keyword matches per case (37 alternatives in this snapshot), using saved filters.
No candidate was automatically approved. This private HTML contains source text
and must stay local; measurement reports continue to omit source bodies.
The CLI uses read-only PostgreSQL snapshots, immutable private revisions, the same
keyword search conditions/ranking as the API, versioned passage hashes and body-free
reports. Natural questions and auxiliary keyword scores are separate. Synthetic
20-case migrated-schema verification and Chromium reports passed; no schema,
dependency, AI call or worker was added. Plan: `EVALUATION_PLAN.md`.

Phase 2.4B GitHub discussions is implemented; the owner confirmed the synthetic
browser flow using `GITHUB_DISCUSSIONS.md`. A separate manual collector prepares/seals/applies
PRs/issues/comments/reviews, retaining independent versions and policy/deletion
boundaries. Repository Discussions groups roots before pagination, reads children
lazily, preserves missing-parent groups, and focuses Search hits on their page.
No migration, dependency, worker, external AI or AWS service was added.
Selected `moonkongv2/jy_yamyam` has 0 PRs/issues as of 2026-10-06: real empty
preparation and isolated PostgreSQL/HTTP apply/replay passed. A labeled 30-record
fixture passed isolated HTTP/Chromium checks; live nonempty/private sources and
personal-account apply remain unverified. Plan: `GITHUB_DISCUSSIONS_PLAN.md`.
Final local checks: 297 backend tests, 104 frontend tests, lint/build and whitespace
checks passed. The existing sealed 415-item Phase 2.4A preview still validates.

GitHub repository browsing checkpoint after Phase 2.4A is implemented;
owner browser confirmation is next. Entries groups GitHub by numeric repository
scope before pagination. Repository pages show source-date ordered commits and
path-grouped retained document snapshots, with separate document/snapshot pages.
Search stays Entry-level with repository context; readers/sidebar preserve return
URLs. Existing Entries, versions, permissions and receipts are unchanged.
No migration, dependency, external AI call or service was added.
Implementation plan: `GITHUB_REPOSITORY_VIEW_PLAN.md`; checks: `GITHUB_BACKFILL.md`.

Phase 2.4A GitHub commits/document backfill is implemented with local checks;
owner verification is next using `GITHUB_BACKFILL.md`. Strict run/evidence contracts,
pinned resumable preparation, reviewed apply, Sources results and GitHub readers
reuse the existing PostgreSQL history/receipt model; no migration/dependency was
needed. The plan and implementation are included in this Phase 2.4A commit;
owner verification remains pending.
Full selected public preparation is finished: 372 commits + 43 document snapshots
(415 items), following quota pauses and owner-selected GitHub CLI authentication.
All 415 were verified in isolated PostgreSQL + real HTTP/browser; same/equivalent
preview replay, owner/policy/annotation/delete checks passed. Oldest/latest source
samples match fresh GitHub reads. The sealed full preview is private; no personal
account apply was run. Evidence omissions correctly finish Partial. Owner account
apply/browser confirmation and private/org access remain pending. The owner explicitly
requested implementing Phase 2.4B while those confirmations remain pending.
Authentication/verification follow-up: `48f6f52`.
Codex plan: `bdfcd57`; session browsing: `ab40b30`; saved titles: `fd7597b`;
conversation-only reading: `2598187`. Local checks pass. Development DB upgraded to
`c04d8a12e673`. Phase 2.3 implementation is committed at `36de1de` with whitespace
cleanup at `63f0c1a`; owner confirmed its preview. Personal apply remains unverified.
Phase 2.1 committed at `69dc764`; owner requested continuing without its HTML
preview check. Phase 2.2 committed at `d99ef9e`. The owner
confirmed successful synthetic-demo execution (Entry 1270) and authorized the
commit; the complete browser scenarios in `HISTORY.md` remain pending.
Phase 2.2 migration `a22b8c30d567` gave all 1,266 existing Entries one
initial observed version; source timestamps/history were not invented.
Local API health/new routes verified and import/purge worker restarted.
The owner requested a Notebook-inspired frontend refresh before further collection
work, followed by separating Search from recent Entries. Implementation and local
checks are complete. The owner requested English-control/session fixes after
browser review and authorized committing the UI checkpoint. The broader visual
walkthrough remains available in `frontend/README.md`.
UI checkpoint: `19e395a`. Owner confirmed B synthetic discussion browsing;
A repository browsing and personal apply remain separate pending checks.

## Personal-release target

Finish private daily use before commercial service work. Prioritize past
solutions and decision reasons, then period retrospectives, then project
resumption; include ordinary life records without requiring a project.
The agreed additional sources are Codex CLI on one Mac and selected personal/
organization GitHub repositories, including accessible historical records.
Both need scheduled collection and collect-now controls. GitHub delivery starts
with commits and key documents; PRs/issues remain in scope.

The release must support access from other devices/external networks, prefer
AWS, and fit a combined hosting/storage/AI budget of USD 20/month. Version
retention, deletion suppression, and source/repository/record-level external-AI
exclusions are implemented foundations; full collectors remain upcoming.

## What works now

- Private evaluation CLI: init/draft/review-sheet/record-answer/edit/inspect/anchor/validate/review/run with explicit
  local authentication, owner/database binding, immutable revisions and fixed queries.
  Current-vs-historical evidence, AI eligibility, collection gaps and failed-score
  denominators remain explicit. Synthetic fixture readiness never counts as the
  real evaluation set. First full backend check failed 5 tests because the concurrent
  evaluation test left committed fixture rows; fixture cleanup fixed that and the
  rerun passed 316 tests; final checks including local candidate authoring passed
  319 backend tests (22 evaluation tests). Reports passed 390/1440px standalone Chromium checks with
  no page errors, outbound requests or document overflow. Real owner data/large
  corpus benchmarks remain pending; private files stay in ignored `.local/evaluation/`.
  Candidate claims cannot be approved unchanged. There are no explicit SHA overlaps
  between these retained Codex turns and GitHub commits; life/PR/issue support remains
  incomplete. Candidate relevance and adopted decisions require owner verification.
  Review previews validate owner/version/hash before displaying excerpts, omit
  deleted/stale/invalid spans, escape source HTML and keep immutable private files.
  Export does not edit evidence, approvals, records or policies. Regenerate after
  changes; saved local HTML is a snapshot and may retain previously exported text.
  Final follow-up checks: 322 backend tests (25 evaluation tests), compile/help and
  whitespace checks passed. Synthetic review expansion/escaping passed Chromium at
  390/768/1440px without errors, outbound requests or overflow. An initial excerpt
  test exposed a missing first character; correcting the paragraph boundary fixed it.
  Guided record-answer lets the owner select evidence, enter each verified fact,
  explicitly approve, save one immutable revision and generate both baselines.
  Canceling before approval saves nothing; benchmark failures after registration
  leave the approved revision intact and can be retried with run.
  Latest registration checks: 324 backend tests (27 evaluation tests), compile/help
  and whitespace passed. Synthetic end-to-end registration confirms two claims,
  two reports, unchanged source AI policy and cancellation without publication.

- GitHub discussions: typed source IDs, immutable private previews, mutable-source
  staged resume, kind-count receipt checks and existing observed-version rules.
  Discussions tab, per-root lists, orphan-date filters, lazy comments/reviews/code
  context, individual history/deletion, SHA role links and search focus work.
  Selected actual source is empty; synthetic 30-record real HTTP/browser checks
  cover paging/reload/readers/search/Sources at 320/390/768/1440px without overflow
  or page errors. Test details and owner walkthrough are in `GITHUB_DISCUSSIONS.md`.

- GitHub repository browsing: owner-scoped grouping before archive pagination,
  compact chronological commits, document paths and historical snapshots,
  individual search references and reader/sidebar return preservation. Latest
  checks: 282 backend tests, 97 frontend tests, lint/build, generated API types
  and whitespace checks passed. Actual 415-item isolated PostgreSQL/HTTP checks
  show one repository, 372 commits, 13 document paths and 43 snapshots, preserving
  replay/annotation/AI-deny/deletion behavior. Real HTTP Chromium navigation,
  reload/new-tab/search returns passed at 320/390/768/1440px with no page errors
  or horizontal overflow. Early sandbox TCP and browser transport teardown issues
  were resolved by the approved DB run and corrected verification cleanup.
  Personal account apply and owner browsing confirmation remain pending.

- GitHub commit/diff and historical Markdown snapshot collection: private cached
  preparation with pinned heads, quota pause/resume, immutable preview validation,
  authenticated idempotent apply and owner/policy/deletion checks. Sources provider
  switching and current-version evidence readers connect related commit/doc records.
  Backend 276 tests and frontend 87 tests passed; Chromium synthetic UI checks fit
  320/390/768/1440px. Final lint/build and OpenAPI consistency checks are recorded
  in `GITHUB_BACKFILL.md`. No real account apply was performed.

- Entries groups current Codex turns by owner/scope/thread before server pagination;
  other records remain individual. Sessions retain fork/archive/gap metadata,
  inferred-order warnings, lazy turn reading and focus links from Search.
  Final answers and unknown messages stay in primary reading/search; explicitly
  classified commentary stays in Work details and an optional search scope.
  Per-turn history, annotation, delete/suppression and AI permission remain intact.
  Read turn and Codex Entry detail show only user/assistant messages, excluding
  classified commentary. Commands/results/diffs remain in Work details and search.
  Collection gaps are a separate notice. Existing structured records need no
  recollection; records without valid structured evidence retain a warned full view.
  Current-version primary_content is derived separately; existing bodies/hashes
  remain unchanged. v1 manifests/receipts remain valid, v2 records phase/order.
  Session titles prefer saved Codex names; fallback titles normalize whitespace
  and cap display at 60 characters plus an ellipsis. First questions appear in
  separate two-line card previews. Original turn titles/content remain unchanged.
- Latest checks: 249 backend tests, 83 frontend tests, lint/build and whitespace
  checks pass. Real loopback HTTP/isolated-schema verification covers 25 synthetic
  turns, search scope, grouped count/focus and replay without duplicate versions.
  Synthetic Chromium checks pass at 320/390/768/1440px with no page errors.
  An initial full run's health test used an offline development DB; corrected
  DATABASE_URL/TEST_DATABASE_URL isolated settings passed. Frontend old list/cache
  assertions were updated for archive; an initial browser stub intercepted module
  imports and was corrected. No unresolved check failures remain.
  The added snapshot-index test initially called a yielded generator as a function;
  correcting that test passed. Saved-name sanitization, latest valid index row,
  legacy serialization, name priority and fallback/preview are covered.
  Final targeted rerun hit sandbox TCP restrictions; the approved host rerun
  passed all 28 collector/session tests. No application failure remained.
  The new conversation test initially omitted required command/diff item IDs;
  correcting its fixture passed. Reading excludes tools without changing search,
  evidence, versions, or command-like text inside an assistant answer.
  The supplied sample.html matched a private preview: seven command/result blocks
  are excluded from reading, leaving two messages (18,485 → 2,404 characters),
  with no server writes. Synthetic Chromium reading/work checks pass at four widths.
- Installed CLI 0.160.0 schemas and actual bounded reads verified: 33 turns from
  10 selected readable lifhop sessions, with 63 commentary and 32 final messages.
  Original v1 preview's 33 payload digests remain unchanged. New private v2 preview
  is `.local/verification/codex-session-v2/preview`; it has not been uploaded.
  A separate title-verified preview at `.local/verification/codex-session-titles-verified/preview`
  captures saved names for 4 sessions/25 turns. The owner's local apply checkpoint
  acknowledges all 33 turns; final run status and current-version UI are unverified.
  `scripts/seed_codex_session_demo.py` creates an explicit synthetic 25-turn local
  source for user checks. See CODEX_BACKFILL.md.
- Codex CLI 0.158.0 manual backfill: explicit project/thread selection, exclusions
  and date filters, immutable private sanitized preview, device-scoped turn IDs,
  bounded official reads against disposable snapshots and explicit gaps.
  Authenticated direct HTTP apply saves Entry/version and receipt atomically;
  interruption/lost acknowledgment can resume without duplication. Server receipts
  verify local checkpoint skips. Ownership, collection policy, deletion suppression,
  annotations and AI-off defaults are preserved. No S3, worker or new AWS service
  is required for Codex text ingestion. Sources displays paginated runs/coverage;
  Search and version inspection show ordered recorded evidence and omissions.
  See `CODEX_BACKFILL.md` for execution and verification.
- Phase 2.3 checks: 237 backend tests with fresh-schema migrations, including actual
  loopback HTTP synthetic apply/replay and pre-commit rollback; 80 frontend tests,
  lint/build pass. Synthetic Chromium Sources/search/evidence/failure/retry checks
  pass at 320/390/768/1440px. A final-suite setup attempt used the wrong test DB
  account; the corrected rerun passed. Actual private preview selected 13 of 171
  files, read 10 sessions, failed 3 and prepared 33 turns; SOURCE_CONFLICT and
  EMPTY_HISTORY remain gaps. Personal source content has not been uploaded.
- FastAPI/PostgreSQL backend with authentication and user-owned Entries.
- Observed versions, explicit current pointer, source identity/locator/times,
  content/evidence SHA-256, parser/completeness and original-material links.
  Newer complete snapshots replace current; older/partial/unknown-time candidates
  remain inspectable. Unchanged replay has no duplicate Entry/version.
- Imported content read-only; separate personal annotations survive imports.
  Manual editing works. Browser history/provenance and explicit version selection.
- Confirmed source-deletion markers retain content; unavailable/unknown is distinct.
  Search explicitly filters source state and otherwise includes retained records.
- Lifhop deletion removes body/versions/annotations immediately, blocks reimport
  through minimal identities, and durably queues original purge in the worker.
  Shared ZIP deletion blocks/removes the entire raw object, preserving other text.
- Sources UI separates collection and AI permission; AI starts disabled at source
  and record levels. Egress guard checks every dependency/policy revision; mocked
  embeddings/reranking/summary/answer/telemetry deny tests pass. No AI provider is
  connected. Latest deletion-ledger export/apply protects isolated restores.
- Owner-scoped literal phrase search in title/content, combined source/type/date
  filters, total counts, and 20-record browser pagination. Search has its own
  `/search` screen; `/entries` shows recent records. Empty Search makes no API
  request; keyword and filter-only searches apply on submission. Old filtered
  `/entries` URLs redirect to Search. Validated detail return URLs preserve
  origin, conditions and page across sidebar navigation, reload and new tabs.
  Entries pagination survives note creation/cancellation.
- Title matches rank before body matches, then newest registration and ID. Dates
  are displayed/filtered in Asia/Seoul; registration and source/event dates are
  separate. Missing event dates are never inferred from text.
- New notes/Markdown imports have explicit provenance. Only old Markdown rows
  with matching owner/artifact MIME evidence are backfilled; other unproven
  sources remain unknown. User/date/ID index supports ordered browsing.
- Browser Markdown/ChatGPT ZIP upload, job polling/history, saved progress counts,
  sanitized item errors, paginated result Entries, retry, and protected originals.
- Local SeaweedFS storage and PostgreSQL ImportJob queue are defaults; explicit
  AWS S3/SQS modes remain available. Worker startup is separate from the API.
- Original artifact links on newly imported Entries; persisted job result IDs.
- ZIP upload/download uses bounded streams and temporary files. Legacy and
  numbered conversation JSON arrays are parsed one record at a time. Defaults:
  ZIP 1 GiB, declared archive 1 GiB, JSON 256 MiB, one record 16 MiB.
- Entries and progress commit together every 25 items. An owner session lock on
  a pinned PostgreSQL connection serializes imports across commits. Interrupted
  attempts resume from durable counts; full item-error retries replay the file.
  Three attempts, completed-delivery no-op, and item savepoints remain.
- S3-backed Entry attachments.
- Local S3-compatible storage is the default for development; tests block
  unexpected AWS client creation.
- React login, Entry list/detail, and note creation/editing/deletion using
  authenticated Entry APIs and server-result cache updates.
- English interface labels, instructions, job statuses, and frontend error messages.
  Dates use English formatting in Asia/Seoul; user content retains its language.
  Search/Markdown date controls use an English calendar and `YYYY-MM-DD`;
  Markdown time uses `HH:mm` in the device timezone. File selection and form
  validation messages stay English even with a Korean browser locale.
  Login changes to Logout after authentication. Logout clears tokens/private
  query caches, redirects to Login, and propagates to other tabs. API 401 responses
  end the matching session with an English notice; stale responses cannot restore
  the previous session's record cache.
- Light panel UI: collapsible Search filters and preview cards; detail record navigation,
  full-text reader, and annotations/history. Import, Sources, job, note, and login
  pages share the same styles. Narrow screens stack panels. Delete lives in the
  record actions menu with an explicit confirmation near the top of the reader.
  Switching records resets the previous edit state and preserves list filters.
- Empty/loading/error states, draft-preserving save errors, title validation,
  deletion confirmation, and account-switch cache clearing.
- Read-only Codex/GitHub verification CLI produces private local HTML/JSON previews,
  with source IDs/dates, command outcomes/diffs, coverage, and omissions. These
  Phase 2.1 commands do no Entry writes, uploads, model execution or scheduling;
  Phase 2.3 adds a separate explicit Codex apply command.
- Codex CLI 0.158.0 official app-server reads run against disposable rollout/history
  DB copies. Local inventory: 169 files; selected historical sample: 3 turns,
  22 command items and 3 file-change items; list/turn pagination verified.
- Selected public GitHub repository `moonkongv2/jy_yamyam`: 3 branches inventoried,
  only `main` selected; 372 reachable commits across 4 pages. One commit's 2 file
  patches and README at its pinned SHA verified through anonymous REST GET.
- Disposable PostgreSQL tests use real migrations in fresh schemas. Local
  Phase 2.2 checks: 211 backend tests (25 acquisition and 25 history/policy cases).
  UI checkpoint checks: 79 frontend tests, lint/build pass; backend unchanged.
  Local Chromium checks with synthetic API responses cover Entries, Search initial/
  results, detail, Import, Sources, job, login and new note at desktop/mobile sizes,
  plus 320/768/1024/1280px layouts. Search submission, filter-only queries, reset,
  legacy redirects, new-tab/reload return context, active menu, deletion cancellation,
  history, annotations and draft reset pass.
  Korean-locale Chromium checks also pass for English date/time/file controls,
  calendar selection and viewport bounds, login/logout, logout after reload,
  cross-tab logout and expired-session redirects. No application Korean labels
  remain in the source audit; Korean user-content fixtures remain intentional.
  This UI check does not establish actual DB/storage integration.
- Actual local HTTP/S3/worker checks passed with a 512 MiB synthetic ZIP and a
  494 MiB owner archive in isolated schemas. Original hashes, search counts,
  reimport uniqueness, visible progress, and synthetic worker-kill recovery passed.
  Worker peak RSS was about 119/211 MiB respectively; these are local measurements.
  Test objects/schemas were removed.
- Phase 2.2 real HTTP/SeaweedFS synthetic Markdown/shared-ZIP deletion checks
  passed in an isolated transaction/schema: blocked downloads, removed objects,
  retained sibling text, and rollback cleanup. Actual AWS purge is unverified.
- GitHub Actions checks for migrations, backend/frontend tests, generated API
  types, and frontend lint/build (remote workflow execution pending).

The learning-through-F3 baseline is marked by Git tag
`learning-complete-f3` at `187b651f9422e901059f238c334d0e5fa885b4f4`.
The project remains a learning project; delivery from here follows the
user-verifiable product slices in `ROADMAP.md`.

## Next

1. Diagnose the measured 3.2B1 Korean retrieval failures and English rank regression
   before another paid comparison or B2 implementation. Local API setup and the
   scoped 43-document/3-question transmission grant are complete. Preserve the
   frozen Korean→English cases and exact gold-span scoring.
   Case-04 remains draft. Complete the remaining questions:
   check question/claim/span meaning, distinguish insufficient
   evidence from known collection gaps, then approve about 20 real questions and
   freeze the natural-language/keyword baselines. Candidate links alone do not
   establish support. Owner confirmed Phase 2.4B synthetic browsing; actual source is empty.
2. Confirm GitHub repository browsing in Entries → repository → Commits/Documents
   → reader → return, and Search → Browse repository → return. Existing stored
   GitHub Entries need no reimport for this UI. Repository browsing and the earlier
   authentication/verification follow-up are separate commit checkpoints.
3. Verify Phase 2.4A using `GITHUB_BACKFILL.md`: synthetic Sources/search/evidence,
   private partial preview review, explicit personal apply and same-bundle replay.
   Full source preparation and isolated actual verification are complete. Apply the
   reviewed 415-item preview in the owner terminal; confirm Sources/search/results.
4. Verify the owner-bound private Phase 2.3 apply run status in Sources and
   Codex search/evidence, replay, annotations and disposable deletion/policy checks
   in `CODEX_BACKFILL.md`. Its checkpoint has 33 acknowledgments; completed status,
   target account and selected current versions still require confirmation.
5. Expand retrieval evaluation across sources/languages and plan Phase 3.3 cited answers
   after the 3.2B semantic-search decision.
6. Verify Phase 2.2 using `HISTORY.md`: synthetic history, annotations, source
   markers, deletion/reimport block, and Sources permissions.
7. Follow the sequence: Codex/GitHub history → evidence-based answers/retrospectives
   → scheduled collectors → private AWS release.

## Known limitations

- Phase 3.1 real question/evidence approval and owner report review remain pending.
  The CLI reads the configured local DB and report links assume the app uses that DB.
  Historical-only Entry hits are separate from passage retrieval; no AI answer or
  claim-grounding/abstention test is performed. Exact natural-question substring
  search may have low recall. Missing/invalid/timed-out cases stay visible; synthetic
  corpora do not establish real quality. Very large corpus performance is unverified.

- Repository document lists show the latest retained snapshot by known event date,
  then ID; they do not promise the current GitHub file or selected HEAD contents.
  Unknown dates sort last. Paths renamed in Git remain separate. Counts describe
  retained records, including source-deleted records, rather than source coverage.
  Offset pages can shift during concurrent collection/deletion. Only bounded
  current-version metadata is classified; invalid records remain accessible.
- Legacy assistant phases and missing turn positions stay unknown. Same-time v2
  observations can be retained candidates requiring explicit current selection.
  Session counts describe retained turns, not full source coverage. Session-wide
  deletion/settings are not implemented. JSONB grouping was checked on small
  synthetic data; large-corpus performance is unverified. Concurrent offset pages
  can shift. Owner Codex reading screens are confirmed; mobile-device checks remain pending.
- Owner confirmed the initial and large-ZIP Phase 1.2 flows in the browser.
  Phase 1.3, English UI, and Phase 2.1 owner preview checks remain pending.
  Remote CI execution remains pending; frontend automated tests stub API.
- Refreshed UI owner review is pending. Chromium layout/interaction checks use
  synthetic API responses; other browser engines and actual mobile devices remain
  unverified. Theme is light; a dark theme is not implemented.
  OS file-picker dialogs and browser-owned menus can use the device language.
- Exact phrase is literal case-insensitive substring search. Passages uses local
  simple FTS/lexical ranking; no translation, embeddings, fuzzy matching, attachment
  extraction or LLM answers. Cross-language pilot questions still fail. Backfill is
  required for old records; 8 MiB input/512 passage limits and unverifiable Codex
  mapping surface as partial coverage. Very large corpus performance is unverified.
- Offset pages can shift when records change concurrently. Timezone is initially
  fixed to Asia/Seoul; changing it in user settings is not available.
- Recent job history shows the latest 20 jobs; Entry lists/job results paginate.
- Progress updates at batch commits. Preflight validation initially shows zero
  total; upload byte percentages are not shown. Textless active branches appear
  as EMPTY_CONVERSATION errors and can produce a PARTIAL result.
- Earlier imported Entries/jobs have no reconstructed missing artifact/result
  links. Existing duplicate Markdown rows are preserved separately; future
  identical uploads match their initial canonical byte identity. Explicit document
  IDs and verified source modification times track changed Markdown versions.
- GitHub commit/document ingestion is implemented; owner apply remains pending; full selected actual preparation and isolated
  verification are complete. GitHub discussions are implemented with empty-source
  and synthetic checks; live nonempty/public/private/org discussion access and
  personal-account apply remain unverified. The owner confirmed synthetic discussion
  browsing. Collection is a mutable observation
  window; edited reviews without a source clock need manual current selection.
  Discussion-wide deletion and scheduled collection are not implemented. Codex backfill
  and reading are implemented and owner screen verification is complete; final
  apply run/account/current-version diagnostics remain separate follow-up checks.
  Codex backfill supports installed CLI 0.158.0/0.160.0 with bounded snapshots;
  the separate Phase 2.1 probe remains pinned to 0.158.0.
  conflicts, empty legacy responses and unknown/divergent snapshots remain gaps.
  Other installed CLI versions, private repos, organization SSO,
  and expiring-token access are not verified with real samples. Preview truncation
  and incomplete secret redaction require reports to stay private. Full collection
  volume and deployment cost still need verification.
- The ChatGPT Web extension is experimental and currently unreliable on
  affected pages. Do not use it as the product's dependable capture path.
- Attachment storage does not extract PDF or image content for search.
- Browser access tokens are stored in localStorage for development only;
  review production authentication before internet deployment.
- Queue redrive/DLQ, the crash window between DB commit and AWS SQS enqueue,
  production worker supervision, and broader observability remain follow-up.
- Source deletion confirmation is manual until adapters reconcile source state.
  Missing/equal source modification times require explicit version review.
- Original purge needs the worker; already issued download URLs can work up to
  10 minutes or object removal. Attachment final purge waits 11 minutes because
  upload URLs remain valid after completion. Real AWS version deletion/IAM,
  automatic policy/deletion journaling, backups and 30-day expiry are unverified
  deployment work. Old uploads without known Entry links cannot be safely purged
  by attribution. Restore must apply latest deletion ledger and current denies.
- Worker recovery uses RUNNING age (processing limit + 60 seconds) and owner locks;
  hard process termination is not a wall-clock timeout guarantee.

See `DECISIONS.md` and `CAPTURE.md` for enduring architecture and capture
constraints. Historical step-by-step status is available at the learning
baseline tag.

## Local validation incident

An initial integration script loaded DB settings before its test environment and
misdirected cleanup. The two affected local originals were restored byte-for-byte
from retained SeaweedFS data; one historical job start timestamp was restored
from its previous PostgreSQL row version. The script now verifies the disposable
DB/schema and cleans only object keys created by that invocation. Two September
artifact metadata rows have no verified local original; their availability before
this incident is unknown. No Entry bodies were changed by that script.
