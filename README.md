# lifhop

**Hop through your life.**

lifhop is a personal knowledge and life memory platform that collects logs, documents, conversations, and external data sources into one searchable archive.

The long-term goal is to build a system that can answer questions based on my own historical records while showing the source records used to generate the answer.

This project is primarily a **learning project** focused on backend engineering, AWS, data pipelines, search, and LLM/RAG systems.

## Vision

Personal data is scattered across many services and formats:

- ChatGPT conversations
- Gemini conversations
- Notion pages
- GitHub activity
- Markdown notes
- PDFs and images
- Personal logs
- Project records

lifhop aims to normalize these sources into a common internal model so that they can be searched and queried together.

Personal-release priorities are finding past solutions and decision reasons,
reviewing a period, and resuming projects, in that order. Ordinary life records
such as travel planning belong alongside development records. Complete this
private release before planning a commercial service.

Example questions:

- What decisions did I make about the battery design for my bike project?
- How did the architecture of this project evolve?
- What did I investigate about App Store registration?
- Summarize my work on a project during August 2026.
- Why did I choose pgvector instead of OpenSearch?
- Which rental car company did I use in Okinawa in April 2026, and why?

Answers should be grounded in stored records and provide references back to the original sources.

## Core Concept: Entry

An `Entry` is the central data unit in lifhop. Different types of information are normalized into entries.

Examples:

- Personal log
- Note
- Document
- Conversation
- Project event
- Imported external record

Initial conceptual model:

```text
Entry
- id
- type
- title
- content
- event_at
- metadata
- created_at
- updated_at
```

External mutable resources can also carry stable source identity:

```text
provider
external_id
```

Current imported ChatGPT conversations use:

```text
UNIQUE(user_id, provider, external_id)
```

to support idempotent upsert and safe reprocessing.

A broader persistent source/connection model may be added later when connected or continuous-capture workflows make its lifecycle concrete.

## Data Sources and Release Scope

### Manual sources

- Text logs
- Notes
- Markdown
- PDF and images as attachments; searchable extraction/OCR is deferred

### Import / capture sources

- ChatGPT data export ZIP (backend and browser import implemented)
- Codex CLI on one Mac: available past sessions and scheduled collection of
  new messages, commands/results, and recorded code changes (planned)
- Selected personal/organization GitHub repositories: full accessible periods,
  commits, relevant diffs/documents, PRs/reviews, and issues/comments (planned)

Codex and GitHub are both required for the private release, with scheduled and
on-demand collection. The ChatGPT Web capture PoC remains experimental.
Gemini, Notion, Claude Code, and other sources are later candidates through the
common importer/canonical normalization boundary.

The private release must retain collected versions, prevent deleted records
from being reimported, and support repository/record-level exclusions from
external AI, including embeddings. These foundations are implemented in Phase 2.2; current
selection uses freshness/completeness guards and keeps observed versions. See `ROADMAP.md` for the agreed scope and checks.

## Long-Term Architecture Direction

The private release targets access from other devices and external networks,
preferably on AWS, within USD 20/month including storage/backups and AI usage.
Evaluate a small single-host deployment first. The diagram and service list
below describe a possible longer-term architecture, not required private-release
resources. Host, region, identity setup, workload fit, and total cost remain to
be verified before provisioning.

```text
                    Clients
                       |
                       v
                 FastAPI API
                  /        \
                 /          \
                v            v
         PostgreSQL          S3
         + pgvector       Attachments
                |
                v
               SQS
                |
                v
           ECS Workers
        /       |       \
   Import    Embedding   Sync
        \       |       /
                v
          Search / RAG
                |
                v
               LLM
                |
                v
       Answer + Source Entries
```

AWS services are introduced when a concrete product or operational need
justifies their cost and complexity.

Potential production infrastructure:

- ECS Fargate
- RDS PostgreSQL
- S3
- SQS
- EventBridge
- IAM
- Secrets Manager / Parameter Store
- CloudWatch
- ECR
- Route 53
- ALB
- ACM

## Technology Direction

Current backend stack includes:

- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Pydantic
- pytest
- Docker
- Docker Compose
- AWS S3
- AWS SQS
- boto3

Later additions may include:

- PostgreSQL Full Text Search
- pgvector
- LLM APIs
- ECS Fargate
- RDS
- Terraform
- GitHub Actions
- CloudWatch / production observability

Technology choices may change as the project progresses. Significant architecture changes should be documented rather than silently introduced.

## Local object storage

Local development uses SeaweedFS's S3-compatible endpoint instead of AWS S3
by default. Start it with:

```bash
docker compose up -d seaweedfs
```

The service creates the `lifhop-local` bucket and keeps objects in a Docker
volume. Run the FastAPI app on the host so that its default
`LOCAL_S3_ENDPOINT=http://127.0.0.1:8333` is reachable. The credentials in
`compose.yaml` are development-only.

`S3_MODE=local` is the default even when an existing `.env` contains an AWS
profile and bucket. Local mode accepts only a loopback HTTP endpoint. To
connect to real AWS S3 intentionally, set `S3_MODE=aws` and configure
`S3_BUCKET_NAME` and AWS credentials. The test suite blocks unexpected
boto3 client creation.

Queue selection is separate: `QUEUE_MODE=local` is the default and uses
PostgreSQL ImportJob rows as a durable local queue. Run the import worker with
`python -m app.workers.import_worker`; local Markdown and ZIP import require no
AWS requests when `S3_MODE=local` is also selected. `QUEUE_MODE=aws` intentionally
uses SQS and requires `SQS_IMPORT_QUEUE_URL` and AWS credentials. See
`frontend/README.md` for setup, limits, retry behavior, and synthetic samples.

## Development Philosophy

This remains a learning project. Through the frontend learning interlude, the
implementation followed an incremental learning sequence. From the
`learning-complete-f3` baseline onward, development is organized into small,
user-verifiable product results described in `ROADMAP.md`.

Preferred process:

```text
1. Define a useful user flow
2. Build the smallest complete implementation
3. Verify behavior and relevant failures
4. Show the result
5. Improve it using actual use and evaluation
```

Avoid introducing infrastructure purely to make the architecture look sophisticated.

## Project Documentation

- `README.md` — project purpose and architecture overview
- `ROADMAP.md` — active product delivery sequence and user-visible checks
- `AGENTS.md` — working rules for AI coding agents
- `CURRENT.md` — concise working status and next product slice
- `DECISIONS.md` — durable architecture decisions
- `CAPTURE.md` — capture/acquisition strategy and risk register
- `ACQUISITION.md` — Phase 2.1 read-only source checks and private preview guide
- `HISTORY.md` — Phase 2.2 browser checks, retention policy and restore procedure
- `GITHUB_DISCUSSIONS.md` — Phase 2.4B collector and synthetic browser verification
- `EVALUATION.md` — Phase 3.1 private question authoring and keyword-retrieval baselines
- `PASSAGE_SEARCH.md` — Phase 3.2A local passage search, backfill and verification
- `SEMANTIC_SEARCH.md` — Phase 3.2B1 scoped embedding comparison and usage accounting
- `SEMANTIC_PRODUCT_PLAN.md` — approved optional Semantic implementation sequence after closing B1 tuning
- `SEMANTIC_PRODUCT.md` — Semantic search UI/demo, pgvector setup, explicit indexing and worker verification
- `ANSWER_SLICE.md` — selected-passage cited-answer demo, policy/cost boundary and verification
- `UNIFIED_ANSWER.md` — one-action questions, combined consent, stop/replay limits and synthetic verification
- `RETROSPECTIVES.md` — bounded period summaries, date meaning, coverage and per-item citations
- `HISTORICAL_QUESTIONS.md` — observed version cutoffs, local history preview and cited answers

The repository is the source of truth for the project. ChatGPT, Codex CLI, Antigravity CLI, and other coding agents should read the project documentation before making changes.

## Current Status

The learning-through-F3 baseline is marked by Git tag
`learning-complete-f3`; F0–F3 was completed on 2026-09-28. The project
still serves a learning purpose, while the active roadmap now prioritizes a
usable product.

The repository now includes a minimal React + TypeScript + Vite frontend that demonstrates the real browser-to-FastAPI flow:

- React Router routes for login, Entry list/detail, note creation, and imports/jobs
- authenticated calls to the existing FastAPI login and Entry CRUD APIs
- TanStack Query for Entry server-state handling
- a Vite development proxy for local `/api/*` requests
- generated TypeScript API types from FastAPI OpenAPI using `openapi-typescript`

The backend already supports authenticated Entry CRUD, Markdown import,
ChatGPT ZIP import with asynchronous processing, and S3-backed file storage.
The ChatGPT Web Capture PoC is **LIMITED GO**: its current DOM extractor is
unreliable, so it is not a dependable product capture path.

Phase 1.1 now supports creating and managing a text Entry through the browser,
with local automated checks complete and owner browser verification confirmed. See
`frontend/README.md` for setup, user checks, and isolated test commands.
Phase 1.2 adds browser Markdown/ChatGPT ZIP upload, job status/results/retry,
protected original downloads, and bounded local processing. Local automated
checks, a real local-storage/worker integration check, and owner browser
verification of the initial flow are complete. A follow-up supports large ZIPs,
numbered JSON shards, saved progress, and interruption recovery; local 512 MiB
synthetic and 494 MiB real-archive checks passed, and the owner confirmed the
large-import browser result on 2026-10-02.
Phase 1.3 adds owner-scoped literal phrase search,
source/type/date filters, URL-preserved search state, and browser pagination.
Local checks are complete; owner browser verification is pending. This is
followed by Codex/GitHub historical collection,
source-grounded answers and period retrospectives, scheduled collection from
both new sources, and private daily-use deployment in `ROADMAP.md`.

Phase 2.1 provides a read-only CLI for Codex and selected GitHub history previews.
Real historical Codex messages/commands/changes and a GitHub commit/diff/document
were verified locally, with coverage and omissions recorded. These previews do
not create Entries or run collectors. See `ACQUISITION.md`; owner review is pending.

Phase 2.2 adds observed versions and provenance, imported read-only content with
personal annotations, source deletion markers, reimport suppression and durable
original purge, and independent collection/external-AI permissions. Existing
records have initial observed versions. Local checks pass; owner browser
verification is next using the synthetic walkthrough in `HISTORY.md`.

See `CURRENT.md` for the active product slice and `ROADMAP.md` for its
completion criteria.

Phase 2.3 adds manual Codex historical backfill: private filtered previews,
authenticated turn ingestion, durable replay receipts, Sources coverage and
readable message/command/diff evidence. Local tests and synthetic HTTP/browser
checks pass; owner preview review is confirmed, personal apply verification is
pending. Setup, exclusions,
device identity recovery, resume and cleanup are in `CODEX_BACKFILL.md`.

The Codex session checkpoint groups turn Entries for browsing, retains message
phase/order, separates commentary from primary reading/search, and focuses search
matches within sessions. Synthetic verification commands are in `CODEX_BACKFILL.md`.

Phase 2.4A adds manual GitHub commit/diff and historical Markdown collection with
private resumable preparation, reviewed apply and Sources/evidence readers. Local
checks pass; all 415 selected-source items were prepared and verified through
isolated PostgreSQL/HTTP/browser checks. Owner account apply and browser
confirmation are next. See `GITHUB_BACKFILL.md` for synthetic and real-source
commands. Owner confirmation of this slice remains pending; discussion collection
is described below.

Phase 2.4B adds manual PR/issue/review/comment preparation and apply, independent
observed versions, repository Discussions browsing and search focus. The selected
repository currently has no PRs/issues; empty-source and synthetic HTTP/browser
checks are complete; the owner confirmed synthetic browsing. Live nonempty/private
source checks remain pending. See `GITHUB_DISCUSSIONS.md`.

Phase 3.1 adds a local private evaluation CLI with fixed question/evidence revisions,
read-only PostgreSQL snapshots, current/historical passage references, keyword search
baselines and local reports. A separate approved three-question pilot is measured;
the original about-20-question diverse set remains incomplete. Synthetic verification
is separate. See `EVALUATION.md` for authoring and review commands.

Phase 3.2A adds local PostgreSQL passage retrieval beside Exact phrase search,
source-version ranges, grouped identical document snapshots and original passage
readers. Current-record changes synchronize the derived index atomically; old
accounts use authenticated resumable backfill. No embeddings or generated answers
are added, and external-AI-denied records remain locally searchable. See
`PASSAGE_SEARCH.md`; owner browser checks, including note create/edit/delete search
updates, are confirmed.
