# lifhop Current Status

Last updated: 2026-10-01

## Current product slice

Phase 1.1 in `ROADMAP.md` — create and manage a text Entry in the browser.
Implementation, local automated checks, and owner browser verification
are complete. See `frontend/README.md` for setup and the user check.

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
- Markdown import; ChatGPT ZIP import through S3, ImportJob, SQS, and a worker.
- Original import artifact preservation and protected download.
- S3-backed Entry attachments.
- Local S3-compatible storage is the default for development; tests block
  unexpected AWS client creation.
- React login, Entry list/detail, and note creation/editing/deletion using
  authenticated Entry APIs and server-result cache updates.
- Empty/loading/error states, draft-preserving save errors, title validation,
  deletion confirmation, and account-switch cache clearing.
- Disposable PostgreSQL test service; backend ownership/validation/lifecycle
  tests and frontend page tests. Local checks: 94 backend tests and 10 frontend
  tests pass; frontend lint/build pass.
- GitHub Actions checks for migrations, backend/frontend tests, generated API
  types, and frontend lint/build (remote workflow execution pending).

The learning-through-F3 baseline is marked by Git tag
`learning-complete-f3` at `187b651f9422e901059f238c334d0e5fa885b4f4`.
The project remains a learning project; delivery from here follows the
user-verifiable product slices in `ROADMAP.md`.

## Next

1. Implement Phase 1.2: browser Markdown/ChatGPT ZIP imports, job results,
   protected original downloads, and a local queue path.
2. Verify limits, failures, retry, and repeated delivery before owner review.
3. Follow the sequence: archive/search → Codex/GitHub history → evidence-based
   answers/retrospectives → scheduled collectors → private AWS release.

## Known limitations

- Owner confirmed the browser flow. Remote CI execution remains pending;
  frontend automated tests use an isolated in-memory API stub.
- The frontend cannot yet import, search, or ask questions about Entries.
  The list displays only the latest 20 records; pagination is Phase 1.3.
- Codex/GitHub adapters, retained Entry versions, deletion tombstones, and
  external-AI policies are not implemented. Source access/history size and
  deployment cost still require verification; enum values are not integrations.
- The ChatGPT Web extension is experimental and currently unreliable on
  affected pages. Do not use it as the product's dependable capture path.
- Attachment storage does not extract PDF or image content for search.
- Browser access tokens are stored in localStorage for development only;
  review production authentication before internet deployment.
- Queue redrive/DLQ, commit-to-SQS failure handling, production worker
  supervision, and broader observability remain operational follow-up.
- SQS still points to the configured AWS queue. Local ZIP processing needs a
  local queue path before Phase 1.2 can be demonstrated without AWS requests.

See `DECISIONS.md` and `CAPTURE.md` for enduring architecture and capture
constraints. Historical step-by-step status is available at the learning
baseline tag.
