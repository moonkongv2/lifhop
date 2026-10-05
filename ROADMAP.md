# lifhop Product Roadmap

Last revised: 2026-10-06

## Purpose and release boundary

Finish a private, daily-use release for the owner before planning a commercial
service. lifhop remains a learning project, with delivery organized around
observable product results. The learning baseline is `learning-complete-f3`;
`CURRENT.md` records actual implementation status, not planned capabilities.

Personal priorities, in order:

1. Recover past solutions, facts, and the reasons behind decisions.
2. Review records across a selected period.
3. Recover context when returning to a project.

Both technical work and ordinary life belong in the archive. Project or
repository membership must be optional. Seed evaluation questions include:

- 우리가 이전에 진행했던 모터 RPM 제어 최적화 문제에서 제어 주기 설정을 어떤 기준으로 했었지?
- 2026년 4월 오키나와 여행 시 이용했던 렌터카 업체와 선정 이유?

These are questions to evaluate, not evidence that the answers are present.
Distinguish a suggestion from an adopted decision, a considered vendor from
one actually used, and an inferred reason from an explicitly recorded reason.

## Agreed personal-release scope

| Area | Required scope |
| --- | --- |
| Existing inputs | Manual text, Markdown, and ChatGPT export ZIPs |
| Codex | CLI on one Mac; existing accessible history and new records; user/assistant messages, commands/results including tests, and recorded code changes |
| GitHub | Selected personal/organization public/private repositories; all available time periods within the declared branch/content scope |
| GitHub priority | Commit messages, relevant diffs, and key documents first because the owner usually commits directly; PRs, reviews, issues, and comments remain in scope |
| Recurring collection | Both Codex and GitHub: scheduled collection plus an explicit collect-now action |
| Access | Authenticated use from other devices and external networks; AWS preferred |
| Budget | At most USD 20/month for lifhop hosting, storage/backups, and AI API usage combined |
| External AI | Allow selected records; exclude particular repositories or records from external AI processing |
| History | Retain previously collected versions when sources change; preserve and label confirmed source deletions |
| lifhop deletion | Exclude deleted records immediately from retrieval/answers, purge associated content under a defined policy, and prevent automatic reimport |

Exclude secrets, binary payloads, and oversized outputs from Codex ingestion;
report omitted/truncated content. Whole-codebase semantic indexing is outside
this release. Relevant text diffs and selected documents still belong in scope.
Neither a commit diff nor a Codex answer alone proves a change was tested or
used in production.

### Planning defaults and implementation-time checks

These defaults are proposals, not additional user commitments:

- ChatGPT continues with manual ZIP import for this release. Automatic ChatGPT
  capture remains experimental and is not a completion prerequisite.
- Start with one selected GitHub repository, then backfill the remaining
  selected repositories. Inventory repository count, history size, branches,
  and credentials before estimating work or cost.
- Start commit coverage with the default branch and explicitly selected extra
  branches; display this scope. Full time coverage does not imply every branch,
  deleted ref, unreachable commit, or deleted source record can be recovered.
- Try Codex collection every 15 minutes while the Mac is awake and online,
  and GitHub collection hourly; make intervals configurable and measure them.
- Aim for daily backups, a recovery point within 24 hours, and a documented
  same-day restore. Confirm feasibility in the deployment slice.

Choose the AWS region, host size, credentials, model, and initial repository
list during their relevant slices. Validate source access and data volume
before promising completeness. Surface a failed feasibility check and revise
the affected slice; do not silently remove an agreed source or raise the budget.

## Delivery rules and existing foundation

Complete one user-verifiable slice at a time and show the result before the
next. Run relevant backend tests and frontend build/lint for behavior changes;
add a small CI workflow in Phase 1. Keep OpenAPI and generated frontend types
aligned. Use migrations and verify upgrade behavior for persistent changes.
Keep private samples, evaluation answers, credentials, and archives out of Git.

The existing backend supports authenticated user-owned Entry CRUD, attachments,
Markdown import, preserved import artifacts, and asynchronous ChatGPT ZIP
processing through ImportJob/SQS/a worker. ZIP and Capture API paths reuse
canonical normalization and external Entry upsert. Local S3 is the default;
SQS still uses the configured AWS queue. The frontend has login/list/detail.

Search, RAG, Codex/GitHub ingestion, source connections, revisions, external-AI
policies, deletion suppression, and scheduled sync are not implemented.
Provider enum values and `DevSessionPayload` do not constitute working adapters;
the current normalizer handles documents and conversations only. The ChatGPT
DOM extension is LIMITED GO and unreliable. Attachments do not provide PDF/OCR
search. Existing upsert replaces content without a freshness/completeness guard.

## Phase 1 — A usable archive

### 1.1 Create and manage a record in the browser

Reuse Entry APIs for creation, editing, and deletion with clear empty, loading,
validation, and error states. Preserve ownership boundaries. Add lightweight
automated backend/frontend checks using isolated test services.

**User check:** Sign in, write a note, find it in the list, open, edit, and
delete it; the displayed state follows the server result.

### 1.2 Import and inspect existing records

Provide Markdown and ChatGPT ZIP upload screens, job progress/results, useful
failures, and access to resulting Entries and protected raw-artifact downloads.
Provide a local queue path before demonstrating ZIP processing without AWS.
Bound upload size, extracted archive size, item count, and processing work.
Support the owner's approximately 500 MiB export, including numbered conversation
JSON shards, with bounded-memory file handling and saved processing progress.
Separate original-file and parsed-JSON budgets; verify interruption/restart with
committed Entries and progress kept consistent.
Expose item failures without logging private bodies; classify a job with zero
successful items and processing errors as failed rather than useful partial
success. Make repeated job delivery safe and provide a controlled retry path.

**User check:** Import valid and invalid samples, see counts/errors, retry a
failure, and reimport a conversation without creating another logical Entry.

### 1.3 Search and navigate records

Add owner-scoped keyword search, source/type/date filters, and pagination.
Test Korean and English phrases, exact names, numbers, units, and code terms.
Choose indexes using real relevance and query-plan evidence. Distinguish
source/event dates from ingestion dates; do not invent missing event dates.
Store timezone-aware timestamps and apply an explicit user timezone to date
ranges (initially Asia/Seoul); distinguish a date mentioned in text from the
date the record itself was written.
Search must work for travel notes with no repository or project association.

**Phase exit:** The owner can put records in lifhop and find them through the
browser without an LLM. This remains useful when AI is unavailable or excluded.

## Phase 2 — Integrate Codex and GitHub with trustworthy history

### 2.1 Verify acquisition and define coverage

Use small private samples to verify access before building full collectors:

- Codex: inventory installed CLI version and available active/archived history.
  Evaluate documented stored-thread reads first, including pagination and
  persisted command/change data. If a local-file adapter is needed, isolate
  version-dependent parsing and document supported formats. Never alter or
  migrate the source history to make ingestion work. Do not resume sessions,
  run models, or execute captured commands as part of collection.
- GitHub: verify selected repositories, organization authorization, least-
  privilege read access, branch scope, historical pagination, file/diff limits,
  and token expiry. Inventory the volume before full backfill. Never infer
  deletion from a permission failure, missing page, or exhausted rate limit.

**User check:** Inspect one historical Codex session and one GitHub commit with
their messages/results or diff, original identifiers, dates, and omissions.
Record available history, gaps, parser/API versions, and the selected method.

### 2.2 Add provenance, versions, deletion, and AI policy

Introduce only the persistent fields/models required by the two verified
adapters, through migrations. Apply the same rules to existing imports:

- Retain provider, stable source identity, source locator when available,
  observed/source times, content hash, parser version, and completeness state.
  Link normalized records to retained source material. Preserve the distinction
  between exact uploaded originals and sanitized/truncated acquisition payloads.
- Keep changed versions and an explicit current version. An unchanged replay
  creates neither duplicate Entries nor duplicate versions. Source freshness
  and completeness decide replacement; arrival order alone does not.
- Preserve message roles and order, command exit/result state, and relevant
  diff provenance. Treat unknown or partial results honestly. Import existing
  Entries as an initial observed version; do not manufacture earlier history.
- Keep imported source content read-only; personal annotations stay separate
  so a refresh cannot overwrite them. Manual Entries remain editable.
- Retain confirmed source deletions with a visible marker. If deletion cannot
  be verified, show unavailable/unknown. Define inclusion filters explicitly.
- A lifhop delete suppresses all versions and derived results immediately;
  retain a minimal owner/source identity tombstone to block reimport. Check it
  again before committing retries or in-flight jobs. Re-enable only through
  an explicit owner action. Define content purge and backup-expiry behavior,
  including shared ZIP artifacts and restore-time reapplication of deletions.
- Configure collection exclusions separately from external-AI permission.
  AWS storage permission does not imply AI-provider permission. New sources
  start with external AI disabled until explicitly enabled. Repository/record
  denial wins; reimports must not reset it. Prevent excluded content from
  reaching remote embeddings, rerankers, summaries, prompts, or telemetry.
  Derived content inherits its sources' restrictions; policy changes invalidate
  pending jobs and cached results. Already sent content cannot be unsent.

**User check:** Replay, edit, send an older/partial snapshot, delete at the
source, and delete in lifhop. Verify history/current state and no resurrection.
Use mocked egress checks to prove AI-excluded records are never transmitted.

### UI checkpoint before 2.3

At the owner's request, refine the frontend before adding more collectors.
Use a light, Notebook-inspired panel layout: recent Entries and concise archive cards;
top-level Search with a large query field, collapsible filters, and results;
record navigation, full-text reading, and personal annotations/history on detail.
Apply consistent spacing, typography, forms, and navigation to Import, Sources,
jobs, and login. Keep the English interface and support narrow screens.

**User check:** Browse/search, preserve search context through detail/new-tab/reload,
switch records, read full content, save an annotation,
inspect retained versions, and cancel deletion from the record actions menu.
Verify the layout at desktop and mobile widths before committing the UI checkpoint.

### 2.3 Backfill Codex CLI history

Build the read-only collector for the owner's Mac and the shared ingestion
path. Include all accessible selected historical sessions, messages, commands,
test results, and recorded changes. Filter before upload; do not upload entire
Codex configuration, credentials, environment dumps, or unrelated local files.
Provide preview/exclusions and bounded output handling. Preserve gaps when
source data has been compacted, truncated, removed, or was never recorded.

Checkpoint after durable ingestion. Handle partial writes, interruption,
resumed/forked sessions, archived history, and format changes without duplicate
messages or replacement by an incomplete snapshot. The cloud cannot discover
new local records while the Mac is asleep; show collector freshness separately.

**User check:** Find a past question, command result, and available code change
through lifhop. Interrupt/restart the backfill and confirm stable identities.

### UI checkpoint after 2.3 — Codex session reading

At the owner's request, group turn Entries into Codex session cards and a
paginated session reader before GitHub backfill. Preserve original message phase
and turn order where available. Show final/unknown messages in primary reading,
retain interim commentary in Work details, and allow optional commentary search.
Keep turn-level history, annotation, deletion suppression and AI permission.
Group before server pagination; search links focus the matched turn in its session.
Unknown legacy metadata stays explicit and v1 collector replay remains compatible.

**User check:** Browse a 25-turn synthetic session, expand work details, search
with/without commentary, open the matching later-page turn and return to Search.
Review new personal preview metadata before explicit apply.

### 2.4 Backfill GitHub history

Implement in two reviewable increments: commits/key documents first, then
PRs/reviews/issues/comments. Both increments belong to the personal release.
Use repository identity plus source object identity; deduplicate commits
across selected branches. Paginate the full accessible period and checkpoint
backfill progress. Handle empty repositories, renames, rate limits, access
revocation, unavailable patches, binary/large files, and ref changes explicitly.

Preserve commit messages, parents, authorship/times, relevant text diffs and
file paths, and source links. Choose a visible document-path allowlist. Use
available commit history for relevant document changes rather than claiming
the current README is a historical snapshot. PR/issue history means accessible
objects and discussions; earlier edits not exposed by the source remain gaps.
Current records plus later collected versions cannot reconstruct every past edit.

**User check:** Find an old direct commit and its documented rationale; open
its relevant diff/document and any associated discussion. Re-run without
duplicates. In a repository with no PRs/issues, report zero rather than failure.

**Phase exit:** ChatGPT, Codex, and GitHub records can be searched together,
filtered by source/time, and inspected with provenance and coverage. Every
selected source has a visible backfill result, including gaps and failures.

### UI checkpoint between 2.4A and 2.4B — GitHub repository browsing

Group retained GitHub Entries by numeric repository identity for browsing while
keeping commit/document identities for search and evidence. Provide chronological
commit lists and path-grouped historical document snapshots with page-preserving
reader navigation. Label retained counts and document freshness accurately.
Verify this checkpoint before collecting discussions in 2.4B.

**User check:** Open a repository card, inspect a past commit/diff and document
snapshot, return to the same page, and reach that repository from a search hit.

## Phase 3 — Answers grounded in records

### 3.1 Establish a private evaluation set

Start with about 20 real questions and expected supporting passages, including
the two seed questions, Korean/English, non-project life records, cross-source
evidence, date ranges, changed decisions, and insufficient evidence. Include
AI-excluded records and sources with known collection gaps. Use synthetic or
redacted fixtures in Git and keep the real evaluation set private.

Record lexical retrieval results before adding semantic retrieval. Measure
whether supporting records are found, whether each material claim has matching
evidence, and whether uncertainty is appropriate. Fix acceptance targets before
comparing implementations; never use invented answers as ground truth.

### 3.2 Index text within policy and cost limits

Split searchable text into passages anchored to Entry versions and source
locations. Add embeddings/pgvector if evaluation shows a retrieval benefit;
retain exact keyword search. Estimate tokens and cost before historical
embedding backfill, batch within the monthly allowance, and support resumption.
Avoid embedding every large tool log or diff by default.

Synchronize create/update/delete/reimport and policy changes. Jobs reference a
specific content/policy version; stale jobs cannot republish old content.
External-AI-excluded records retain local keyword search and direct viewing;
local semantic models are optional only if feasible within memory/cost limits.

**User check:** New or edited records become findable; old/deleted passages
stop appearing as current evidence. Excluded content never reaches an AI API.

### 3.3 Ask questions and review a period

Provide a question page with source/date filters, bounded source context,
versioned passage citations, and links to full records. Retrieve within owner
and AI policy boundaries. Treat imported instructions as untrusted source text.
Bound request size, time, output, concurrency, and retries. Show timeout,
insufficient evidence, policy exclusion, and budget exhaustion distinctly.

Support a basic date-range retrospective with cited events/decisions; distinguish
source-event time from collection time and proposals from completed work. Mark
coverage gaps and disclose when only part of a large period was examined.
Use relevant versions for historical questions, current versions by default,
and show if a cited source subsequently changed or was deleted in lifhop.
Project-resume questions use these same flows; a separate briefing dashboard
and automatic project classification are deferred.

**Phase exit:** Review the evaluation set, including answers combining sources,
and inspect citations. Record failures, latency, and per-query cost. No observed
ownership leak, prohibited AI transmission, or deleted-content resurfacing is
acceptable for release. Report unsupported conclusions as failures to fix.

## Phase 4 — Scheduled collection from both new sources

### 4.1 Codex and GitHub incremental collection

Reuse backfill adapters with configurable schedules and collect-now controls.
Codex runs on the Mac, uploads over an authenticated connection, and catches up
after wake/reconnect; cloud reading of already uploaded data remains available.
GitHub polling runs independently of the Mac. Provide scoped/revocable collector
credentials, pause/disconnect, selected-source controls, and persisted cursors.
Do not rely on timestamps alone to discover newly reachable old commits.

Prevent overlapping jobs from racing. Resume after failure; acknowledge only
after durable writes. Reconcile changed refs and mutable discussions/documents
without re-reading all history on every poll. Preserve unavailable-source status
and do not treat lost authorization as deletion. Keep historical backfill and
incremental progress separately visible so one cannot mask failure of the other.

### 4.2 Make failures recoverable

Show per-source last success, collector heartbeat where relevant, history
coverage, indexing state, partial/error counts, and next attempt. Bound retries,
isolate persistent failures, and support controlled retries. Address DB-commit
followed by queue-send failure, stuck jobs, worker restarts, and duplicate
delivery using the smallest adequate recovery mechanism. Choose reconciliation,
outbox, or queue redrive based on verified failures; document the decision.

**Phase exit:** New Codex and GitHub records arrive on their schedules and via
collect-now. Demonstrate offline/wake, expired authorization, interrupted work,
overlapping attempts, duplicate delivery, and recovery without data regression.

## Phase 5 — Private daily-use release on AWS

### 5.1 Prove a deployment fits the total budget

Prepare a reproducible, measured proposal before provisioning. Evaluate a small
single-host deployment for the web app, API, PostgreSQL, and bounded workers;
compare EC2/Lightsail based on region, memory, credentials, storage, and total
cost. The README's ECS/RDS/ALB diagram is not a required deployment inventory.
Preserve role-based AWS access where supported; resolve any host/identity
limitation explicitly rather than embedding permanent AWS keys. Avoid adding
managed databases, load balancers, NAT, or always-on extra services by default.

Budget includes compute, disk, public IP/network charges, retained versions,
raw objects, requests, backups, logs, queue use, AI inference/embeddings,
applicable taxes, and DNS/domain cost if introduced. Do not rely on temporary
credits or free trials. Existing unrelated subscriptions are outside lifhop's
incremental budget; model API use must be budgeted explicitly.

An initial envelope to test is USD 12 compute + 2 storage/backup/operations +
3 AI + 3 contingency/tax = 20. This is a planning allocation, not a verified
quote. Full-history storage and indexing may require staged backfill. Measure
corpus volume, disk, memory, and cost before choosing the host and model.
If the envelope fails, report the tradeoff; do not silently raise the cap,
discard promised history, or claim completion with selected sources missing.

Enforce application-side token/storage/job limits and reserve estimated cost
before concurrent paid work. Pause optional paid work before exhausting its
allowance, preserving keyword search and stored records. Add billing alerts
with headroom; alerts are delayed and do not impose a hard cloud spending cap.
Do not automatically scale resources. Document what keeps costing money when
jobs stop and how the owner stops the deployment safely.

### 5.2 Secure access, backup, and recovery

Use HTTPS from external networks and a usable browser layout on another device.
Restrict account provisioning to the owner; retain user ownership checks for
all endpoints and workers. Replace development localStorage token handling
with a reviewed production session flow, including logout/expiry and CSRF
protection where applicable. Keep database/storage private, protect connector
credentials, and avoid private bodies/tokens in logs. Collection exclusions
must operate before uploading local sensitive data to AWS.

Automate deployment, migrations, worker restart, bounded logs, and backups.
Back up the database, required source objects, policies, and deletion tombstones
consistently to a separate recoverable location. Perform an isolated restore,
verify content and policies, and reapply deletions newer than the backup before
resuming service. Define backup expiry and shared-artifact purge so keeping a
ZIP cannot silently retain content the owner explicitly deleted in lifhop.

### 5.3 Personal-release acceptance

Complete an initial seven-day daily-use trial (adjust if it misses important
usage), with all of the following checked:

- Historical ChatGPT, Codex, and selected GitHub records are available with
  declared coverage; no mandatory project association excludes life records.
- Past-solution questions and a date-range retrospective have inspectable
  evidence, including at least one answer requiring multiple sources.
- Both new collectors update automatically and on demand; failure/recovery and
  Mac-offline status are visible and do not corrupt stored history.
- Version retention, source deletion markers, lifhop deletion suppression,
  and external-AI exclusions pass regression checks.
- Another device on an external network can use the app while the Mac is off.
- A deployment/restart and a backup restore preserve data and access policy.
- Observed usage, current prices, and remaining monthly obligations project
  total cost at or below USD 20; initial backfill also stays within allowance.
  Monitor the first full billing month; a short trial is not proof of a hard cap.

**Release boundary:** Mark the private release complete only after these
checks. Record measured limits, remaining gaps, and operating instructions in
`CURRENT.md` and deployment documentation.

## Next stage — Commercial service and later improvements

After private-release acceptance, use actual usage to write a separate plan
for customer validation, onboarding/account recovery, multi-user isolation and
capacity validation, pricing/billing, support, organization permissions,
provider launch requirements, and data-handling policies. Personal deployment
does not by itself establish readiness to accept other users' private data.

Additional providers, mobile capture, PDF/OCR extraction, automatic ChatGPT DOM
capture, whole-codebase indexing, advanced reranking, automatic decision graphs,
and dedicated project briefings are deferred. Bring one forward only when an
observed personal-release limitation justifies changing this roadmap.

## Feasibility references

Checked 2026-09-30; recheck when implementing. These establish candidates and
constraints, not verified integration with the owner's private data.

- [Codex App Server](https://learn.chatgpt.com/docs/app-server) documents stored
  thread listing/reading and paginated history; some pagination methods are
  experimental. The locally installed CLI reports `0.158.0`; test compatibility
  and persisted content coverage before choosing an adapter.
- [GitHub commits API](https://docs.github.com/en/rest/commits/commits) supports
  paginated commit reads and a branch/SHA selector; the default branch is the
  default scope. Access credentials and complete pagination need validation.
- [AWS Lightsail bundles](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html)
  lists an IPv4 Linux 2 GB bundle at USD 12/month. That price does not establish
  workload fit or total cost, and Lightsail is not yet the selected host.
- [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
  documents notification delay and possible spending beyond alert thresholds.
