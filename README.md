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
external AI, including embeddings. These are planned requirements; current
upsert replaces Entry content. See `ROADMAP.md` for the agreed scope and checks.

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
verification are complete. Search is followed by Codex/GitHub historical collection,
source-grounded answers and period retrospectives, scheduled collection from
both new sources, and private daily-use deployment in `ROADMAP.md`.

See `CURRENT.md` for the active product slice and `ROADMAP.md` for its
completion criteria.
