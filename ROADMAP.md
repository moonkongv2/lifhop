# lifhop Development Roadmap

## Purpose

This roadmap defines the learning path for lifhop.

The goal is not to build every feature as quickly as possible. The goal is to progressively learn backend architecture, API design, database modeling, authentication, file storage, async processing, queues, search, data ingestion, external integrations, LLM/RAG, AWS, Infrastructure as Code, CI/CD, and production operations.

The roadmap is expected to evolve. Major direction changes should update this document, and durable architecture decisions should be recorded in `DECISIONS.md` when appropriate.

---

# Level 1 — Useful

Target capabilities:

```text
Manual Entry
File Attachment
ChatGPT Import
Keyword Search
```

# Level 2 — Smart

Target capabilities:

```text
Semantic Search
Hybrid Search
RAG
Question Answering
Source Citations
```

# Level 3 — Connected

Target capabilities:

```text
Notion
GitHub
Gemini
Automatic Sync
Incremental Import
```

---

# Step 0 — Project Bootstrap

## Goal

Create a local backend development environment.

## Technologies

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- Docker
- Docker Compose
- pytest

## Tasks

- Initialize Python project
- Create FastAPI application
- Add `GET /health`
- Run PostgreSQL using Docker Compose
- Connect FastAPI to PostgreSQL
- Configure SQLAlchemy
- Initialize Alembic
- Configure environment variables
- Add basic tests
- Create `CURRENT.md`

## Completion Criteria

`GET /health` returns HTTP 200 and the application can connect to PostgreSQL successfully.

---

# Step 1 — Entry CRUD

## Goal

Create the core lifhop data model.

## Initial Entry Model

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

Suggested initial types:

```text
LOG
NOTE
DOCUMENT
CONVERSATION
PROJECT_EVENT
```

## API

```text
POST   /entries
GET    /entries
GET    /entries/{id}
PATCH  /entries/{id}
DELETE /entries/{id}
```

Initial filters:

- type
- event date range

## Learning Topics

- REST API design
- HTTP status codes
- Pydantic schemas
- ORM models
- Database migrations
- Pagination
- Testing API behavior

## Completion Criteria

An Entry can be created, read, updated, listed, filtered, and deleted.

---

# Step 2 — Authentication and Authorization

## Goal

Add users and secure personal data.

## Initial Model

```text
User
- id
- email
- password_hash
- created_at
```

## API

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
```

## Learning Topics

- Password hashing
- JWT
- Access and refresh tokens
- Authentication vs authorization
- Resource ownership
- FastAPI dependencies

## Completion Criteria

A user can only access their own Entries.

---

# Step 3 — Attachments and S3

## Goal

Support files such as PDF, images, Markdown, and text files.

## Initial Model

```text
Attachment
- id
- entry_id
- s3_key
- filename
- mime_type
- size
- status
- created_at
```

## Upload Flow

```text
Client
  |
  v
API requests presigned URL
  |
  v
S3 presigned URL
  |
  v
Client uploads directly to S3
```

## Learning Topics

- Object storage
- S3
- IAM
- Presigned URLs
- MIME types
- File metadata
- Secure file access

## Completion Criteria

A user can attach a PDF or image to an Entry and retrieve it securely.

---

# Step 4 — Import Framework

## Goal

Create a generic and extensible architecture for importing data from multiple external sources with different formats.

The framework should separate provider-specific parsing from lifhop's internal data representation so that new providers can be added without changing the core Entry model or persistence logic.

## Source Survey

Initial source formats to consider:

```text
Documents
├── Markdown
└── Notion exports

AI Conversations
├── ChatGPT
├── Claude
└── Gemini

Coding Agent Sessions
├── Codex CLI
└── Claude Code

Development Systems
└── GitHub
```

The goal of this survey is not to fully implement every source during Step 4.

Instead, representative source formats should be reviewed before finalizing the common import model so that the abstraction is not designed only around the simplest source.

## Conceptual Flow

```text
External Source
      |
      v
Provider Parser / Adapter
      |
      v
Canonical Item
      |
      v
Entry Normalizer
      |
      v
Common Entry Model
```

Responsibilities:

```text
Provider Parser / Adapter
- Understand provider-specific raw formats
- Extract stable identifiers and timestamps
- Convert provider-specific structures into lifhop canonical structures

Canonical Item
- Represent imported information using lifhop's internal standard vocabulary
- Preserve important source information without exposing provider-specific schemas to the rest of the application

Entry Normalizer
- Convert canonical structures into searchable lifhop Entries
- Decide how structured information such as conversations or development sessions is represented in Entry.title, Entry.content, and Entry.event_at
```

## Canonical Item Categories

Initial canonical categories to evaluate:

```text
Document
Conversation
DevSession
```

A future category may include:

```text
ProjectEvent
```

Possible provider mapping:

```text
Markdown     -> Document
Notion       -> Document

ChatGPT      -> Conversation
Claude       -> Conversation
Gemini       -> Conversation

Codex CLI    -> DevSession
Claude Code  -> DevSession

GitHub       -> ProjectEvent
```

The canonical model should avoid becoming either:

1. too generic, where all structured information is lost, or
2. provider-specific, where each provider effectively has its own internal model.

A likely direction is a common envelope combined with typed payloads:

```text
CanonicalItem
- provider
- external_id
- kind
- title
- event_at
- external_created_at
- external_updated_at
- metadata
- attachments
- payload
```

Possible payload types:

```text
DocumentPayload
ConversationPayload
DevSessionPayload
ProjectEventPayload
```

The exact fields should be finalized only after reviewing representative raw formats.

## Source Tracking

External imports need stable source identity to support later synchronization and duplicate prevention.

Initial Source model direction:

```text
Source
- id
- user_id
- provider
- external_id
- sync_mode
- last_synced_at
- metadata
```

Entries may later gain:

```text
source_id
external_id
```

Do not introduce all persistence fields immediately unless they are required by the first implementation.

Start with the smallest useful model, observe limitations, and add persistence or constraints when their need becomes clear.

## Attachments

Imported sources may contain or reference files.

Examples:

```text
ChatGPT uploaded files
Gemini uploads or generated media
Notion exported files
```

Imported attachments should eventually reuse the Attachment and S3 architecture introduced in Step 3 rather than introducing provider-specific file storage.

## Initial Implementation

Use Markdown as the first importer because its raw format is simple and stable.

Suggested progression:

```text
Source format survey
        |
        v
Canonical model design
        |
        v
Importer interface
        |
        v
Entry normalizer
        |
        v
Markdown parser
        |
        v
Unit tests
        |
        v
Entry persistence
        |
        v
API integration test
```

Markdown is the first implementation target but should not be the sole basis for designing the canonical model.

## Potential Importers

```text
MarkdownImporter
ChatGPTImporter
ClaudeImporter
GeminiImporter
NotionImporter
CodexImporter
ClaudeCodeImporter
GitHubImporter
```

Only MarkdownImporter is expected to be implemented in Step 4.

The remaining importers are used as design constraints and will be introduced in later steps.

## Learning Topics

- Adapter pattern
- Parser boundaries
- Canonical data models
- Data normalization
- Provider-specific vs domain-specific models
- External identifiers
- Source tracking
- Extensible application architecture
- Structured vs flattened representations
- Version-tolerant parsing
- Unit testing importer behavior

## Completion Criteria

A Markdown file can be:

```text
Markdown file
     |
     v
Markdown provider parser
     |
     v
Canonical Item
     |
     v
Entry Normalizer
     |
     v
lifhop Entry
```

The importer framework must keep Markdown-specific parsing outside the core Entry model and persistence logic.

The resulting architecture should also be reasonably capable of representing at least:

```text
AI conversation data
Coding-agent session data
```

without requiring provider-specific fields in the Entry model.

---

# Step 5 — ChatGPT Export Import

## Goal

Use the import framework from Step 4 with the first complex real-world provider.

Import ChatGPT conversation history from exported account data.

## Initial Pipeline

```text
ChatGPT Export ZIP
        |
        v
Upload
        |
        v
Extract
        |
        v
ChatGPT Parser
        |
        v
Canonical Conversation
        |
        v
Entry Normalizer
        |
        v
Entries
```

ChatGPT import should validate that the abstraction created in Step 4 works with structured conversation data rather than only simple documents.

## Import Job Model

```text
ImportJob
- id
- user_id
- source_id
- status
- total_items
- processed_items
- failed_items
- started_at
- completed_at
- error
```

Possible states:

```text
PENDING
RUNNING
COMPLETED
FAILED
PARTIAL
```

## Key Design Problems

Uploading the same export twice must not duplicate every conversation.

Provider-specific external identifiers and database constraints should support idempotent imports.

The importer should also preserve enough conversation structure to support future search and RAG while producing a useful textual Entry representation.

## Learning Topics

- Batch processing
- Archive parsing
- Structured conversation parsing
- Import progress
- Idempotency
- Duplicate detection
- External identifiers
- Error handling
- Imported attachment handling

## Completion Criteria

A ChatGPT export can be uploaded and conversations appear in the lifhop timeline without duplication.

---

# Step 6 — Async Processing with SQS

## Goal

Move expensive imports away from API request processing.

## Before

```text
API request
   |
   v
Parse huge export
   |
   v
Response
```

## After

```text
API
 |
 v
Create ImportJob
 |
 v
SQS
 |
 v
Worker
 |
 v
Importer
```

## AWS

Introduce:

- SQS
- Dead Letter Queue

Workers may initially continue running locally in Docker.

## Learning Topics

- Message queues
- Producer / consumer architecture
- Background workers
- At-least-once delivery
- Visibility timeout
- Retries
- DLQ
- Idempotent consumers

## Failure Exercise

Kill a worker during an import and verify that the message is redelivered and duplicate Entries are not produced.

## Completion Criteria

Imports continue correctly even when API and worker processes restart independently.

---

# Step 7 — Keyword Search

## Goal

Search across stored knowledge without an LLM.

## Evolution

```text
ILIKE
  |
  v
PostgreSQL Full Text Search
```

## Search Filters

- query
- type
- source
- date range
- tag

## Learning Topics

- Search indexes
- PostgreSQL FTS
- Ranking
- Query performance
- Database indexing

## Completion Criteria

Thousands of Entries can be searched efficiently using keywords and filters.

---

# Step 8 — Semantic Search and RAG

## Goal

Allow retrieval based on meaning rather than exact words.

## Initial Chunk Model

```text
Chunk
- id
- entry_id
- content
- embedding
- position
```

Prefer PostgreSQL + pgvector before introducing a separate vector search system.

## Pipeline

```text
Entry
 |
 v
Chunking
 |
 v
Embedding
 |
 v
pgvector
```

Question answering:

```text
Question
   |
   v
Embedding
   |
   v
Vector Search
   |
   v
Relevant Chunks
   |
   v
LLM
   |
   v
Answer + Sources
```

## Requirement

Generated answers must retain references to the Entries used as evidence.

## Learning Topics

- Embeddings
- Vector similarity
- Chunking
- Retrieval
- Context construction
- Hallucination
- Grounding
- RAG

## Completion Criteria

The user can ask a question and receive an answer with supporting source Entries.

---

# Step 9 — Hybrid Retrieval

## Goal

Improve retrieval beyond pure vector similarity.

Combine:

```text
Metadata Filters
+
Full Text Search
+
Vector Search
```

Potential ranking signals:

- semantic similarity
- lexical relevance
- date relevance
- source relevance
- recency

## Example

Question:

> What problems did I have with DFPlayer in August 2026?

Useful retrieval signals:

```text
entity = DFPlayer
date   = August 2026
intent = problems / issues
```

## Learning Topics

- Ranking
- Retrieval evaluation
- Hybrid search
- Metadata extraction
- Search quality metrics

## Completion Criteria

Hybrid retrieval performs measurably better than vector search alone on a small evaluation dataset.

---

# Step 10 — Connected Sources

## Goal

Move from uploaded exports and local files to connected integrations.

Initial candidates:

```text
Notion
GitHub
```

Step 4 defines how external data is normalized.

Step 10 focuses on how external systems are connected, authenticated, and synchronized over time.

## Notion

```text
Notion
 |
 v
Authorization
 |
 v
Sync Request
 |
 v
SQS
 |
 v
Notion Worker
 |
 v
Notion Adapter
 |
 v
Canonical Items
 |
 v
Entry Normalizer
 |
 v
Entries
```

Support incremental synchronization using fields such as:

```text
last_synced_at
external_updated_at
external_id
```

## GitHub

```text
GitHub Event
 |
 v
Webhook / API
 |
 v
lifhop API
 |
 v
Queue
 |
 v
GitHub Adapter
 |
 v
Canonical Project Events
 |
 v
Entry Normalizer
 |
 v
Entries
```

## Learning Topics

- OAuth
- Webhooks
- Signature validation
- External APIs
- Rate limits
- Incremental sync
- Event-driven systems
- Reusing importer normalization for connected sources

## Completion Criteria

Changes from at least one connected external source automatically appear in lifhop using the same canonical normalization boundary introduced in Step 4.

---

# Step 11 — Importer Expansion and Abstraction Validation

## Goal

Add multiple providers with substantially different raw formats and validate whether the importer abstraction created in Step 4 is genuinely extensible.

Initial candidates:

```text
Claude
Gemini
Codex CLI
Claude Code
```

These providers intentionally cover two different categories:

```text
AI Conversations
├── Claude
└── Gemini

Coding Agent Sessions
├── Codex CLI
└── Claude Code
```

## Validation Goal

Adding a new provider should primarily require:

```text
New provider parser / adapter
        |
        v
Existing canonical model
        |
        v
Existing Entry normalization
        |
        v
Existing persistence pipeline
```

Adding a provider should not normally require modifying:

```text
Entry ORM model
Entry CRUD behavior
Core persistence logic
Other provider parsers
```

If substantial changes are required, revisit the abstraction rather than adding provider-specific exceptions throughout the codebase.

## Coding Agent Sessions

Codex CLI and Claude Code are useful architecture tests because their data contains more than ordinary messages.

Potential information includes:

```text
session metadata
project path
repository context
user prompts
agent responses
tool calls
shell commands
timestamps
model information
```

Their raw session formats may evolve and should be treated as provider-specific implementation details.

The importer layer should tolerate format evolution without leaking unstable provider schemas into the rest of lifhop.

## Learning Topics

- Extensibility testing
- Version-tolerant parsing
- Conversation vs development-session modeling
- Provider schema evolution
- Adapter isolation
- Regression testing across importers

## Completion Criteria

At least:

```text
one additional AI conversation provider
+
one coding-agent provider
```

can be imported through the Step 4 framework without introducing provider-specific fields into the Entry model or duplicating the core persistence pipeline.

The results should be used to evaluate and, if necessary, revise the canonical model and importer interfaces.

---

# Step 12 — Production AWS Deployment

## Goal

Deploy the backend using production-style AWS infrastructure.

## Target Architecture

```text
Internet
   |
   v
Route 53
   |
   v
ALB
   |
   v
ECS Fargate
FastAPI API
  /       \
 v         v
RDS        S3
Postgres
+pgvector
   |
   v
  SQS
   |
   v
ECS Workers
```

Scheduled jobs:

```text
EventBridge
     |
     v
Sync / Maintenance Jobs
```

Supporting services:

- IAM
- Secrets Manager or Parameter Store
- CloudWatch
- ECR
- ACM

## Networking Topics

```text
VPC

Public Subnets
└── ALB

Private Subnets
├── ECS
└── RDS
```

Exact infrastructure should be driven by learning goals, security, and cost rather than copied blindly from large production systems.

## Completion Criteria

The service can be accessed securely over HTTPS while backend infrastructure is not unnecessarily exposed to the public internet.

---

# Step 13 — Infrastructure as Code and CI/CD

## Goal

Make infrastructure and deployments reproducible.

## Terraform

Expected structure may evolve toward:

```text
infra/
├── network.tf
├── ecs.tf
├── rds.tf
├── s3.tf
├── sqs.tf
├── iam.tf
├── monitoring.tf
└── variables.tf
```

Some resources may be created manually first to understand them before automating everything.

## Deployment Pipeline

```text
git push
   |
   v
GitHub Actions
   |
   v
pytest
   |
   v
docker build
   |
   v
ECR push
   |
   v
ECS deploy
   |
   v
ALB health check
```

## Learning Topics

- Infrastructure as Code
- Terraform state
- CI/CD
- Container registry
- Rolling deployments
- Environment separation

## Completion Criteria

A push to the deployment branch can test, build, and deploy the backend automatically.

---

# Step 14 — Production Operations

## Goal

Practice operating the system rather than only building it.

## Failure Exercises

### Worker Crash

Verify message redelivery, idempotent processing, and no duplicate Entries.

### Poison Message

Verify repeated failure eventually routes the message to a DLQ.

### Database Failure

Observe connection behavior, API errors, retries, and logs.

### LLM Failure

Simulate timeout, rate limit, and malformed responses.

### Queue Backlog

Generate a large number of jobs and observe queue depth, throughput, and processing latency. Consider worker autoscaling only after observing the need.

## Monitoring

Create useful CloudWatch metrics and alarms around:

- API 5xx
- queue depth
- failed imports
- worker failures
- RDS health
- latency

## Completion Criteria

Common failure scenarios are observable, understood, and documented.

---

# Documentation Strategy

## README.md

Project purpose, vision, and architecture overview.

## ROADMAP.md

Long-term development and learning sequence.

## CURRENT.md

Created when development begins. Keep concise:

```text
Current milestone
Completed work
In-progress work
Next tasks
Known issues
Last update
```

## DECISIONS.md

Create when meaningful design decisions begin to accumulate. Record the decision, rationale, alternatives when relevant, and conditions under which it should be revisited.

Examples:

- UUID vs integer IDs
- RDS vs DynamoDB
- pgvector vs OpenSearch
- SQS vs Redis-based queue
- ECS vs Lambda
- direct authentication vs Cognito

---

# Working Principle

Do not jump ahead just because a technology appears later in the roadmap.

For each major technology:

```text
Simple implementation
        |
        v
Observe limitation
        |
        v
Understand problem
        |
        v
Introduce solution
        |
        v
Test failures
        |
        v
Improve
```

The learning process is part of the deliverable.
