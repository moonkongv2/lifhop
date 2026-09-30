# lifhop frontend

React + TypeScript + Vite. The browser supports login, Entry list/detail, and
creating, editing, and deleting notes through the existing authenticated API.
New records use type `NOTE`; editing preserves the existing type and event date.

## Run locally

From the repository root, start PostgreSQL and apply migrations:

```bash
docker compose up -d db
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

The backend needs `.env` values for `DATABASE_URL`, `JWT_SECRET_KEY`,
`AWS_REGION`, and `SQS_IMPORT_QUEUE_URL`. For local note CRUD, no S3/SQS service
or AWS credential is required. A development configuration can use:

```dotenv
DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop
JWT_SECRET_KEY=replace-with-a-local-random-secret
AWS_REGION=ap-northeast-2
SQS_IMPORT_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/000000000000/unused
S3_MODE=local
```

Keep `.env` out of Git. Start the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to http://localhost:8000.
If no account exists, register using `POST /auth/register` in
http://localhost:8000/docs, then sign in through the browser.

## Phase 1.1 user check

1. Sign in and open Entries → 새 노트 작성.
2. Enter a title and multiline content, save, and check the detail and list.
3. Open the note, select 수정, change the title/content, and save. Both views
   should show the saved values, including after reloading.
4. Select 삭제. 취소 keeps the note; 삭제 확인 returns to the list and removes it.
5. A whitespace-only title should show validation. If the API becomes
   unavailable, a failed save keeps the draft; restart the API and retry.

## Automated checks

Frontend tests render the real pages with a separate in-memory API stub. They
cover the note lifecycle, server-driven cache updates, validation, cancellation,
loading/failures, retry, missing records, and unauthenticated navigation.
They do not establish a real browser-to-PostgreSQL integration result.

```bash
cd frontend
npm test
npm run lint
npm run build
```

Run backend tests against disposable PostgreSQL separately from development:

```bash
docker compose -f compose.test.yaml up -d --wait
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@127.0.0.1:55433/lifhop_test DATABASE_URL=postgresql+psycopg://lifhop:lifhop@127.0.0.1:55433/lifhop_test .venv/bin/pytest
# Stop only the test service; leave development services running.
docker compose -f compose.test.yaml stop test-db
```

Run these backend commands from the repository root. The test service uses
port 55433 and temporary storage. Tests create/drop tables and require a
`TEST_DATABASE_URL` database name ending in `_test`. AWS boundaries are mocked.
The GitHub Actions workflow also uses an isolated PostgreSQL service and checks
migrations, the backend suite, generated API types, frontend tests, lint/build.

To regenerate types while FastAPI is running:

```bash
cd frontend
npm run generate:api
```

## Current limits

The list displays the API's latest 20 records; pagination/search is Phase 1.3.
Browser import is Phase 1.2. Tokens remain in localStorage for development;
production authentication and imported-record version/deletion policies are
later roadmap work. The owner confirmed the Phase 1.1 browser flow. GitHub Actions execution
remains to be checked separately from local automated tests.
