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

AWS services are introduced gradually, only when there is a clear problem or learning goal they solve.

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

This project is intended for learning, so implementation should progress incrementally.

Preferred process:

```text
1. Build the simplest working implementation
2. Observe its limitations
3. Understand the underlying problem
4. Introduce the technology that solves the problem
5. Test failure scenarios
6. Improve the design
```

Example:

```text
Import inside API request
        |
        v
Large import causes slow requests
        |
        v
Learn background processing
        |
        v
Introduce SQS + Worker
        |
        v
Test redelivery / duplicate processing
        |
        v
Require idempotent consumers
```

Avoid introducing infrastructure purely to make the architecture look sophisticated.

## Project Documentation

- `README.md` — project purpose and architecture overview
- `ROADMAP.md` — development milestones and learning sequence
- `AGENTS.md` — working rules for AI coding agents
- `CURRENT.md` — concise current status and next work
- `DECISIONS.md` — durable architecture decisions
- `CAPTURE.md` — capture/acquisition strategy and risk register

The repository is the source of truth for the project. ChatGPT, Codex CLI, Antigravity CLI, and other coding agents should read the project documentation before making changes.

## Current Status

Step 6 — **Async Processing with SQS** is complete.

Implemented and verified behavior includes:

- ChatGPT ZIP upload preserved in S3 as an `ImportArtifact`
- `PENDING` `ImportJob` persisted before queue submission
- `POST /imports/chatgpt` returns HTTP 202 and enqueues `job_id` to SQS
- a separate worker consumes the message and runs the import processor
- `GET /import-jobs/{job_id}` exposes processing status with ownership protection
- successful processing deletes the SQS message only after durable DB work completes
- failed/undeleted messages can be redelivered after the visibility timeout
- reprocessing the same ChatGPT job does not duplicate Entries because persistence is idempotent by stable external identity
- the SQS redelivery/idempotency failure exercise was verified against the real development queue

The next milestone is **Step 6.5 — ChatGPT Web Capture PoC**, a small Chromium-extension experiment to validate lower-effort ongoing ChatGPT capture before the project returns to frontend learning and Step 7 keyword search.

See `CURRENT.md` for the exact active milestone and `ROADMAP.md` for the full learning and development plan.
