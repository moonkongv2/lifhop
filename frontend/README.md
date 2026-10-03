# lifhop frontend

React + TypeScript + Vite. The browser supports login, Entry list/detail, and
creating, editing, and deleting notes through the authenticated API. It also
supports Markdown/ChatGPT ZIP uploads, job results/retry, and protected originals.
The interface is in English; user content keeps its original language. Dates use
English formatting in the Asia/Seoul timezone.
Entries shows recent records; Search has phrase search, source/type/date filters,
and pagination. Both pages show 20 records at a time. Search applies on submission;
its initial screen makes no search request. Filter-only searches are supported.
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

1. Sign in and open Entries → New note.
2. Enter a title and multiline content, save, and check the detail and list.
3. Open the note, select Edit, change the title/content, and save. Both views
   should show the saved values, including after reloading.
4. Open the three-dot Record actions menu and select Delete. Cancel keeps the note;
   Confirm delete returns to the list and removes it.
5. A whitespace-only title should show validation. If the API becomes
   unavailable, a failed save keeps the draft; restart the API and retry.

## UI checkpoint user check

Use the local API/frontend commands above. No new migration or package is required
for this UI update. Imports and original-file purge still need the storage/worker.

1. Open http://localhost:5173/entries. Expect recent cards with short previews,
   page controls, and New note. The top menu is Entries · Search · Import · Sources.
2. Open http://localhost:5173/search. Expect a large search field, collapsible
   Filters, and an initial prompt. Submit a phrase with Enter or Search. Reset
   returns to the initial prompt. With an empty query, choose Source or another
   filter and submit: matching records should still appear.
3. Apply filters, open a result, and return with Back to search: conditions and
   page should remain. Open a result link in a new tab and reload its detail:
   Back to search should keep the same conditions. Search remains the active menu.
   An old `/entries?q=...` URL should redirect to `/search?q=...`.
4. On detail, expect record navigation on the left, the full text in the center,
   and Notes & history on the right. Switch records using the left panel.
   A manual record has Edit; imported source content remains read-only.
5. Save a personal annotation, then open View history and provenance and inspect
   a retained version. The main reader should continue showing the current version.
   The existing synthetic demo at `/entries/1270` can be used while available;
   see [HISTORY.md](../HISTORY.md) for generating another disposable demo.
6. Open the three-dot Record actions menu → Delete → Cancel. The confirmation
   should appear near the top of the reader; Cancel should keep the record.
7. Open Import, a job, Sources, New note, and Login. Forms/buttons should use the
   same design. Narrow the browser to about 390 px: panels should stack vertically
   with no page-wide horizontal scroll. The record sidebar scrolls within its panel;
   at very narrow widths the top menu can scroll horizontally inside its own row.

Owner visual review is pending. Local Chromium verification uses synthetic API
responses, not the development DB. Screenshots are kept outside Git under
`.local/verification/search-ui/`. Safari/Firefox and actual devices are unverified.

### English controls and account state

1. Reload http://localhost:5173/search and open Filters. Start/End date should
   show `YYYY-MM-DD`; calendar months, weekdays, Today and Clear should be English.
   Select a date and submit, or type a date. Invalid dates show an English error.
2. Open Import. Markdown source modification uses the same English calendar and
   a `HH:mm` text field (24-hour time, device timezone). File controls show
   Choose file / No file selected; a selected filename keeps its original language.
3. After login, the top-right action should be Logout. Click it: expect Login,
   the login page, and cleared account data. Reload: stay logged out. A second
   open tab should also move to Login when the first tab logs out.
4. Submit an empty login form: expect English validation. An API response with
   an expired/invalid token should return to Login with an English expiry notice.

The source audit found no remaining Korean application labels. Korean-locale
Chromium checks cover these controls and session flows with synthetic API
responses; screenshots are under `.local/verification/english-session-ui/`.
Operating-system file pickers and browser-owned menus can still use the device
language. Imported content is preserved as written.

## Phase 1.2 user check

1. Sign in at http://localhost:5173 and open Import.
2. Select Markdown, upload a UTF-8 `.md` file, and open the result Entry. Select
   Prepare original download → Download original file and compare it with the uploaded file.
   Original download is also available on that Entry's detail page.
3. Generate a synthetic ChatGPT ZIP from the checked-in fixture:

   ```bash
   .venv/bin/python -m zipfile -c /private/tmp/lifhop-chatgpt-sample.zip tests/fixtures/chatgpt/conversations.json
   ```

   Select ChatGPT ZIP and upload it. The job page polls every 2 seconds; expect
   Completed, 2 successes, 0 failures, 2 linked conversation Entries, and the original
   ZIP download. Counts/errors update after each saved batch.
4. Upload the same ZIP again. It creates another job/original artifact while
   keeping the same two logical conversation Entries. The latest artifact link
   on each Entry changes to the latest upload. Reload Import to revisit jobs.
5. Upload a non-ZIP text file named `.zip`. Expect Failed with a useful error.
   Retry job processes the same preserved file and fails again; fixing the
   file requires a new upload. Empty/non-UTF-8 Markdown is rejected before storage.
6. With the worker stopped, a ZIP remains Pending. Start the worker to finish it.
   If storage/DB processing fails transiently, automatic attempts are bounded.
   Once FAILED/PARTIAL, the owner can explicitly retry within the remaining
   attempt budget. A duplicate retry while pending/running returns a conflict.

No actual AWS request is needed for these checks with both local modes selected.

## Phase 1.3 user check

Apply the new migration and restart the API using the local commands above.
The migration adds a pagination index and labels old, artifact-linked Markdown
records. It does not infer the source of older records without evidence.
Search/note checks need PostgreSQL and the API; storage/worker are required only
if importing additional samples.

1. Open http://localhost:5173/entries and create a note titled `제주 여행` with
   content `Alice Kim / 120 RPM / 3.5 km / use_state / 100%`.
2. Open Search and submit each phrase or code term, including `alice kim`. Expect the note to
   appear. `%` and `_` are literal characters. Search covers title/content with
   case-insensitive substring matching; it does not split words or infer synonyms.
   Exact titles rank first, title substrings next, body matches next; ties use
   newest registration and descending ID. No project/repository is required.
3. Combine Source=Manual and Type=Note. Markdown/ChatGPT records should disappear.
   Switch to Markdown/Document or ChatGPT/Conversation to find the corresponding imports.
   Unprovable older sources display Unknown source, even when they look like a note.
4. Select Date field=Added and today's date for both bounds. The note appears.
   Switch to Source/event date with the same range: a note without `event_at` is
   excluded. ChatGPT's source date is its conversation creation timestamp.
   Markdown has no source date. A date written in text does not set `event_at`.
   Date bounds use Asia/Seoul, include both selected days, and dates are displayed
   in that timezone regardless of the browser's timezone.
5. With more than 20 matching records, use Next page/Previous page. The total and
   page change while filters remain selected. Reload or open the Search URL in
   another tab, open a detail then Back to search, and confirm the filters/page survive.
   New filters return to page one; Reset returns to the initial Search prompt.
   Deleting the final record on the
   last page moves back to the last remaining page.
6. Search an absent phrase: expect No entries match your search. Reversed dates
   show validation without applying. API failures show a retry button.

Phase 1.3 owner browser verification is pending. Automated API tests use actual
isolated PostgreSQL; frontend tests render pages with mocked API responses.

## Import limits and retry rules

| Environment setting | Default |
| --- | --- |
| `IMPORT_MAX_UPLOAD_BYTES` | 25 MiB per Markdown file |
| `IMPORT_MAX_ZIP_BYTES` | 1 GiB per ZIP file |
| `IMPORT_MAX_EXTRACTED_BYTES` | 1 GiB total declared uncompressed ZIP size |
| `IMPORT_MAX_JSON_BYTES` | 256 MiB total conversation JSON |
| `IMPORT_MAX_RECORD_BYTES` | 16 MiB per conversation JSON record |
| `IMPORT_BATCH_SIZE` | 25 items per saved batch |
| `IMPORT_MAX_ARCHIVE_FILES` | 5,000 archive members |
| `IMPORT_MAX_ITEMS` | 2,000 conversations |
| `IMPORT_MAX_NODES_PER_ITEM` | 20,000 message nodes |
| `IMPORT_MAX_TOTAL_NODES` | 200,000 message nodes |
| `IMPORT_MAX_SECONDS` | 120 seconds of processing budget |
| `IMPORT_MAX_ATTEMPTS` | 3 processing attempts, automatic + manual combined |

Multipart request input is limited to the selected file budget plus 64 KiB
of overhead. Uploaded ZIPs remain spooled files and are streamed to object storage.
The worker downloads to an automatically cleaned temporary file. Reserve temporary
disk space for concurrent uploads/workers in addition to preserved originals.

Both `conversations.json` and numbered `conversations-000.json` /
`conversations_000.json` arrays are supported, including nested directories.
A sequential preflight pass validates JSON/CRC/size/item/node limits and counts
records before any Entry writes. A second pass parses one bounded record at a
time, in archive order. Media remains in the preserved ZIP and is not extracted
or indexed. JSON metadata, raw archive size, and individual records have separate
budgets. Malformed later shards therefore fail before partially saving Entries.

Entries and processed/failed counts commit atomically every `IMPORT_BATCH_SIZE`
items. A pinned PostgreSQL connection holds an owner session advisory lock across
these commits. Interrupted attempts retain completed batches and resume after
`processed_items + failed_items`; the current uncommitted batch rolls back. Worker
exit releases the lock. A crashed RUNNING job is eligible after
`IMPORT_MAX_SECONDS + 60` seconds, provided another worker holds no owner lock.

An already completed/partial/failed delivery is a no-op. Explicit retry resumes
an interrupted attempt; if every item was visited and errors remain, it resets
the counters and reprocesses the complete archive. Existing conversation IDs
prevent duplicate Entries. Changed snapshots retain versions; only a strictly newer
source timestamp with non-decreasing completeness can replace current automatically.
Attempts are bounded. SQL query timeouts and cooperative deadline checks remain;
there is no exact wall-clock process watchdog. A lost database connection ends
processing, so a session lock is never intentionally released while writes continue.

### Large ZIP user check

1. Restart both the API and worker so they load the new code/default limits.
   No new migration or package installation is needed for this follow-up.
2. Open http://localhost:5173/imports, select ChatGPT ZIP, and upload the original
   export. Uploading a roughly 500 MiB archive should reach the job page.
3. During preflight, total may be zero. During conversion, saved success/failure
   counts update in batches. On completion, open result Entries and search them.
4. A textless active branch reports `EMPTY_CONVERSATION`; this can yield Partially completed
   even when all supported text conversations were saved. Repeating that same
   file does not create text for such items.
5. Upload the same archive again and verify that conversation Entries do not
   multiply. Check the protected original download. Inspect source/event dates
   separately from registration dates in Entries.

The owner-provided archive produced 1,254 saved conversations and 30 textless
items from 1,284 total in the local check. The owner confirmed the expected
browser result on 2026-10-02. Agent integration checks used a disposable DB
schema and temporary local storage objects; the owner performed the browser
import separately.

To repeat the actual HTTP/storage/worker check with a synthetic 512 MiB archive:

```bash
docker compose up -d seaweedfs
docker compose -f compose.test.yaml up -d --wait
.venv/bin/python scripts/check_large_import.py
# Optional: read an existing archive locally; never modifies that file.
.venv/bin/python scripts/check_large_import.py --archive /path/to/export.zip
```

The script forces local storage and the disposable test DB, verifies its unique
schema before processing/cleanup, and only deletes object keys created by its
own invocation. It reports aggregate counts, durations, peak worker RSS, original
byte equality, and reimport uniqueness. The synthetic check also terminates a
worker after a durable batch and verifies recovery. It prints no imported titles
or bodies. Measurements on this Mac were ~6 seconds for upload and ~12 seconds
for processing, with ~119 MiB synthetic / ~211 MiB real worker peak RSS; deployment
hardware, concurrent uploads, and larger individual records require measurement.

## Automated checks

Frontend tests render the real pages with a separate in-memory API stub. They
cover the note lifecycle, server-driven cache updates, validation, cancellation,
loading/failures, retry, missing records, and unauthenticated navigation. Search
tests cover URL filters, pagination/reset, detail return, deletion page recovery,
calendar validation, empty results, and Seoul date display. Import
page tests cover multipart upload, polling, item errors, cache refresh, original
download preparation, and resuming jobs by URL.
Session tests cover logout/cache cleanup, cross-tab logout, API 401 expiry and
late responses from a previous session. Date/time tests reject impossible dates
and incomplete timestamps; form validation and file-selection labels are English.
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

Entry search/list and job-result Entries have pagination. Search has no fuzzy
matching, stemming, or attachment content extraction. Ranked searches/counts
still examine owned rows; real-corpus performance requires later measurement.
Offset pages can shift during concurrent changes. Asia/Seoul is fixed initially.
Job history shows the latest 20 jobs; each job's result Entries have
pagination. Earlier Entries/jobs do not have reconstructed artifact/result
links. Markdown reupload creates a new Entry. Tokens remain in localStorage
for development;
production authentication remains later roadmap work. Imported-record
version/deletion policies are implemented in Phase 2.2. The owner confirmed the Phase 1.1 browser flow. GitHub
Actions execution
remains to be checked separately from local automated tests. The owner
confirmed the Phase 1.2 browser flow. Automated browser connection failed in
the implementation session. Real local S3/queue/worker integration passed using
synthetic inputs in an isolated DB schema, including original downloads,
reimport, failed ZIP, and retry. Temporary inputs/storage were cleaned up.

Phase 2.2 adds history/provenance on Entry detail, personal annotations, source
status filters, and Sources collection/AI/reimport controls. Imported text is
read-only; manual notes stay editable. Deletion removes versions immediately,
blocks automatic reimport and queues original purge through the import worker.
Shared ZIP deletion removes the whole original while retaining other record text.
See [HISTORY.md](../HISTORY.md) for the precise browser walkthrough, synthetic demo,
retention/restore policy, and AWS/backup verification boundaries.
## Phase 2.3 Codex verification

After preview review and explicit apply using `../CODEX_BACKFILL.md`, open
`http://localhost:5173/sources` to inspect backfill counts, session coverage,
timestamps and gap reasons. Results refresh every five seconds and paginate.
Search with source Codex, open a record, then inspect Notes & history for ordered
messages, command results/exit codes, diffs, thread/turn/fork/archive context and
declared omissions. Existing history/policy controls remain available.

The collector runs manually on the Mac; it does not need to keep running for
stored records to remain visible. Synthetic automated/browser checks pass;
actual owner-history checks follow explicit apply.
