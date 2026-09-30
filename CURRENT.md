# lifhop Current Status

Last updated: 2026-09-30

## Current product slice

Phase 1.1 in `ROADMAP.md` — create and manage a text Entry in the browser.
Implementation has not started.

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
- React login, Entry list, and Entry detail with generated API types.
- Existing backend tests and frontend build/lint commands.

The learning-through-F3 baseline is marked by Git tag
`learning-complete-f3` at `187b651f9422e901059f238c334d0e5fa885b4f4`.
The project remains a learning project; delivery from here follows the
user-verifiable product slices in `ROADMAP.md`.

## Next

1. Implement Phase 1.1: create, edit, and delete a text Entry in the browser.
2. Show the completed browser flow and verify relevant API behavior,
   frontend build/lint, and tests.
3. Continue with Phase 1.2 browser imports after Phase 1.1 is reviewed.
4. Follow the revised sequence: archive/search → Codex/GitHub history →
   evidence-based answers/retrospectives → both scheduled collectors → private
   AWS release. See `ROADMAP.md` for defaults and completion checks.

## Known limitations

- The frontend cannot yet create, edit, delete, import, search, or ask
  questions about Entries.
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
