# lifhop Product Roadmap

## Purpose

lifhop remains a learning project, but implementation after the frontend
learning interlude is organized around usable product results. The goal is a
personal archive that can collect records, retrieve them, answer questions
with traceable source evidence, and make gaps in collection visible.

The earlier learning sequence is preserved in Git history at
`learning-complete-f3`. This file is the active implementation plan.
`CURRENT.md` identifies the next slice; `DECISIONS.md` records durable
architecture decisions; `CAPTURE.md` holds capture-specific constraints.

## Delivery rule

Complete one user-verifiable slice at a time. Each slice includes the API,
browser flow when applicable, authorization, useful failure behavior, and
tests for the new behavior. Show the user the result before starting the next
slice. Run the relevant existing backend tests and frontend build/lint checks
for each change; add a lightweight automated check early so this does not
depend on memory. Keep the FastAPI OpenAPI contract and generated frontend
types aligned.

The order below expresses dependencies, not a commitment to implement every
possible provider or technology. Change it when observed usage or evaluation
shows a better route; document material changes here and in `CURRENT.md`.

## Existing foundation

- FastAPI, PostgreSQL, SQLAlchemy, Alembic, authentication, and user-owned
  Entry CRUD with pagination.
- S3 attachments and preserved import artifacts.
- Markdown import and asynchronous, idempotent ChatGPT ZIP import through
  ImportJob, SQS, and a worker.
- Shared canonical normalization and external Entry upsert.
- React login, Entry list, and Entry detail using generated API types.
- Experimental ChatGPT Web capture. The current DOM extractor is unreliable;
  its successful earlier demo does not make it a dependable acquisition path.

The frontend has no Entry creation, import, search, or question-answering
screen yet. Attachment storage does not imply searchable PDF or image text.

## Phase 1 — A usable archive

### 1.1 Create and manage a record in the browser

Add a browser form for creating a text Entry, then edit and delete controls on
the user's own Entries. Provide clear empty, loading, validation, and error
states. Reuse the existing Entry API and generated schema.

**User check:** Sign in, write a note, see it in the list, open it, edit it,
delete it, and see the list update.

### 1.2 Import records in the browser

Add Markdown and ChatGPT ZIP upload flows using the existing APIs. For ZIPs,
show the ImportJob state and final counts/errors; allow the user to open
imported Entries. Keep the imported raw artifact accessible through its
existing protected download endpoint. Use the local S3-compatible store.
Provide a local queue path before demonstrating ZIP processing so ordinary
development does not require AWS SQS.

**User check:** Upload a file, observe processing or a useful failure, and
open a resulting Entry without calling the API manually.

### 1.3 Search and navigate records

Add user-scoped title/content keyword search, source/type and date filters
that are backed by existing or explicitly added fields, and pagination.
Connect search results to Entry detail. Start with the simplest query that
works on real Korean and English records. Add PostgreSQL indexing or full
text search only after testing relevance and query plans on representative
data; do not require a fixed ILIKE-to-FTS progression.

**User check:** Find a known note or imported conversation, narrow results,
page through them, and never see another user's records.

**Phase exit:** A user can put records in lifhop and find them through the
browser. This is the first useful release without an LLM.

## Phase 2 — Answers grounded in records

### 2.1 Establish an evaluation set and source references

Record a small, private set of real questions with expected supporting
Entries, including Korean, English, and queries with no sufficient evidence.
Do not commit personal archives or secrets. Ensure the answer API can expose
an inspectable reference to the original Entry and, when useful, a passage.

**User check:** Review which records should support representative answers
before trusting generated output.

### 2.2 Index existing searchable text

Split Entry text into retrievable passages, create embeddings, and backfill
existing Entries. Keep the index synchronized when an Entry is created,
updated, deleted, or reimported. Use PostgreSQL with pgvector if evaluation
shows semantic retrieval is needed; keep lexical search available for exact
names, dates, and terms. Reuse the existing job infrastructure only where
background processing is actually needed.

**User check:** A newly imported or edited Entry becomes findable by meaning;
a deleted or replaced passage stops appearing.

### 2.3 Ask a question and inspect the evidence

Add a question-answering API and browser page. Retrieve only the current
user's records, give the model bounded source context, return references
alongside the answer, and show insufficient evidence honestly. Handle model
timeouts, errors, and usage limits as visible failures.

**User check:** Ask a question, read the answer, open every cited Entry, and
see an appropriate response when the archive lacks an answer.

**Phase exit:** lifhop answers representative questions with traceable
records. This is the first complete version of the core product promise.

## Phase 3 — Records that continue to arrive

### 3.1 Choose the first recurring source

Compare a small number of sources the user actually uses. For each, verify
available official APIs or native hooks, data access, incremental update
semantics, permissions, maintenance burden, and provider policy. Choose one
stable path; do not assume the experimental ChatGPT DOM extractor is ready.
Keep ZIP import for historical enrichment.

**User check:** Inspect a concrete working acquisition prototype and choose
the source with the best useful-records-to-effort ratio.

### 3.2 Deliver one dependable capture or sync flow

Route the chosen source through the existing canonical/Entry boundary.
Support idempotent updates, a visible last-success/failure state, disconnect
or pause where applicable, and an honest account of what the source covers.
Protect existing complete data from stale or incomplete replacements.

**User check:** Create or update a record at the source, see it appear or
update in lifhop without repeated export/upload, and see failures or gaps.

**Phase exit:** The archive can grow with low repeated user effort.

## Phase 4 — Private daily-use release

Deploy only after the main flows are useful locally. Make backend and frontend
deployment reproducible, run automated checks on changes, apply migrations,
manage secrets, backups, authorization, retention/deletion, file limits, and
LLM usage/cost limits. Replace the development browser token-storage pattern
with a reviewed production authentication flow before internet exposure.
Make import, indexing, capture, and model failures observable. Choose AWS
resources according to actual security, reliability, and cost requirements;
the README architecture sketch is a direction, not a required bill of
materials.

**User check:** Use the product over HTTPS on another device, recover from a
failed import or model request, and confirm new deployments do not lose data.

## Phase 5 — Improve quality and broaden coverage

Use the Phase 2 evaluation set and real usage to prioritize:

- lexical/vector fusion or reranking when it improves retrieval;
- PDF text extraction and, if justified, OCR for documents users actually
  need to search;
- additional conversation, connected, native, or mobile capture sources;
- summaries and hierarchical retrieval for questions spanning many records,
  projects, or years.

Derived summaries guide navigation but do not replace preserved records as
evidence. Add another search system or complex infrastructure only when the
measured limitations of PostgreSQL justify it.

**User check:** Compare answers against the evaluation set and inspect the
original records behind broader conclusions.

## Working boundaries

- Preserve raw imported files separately from normalized Entries.
- Scope retrieval, answers, files, jobs, and source state to the owner.
- Treat SQS delivery and external updates as repeatable.
- Do not silently turn partial capture into a claim of complete history.
- Keep the ChatGPT Web extension experimental until extraction reliability,
  overwrite protection, permissions, and provider policy are validated.
- Do not commit personal archives, credentials, or evaluation data derived
  from private records.
