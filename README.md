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

Example questions:

- What decisions did I make about the battery design for my bike project?
- How did the architecture of this project evolve?
- What did I investigate about App Store registration?
- Summarize my work on a project during August 2026.
- Why did I choose pgvector instead of OpenSearch?

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

## Planned Data Sources

### Manual sources

- Text logs
- Notes
- Markdown
- PDF
- Images

### Import / capture sources

- ChatGPT data export
- ChatGPT Web capture PoC
- Gemini / Google Takeout
- Notion
- GitHub
- Codex / Claude Code session data

Other sources may be added later through the common importer/canonical normalization boundary.

## High-Level Target Architecture

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

- React Router routes for login, Entry list, and Entry detail
- authenticated calls to the existing FastAPI login and Entry APIs
- TanStack Query for Entry server-state handling
- a Vite development proxy for local `/api/*` requests
- generated TypeScript API types from FastAPI OpenAPI using `openapi-typescript`

The backend already supports authenticated Entry CRUD, Markdown import,
ChatGPT ZIP import with asynchronous processing, and S3-backed file storage.
The ChatGPT Web Capture PoC is **LIMITED GO**: its current DOM extractor is
unreliable, so it is not a dependable product capture path.

The next user-visible result is creating and managing a text Entry through the
browser. Import, search, source-grounded answers, recurring capture, and
private daily-use deployment follow in `ROADMAP.md`.

See `CURRENT.md` for the active product slice and `ROADMAP.md` for its
completion criteria.
