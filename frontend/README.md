# lifhop frontend

React + TypeScript + Vite. The browser supports login, Entry list/detail, and
creating, editing, and deleting notes through the authenticated API. It also
supports Markdown/ChatGPT ZIP uploads, job results/retry, and protected originals.
New records use type `NOTE`; editing preserves the existing type and event date.

## Run locally

From the repository root, start PostgreSQL and apply migrations:

```bash
docker compose up -d db seaweedfs
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

The backend needs `.env` values for `DATABASE_URL`, `JWT_SECRET_KEY`,
and `AWS_REGION`. Note CRUD needs PostgreSQL; imports also need SeaweedFS and
the worker. Local queue/storage do not require AWS credentials or an SQS URL.
A development configuration can use:

```dotenv
DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop
JWT_SECRET_KEY=replace-with-a-local-random-secret
AWS_REGION=ap-northeast-2
S3_MODE=local
QUEUE_MODE=local
```

Keep `.env` out of Git. Restart the API/worker after changing settings. In
another terminal from the repository root, run the ZIP worker:

```bash
.venv/bin/python -m app.workers.import_worker
```

The worker polls durable ImportJob rows in local mode. Pending jobs survive API
and worker restarts. To intentionally use AWS, set `QUEUE_MODE=aws` and configure
`SQS_IMPORT_QUEUE_URL`, region, and credentials separately from `S3_MODE`.

Start the frontend in another terminal:

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

## Phase 1.2 user check

1. Sign in at http://localhost:5173 and open 가져오기.
2. Select Markdown, upload a UTF-8 `.md` file, and open the result Entry. Select
   원본 다운로드 준비 → 원본 파일 다운로드 and compare it with the uploaded file.
   Original download is also available on that Entry's detail page.
3. Generate a synthetic ChatGPT ZIP from the checked-in fixture:

   ```bash
   .venv/bin/python -m zipfile -c /private/tmp/lifhop-chatgpt-sample.zip tests/fixtures/chatgpt/conversations.json
   ```

   Select ChatGPT ZIP and upload it. The job page polls every 2 seconds; expect
   완료, 2 successes, 0 failures, 2 linked conversation Entries, and the original
   ZIP download. Counts/errors become visible when processing finishes.
4. Upload the same ZIP again. It creates another job/original artifact while
   keeping the same two logical conversation Entries. The latest artifact link
   on each Entry changes to the latest upload. Reload 가져오기 to revisit jobs.
5. Upload a non-ZIP text file named `.zip`. Expect 실패 with a useful error.
   작업 재시도 processes the same preserved file and fails again; fixing the
   file requires a new upload. Empty/non-UTF-8 Markdown is rejected before storage.
6. With the worker stopped, a ZIP remains 대기 중. Start the worker to finish it.
   If storage/DB processing fails transiently, automatic attempts are bounded.
   Once FAILED/PARTIAL, the owner can explicitly retry within the remaining
   attempt budget. A duplicate retry while pending/running returns a conflict.

No actual AWS request is needed for these checks with both local modes selected.

## Import limits and retry rules

| Environment setting | Default |
| --- | --- |
| `IMPORT_MAX_UPLOAD_BYTES` | 25 MiB per file |
| `IMPORT_MAX_EXTRACTED_BYTES` | 100 MiB total declared archive size/read JSON |
| `IMPORT_MAX_ARCHIVE_FILES` | 5,000 archive members |
| `IMPORT_MAX_ITEMS` | 2,000 conversations |
| `IMPORT_MAX_NODES_PER_ITEM` | 20,000 message nodes |
| `IMPORT_MAX_TOTAL_NODES` | 200,000 message nodes |
| `IMPORT_MAX_SECONDS` | 120 seconds of processing budget |
| `IMPORT_MAX_ATTEMPTS` | 3 processing attempts, automatic + manual combined |

Multipart request input is limited to the file budget plus 64 KiB overhead.
Archive members are read in memory; no ZIP paths are extracted to the filesystem.
Cycles/missing branch links are rejected. Each item uses a DB savepoint, so an
invalid database value does not abort otherwise valid items. Error output uses
item position and fixed reasons; private content and exception bodies are not
logged. Zero successful items with errors is FAILED, rather than PARTIAL.

A completed/partial/failed job delivery returns its recorded result without
reprocessing. Explicit retry switches FAILED/PARTIAL back to PENDING. Processing
is serialized per owner, with the job locked until its final transaction commits.
A crashed RUNNING job can be reclaimed after `IMPORT_MAX_SECONDS + 60` seconds;
live jobs remain protected by their row lock. Byte/node/query/deadline limits
bound work, but there is no subprocess watchdog that forcibly kills a parser
at exactly the deadline. Progress is status-level; per-item counts are final.

## Automated checks

Frontend tests render the real pages with a separate in-memory API stub. They
cover the note lifecycle, server-driven cache updates, validation, cancellation,
loading/failures, retry, missing records, and unauthenticated navigation. Import
page tests cover multipart upload, polling, item errors, cache refresh, original
download preparation, and resuming jobs by URL.
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
port 55433 and temporary storage. Tests run real Alembic migrations in fresh
per-run schemas, then remove those schemas, and require a
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
Job history also shows the latest 20 jobs; each job's result Entries have
pagination. Earlier Entries/jobs do not have reconstructed artifact/result
links. Markdown reupload creates a new Entry. Tokens remain in localStorage
for development;
production authentication and imported-record version/deletion policies are
later roadmap work. The owner confirmed the Phase 1.1 browser flow. GitHub
Actions execution
remains to be checked separately from local automated tests. The owner
confirmed the Phase 1.2 browser flow. Automated browser connection failed in
the implementation session. Real local S3/queue/worker integration passed using
synthetic inputs in an isolated DB schema, including original downloads,
reimport, failed ZIP, and retry. Temporary inputs/storage were cleaned up.

Reimport continues to replace current ChatGPT content. Retained versions,
freshness checks, deletion suppression, and original/artifact purge policies
are Phase 2.2. Deleting an Entry currently leaves its preserved original file;
a new import job can recreate a deleted conversation. Do not treat this as the
final archive deletion behavior.
