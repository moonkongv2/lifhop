# lifhop Current Status

Last updated: 2026-10-01

## Current product slice

Phase 1.2 in `ROADMAP.md` — import and inspect Markdown/ChatGPT ZIP records.
Implementation, local checks, and owner browser verification are complete.
Phase 1.1 was also confirmed by the owner. Setup/checks: `frontend/README.md`.

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
retention, deletion suppression, and repository/record-level external-AI
exclusions are planned requirements, not implemented capabilities.

## What works now

- FastAPI/PostgreSQL backend with authentication and user-owned Entry CRUD.
- Browser Markdown/ChatGPT ZIP upload, job polling/history, final counts,
  sanitized item errors, paginated result Entries, retry, and protected originals.
- Local SeaweedFS storage and PostgreSQL ImportJob queue are defaults; explicit
  AWS S3/SQS modes remain available. Worker startup is separate from the API.
- Original artifact links on newly imported Entries; persisted job result IDs.
- Upload/archive/item/node/time limits; at most 3 processing attempts by default.
  Row/owner locks, item savepoints, stale-job recovery, completed-delivery no-op,
  and bounded infrastructure redelivery.
- S3-backed Entry attachments.
- Local S3-compatible storage is the default for development; tests block
  unexpected AWS client creation.
- React login, Entry list/detail, and note creation/editing/deletion using
  authenticated Entry APIs and server-result cache updates.
- Empty/loading/error states, draft-preserving save errors, title validation,
  deletion confirmation, and account-switch cache clearing.
- Disposable PostgreSQL tests use real migrations in fresh schemas. Local
  checks: 117 backend tests and 19 frontend tests pass; frontend lint/build pass.
- Actual local S3 upload/download and local queue/worker checks passed with
  synthetic records in an isolated DB schema; synthetic objects were removed.
- GitHub Actions checks for migrations, backend/frontend tests, generated API
  types, and frontend lint/build (remote workflow execution pending).

The learning-through-F3 baseline is marked by Git tag
`learning-complete-f3` at `187b651f9422e901059f238c334d0e5fa885b4f4`.
The project remains a learning project; delivery from here follows the
user-verifiable product slices in `ROADMAP.md`.

## Next

1. Implement Phase 1.3: owner-scoped keyword search, source/type/date filters,
   and pagination.
2. Verify Korean/English queries and date semantics before owner review.
3. Follow the sequence: archive/search → Codex/GitHub history → evidence-based
   answers/retrospectives → scheduled collectors → private AWS release.

## Known limitations

- Owner confirmed Phase 1.2 in the browser. Remote CI execution remains
  pending; frontend automated tests stub API.
- Entry list and recent job history show the latest 20 records/jobs. Job results
  have pagination. Archive-wide search/pagination and answers are not available.
- Counts/item errors are final results; RUNNING does not expose per-item progress.
- Earlier imported Entries/jobs have no reconstructed artifact/result links.
  Markdown reupload creates another Entry; ChatGPT reupload uses stable IDs.
- Codex/GitHub adapters, retained Entry versions, deletion tombstones, and
  external-AI policies are not implemented. Source access/history size and
  deployment cost still require verification; enum values are not integrations.
- The ChatGPT Web extension is experimental and currently unreliable on
  affected pages. Do not use it as the product's dependable capture path.
- Attachment storage does not extract PDF or image content for search.
- Browser access tokens are stored in localStorage for development only;
  review production authentication before internet deployment.
- Queue redrive/DLQ, the crash window between DB commit and AWS SQS enqueue,
  production worker supervision, and broader observability remain follow-up.
- Reimport still replaces current conversation content without version/freshness
  guards. New-job reimport can resurrect a deleted source; tombstones and artifact
  purge rules remain Phase 2.2. Same completed-job redelivery skips processing.
- Worker recovery uses RUNNING age (processing limit + 60 seconds) and locks;
  hard process termination is not a wall-clock timeout guarantee.

See `DECISIONS.md` and `CAPTURE.md` for enduring architecture and capture
constraints. Historical step-by-step status is available at the learning
baseline tag.
