# lifhop Current Status

Last updated: 2026-09-29

## Current product slice

Phase 1.1 in `ROADMAP.md` — create and manage a text Entry in the browser.
Implementation has not started.

## What works now

- FastAPI/PostgreSQL backend with authentication and user-owned Entry CRUD.
- Markdown import; ChatGPT ZIP import through S3, ImportJob, SQS, and a worker.
- Original import artifact preservation and protected download.
- S3-backed Entry attachments.
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

## Known limitations

- The frontend cannot yet create, edit, delete, import, search, or ask
  questions about Entries.
- The ChatGPT Web extension is experimental and currently unreliable on
  affected pages. Do not use it as the product's dependable capture path.
- Attachment storage does not extract PDF or image content for search.
- Browser access tokens are stored in localStorage for development only;
  review production authentication before internet deployment.
- Queue redrive/DLQ, commit-to-SQS failure handling, production worker
  supervision, and broader observability remain operational follow-up.

See `DECISIONS.md` and `CAPTURE.md` for enduring architecture and capture
constraints. Historical step-by-step status is available at the learning
baseline tag.
