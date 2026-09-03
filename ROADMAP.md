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
User-provided Document Import
ChatGPT Import
Keyword Search
```

# Level 2 — Smart

Target capabilities:

```text
Document Content Extraction
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

Step 3 focuses on secure file storage and retrieval. It does not yet imply that the contents of a PDF or image are searchable knowledge.

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

Create a generic and extensible architecture for importing user-provided content and data from external systems with different formats.

The framework should separate source-specific parsing from lifhop's internal data representation so that new sources can be added without changing the core Entry model or persistence logic.

## Source Survey

Initial source formats to consider:

```text
User-provided Documents
├── Plain Text
├── Markdown
├── PDF
└── Image

External Documents
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

Representative source formats should be reviewed before finalizing the common import model so that the abstraction is not designed only around the simplest source.

Plain Text and Markdown are the first implementation targets.

PDF and Image are required long-term user-facing source types, but Step 4 only needs to ensure that the architecture can accommodate them. PDF text extraction, OCR, and vision-based image understanding are intentionally deferred until their processing requirements are introduced explicitly.

## Storage vs Ingestion

File storage and knowledge ingestion are separate responsibilities.

```text
Storage
- preserve original files
- use S3-backed storage

Ingestion
- understand source contents
- convert contents into Canonical Items
- normalize them into searchable Entries
```

Two different classes of stored files should be distinguished conceptually:

```text
Entry Attachment
- a file that belongs to a user-visible Entry
- examples: uploaded PDF, image, Markdown file, imported conversation attachment

Raw Import Artifact
- the original input used to perform an import
- examples: Markdown file, ChatGPT export ZIP, Notion export ZIP, Gemini Takeout archive
- retained so the import can be inspected, reprocessed, or downloaded later
```

These may share S3 infrastructure, but they serve different lifecycle and ownership purposes. A raw import archive should not be forced into the Entry Attachment model merely because both are files.

Original user-provided files should be preserved whenever a file exists. For example, importing a Markdown file should retain the original `.md` object in S3 in addition to producing normalized Entry content.

```text
Markdown File Upload
   |
   +--> Original .md --> S3 raw/original file
   |
   +--> Markdown Parser --> DocumentPayload --> Entry
```

A future PDF flow may become:

```text
PDF Upload
   |
   +--> Original PDF --> Attachment / original object --> S3
   |
   +--> Text Extraction --> DocumentPayload --> Entry
```

A future image flow may become:

```text
Image Upload
   |
   +--> Original Image --> Attachment / original object --> S3
   |
   +--> OCR / Vision --> DocumentPayload --> Entry
```

Step 3 already provides the main S3 storage mechanics. Later import and document-processing work should reuse that infrastructure rather than introduce a separate file system.

## Conceptual Flow

```text
Source
  |
  +--> Preserve original file/archive in S3 when applicable
  |
  v
Provider / Format Parser or Adapter
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
Provider / Format Parser or Adapter
- Understand source-specific raw formats
- Extract stable identifiers and timestamps when available
- Convert source-specific structures into lifhop canonical structures

Canonical Item
- Represent imported information using lifhop's internal standard vocabulary
- Preserve important source information without exposing source-specific schemas to the rest of the application

Entry Normalizer
- Convert canonical structures into searchable lifhop Entries
- Decide how structured information such as conversations or development sessions is represented in Entry.title, Entry.content, and Entry.event_at
```

## Normalizer Evolution Strategy

Importer and Normalizer both vary by input type, but they currently use different implementation strategies because they change along different axes.

Importers vary by external source or format:

```text
PlainTextImporter
MarkdownImporter
ChatGPTImporter
NotionImporter
CodexImporter
...
```

These sources have substantially different raw schemas and parsing behavior. The importer boundary therefore starts with an explicit ABC / generic interface so each source-specific implementation is isolated from the beginning.

Entry normalization varies by the much smaller set of lifhop canonical payload kinds:

```text
DocumentPayload
ConversationPayload
DevSessionPayload
ProjectEventPayload (future)
```

At the beginning of Step 4, normalization rules are intentionally small. Start with one `EntryNormalizer` that dispatches on canonical payload type rather than introducing a class hierarchy before the complexity exists.

```text
CanonicalItem
    |
    v
EntryNormalizer
    |
    +--> DocumentPayload      -> DOCUMENT Entry
    +--> ConversationPayload  -> CONVERSATION Entry
    +--> DevSessionPayload    -> appropriate Entry representation
```

Revisit the design and consider Strategy / ABC-based normalizers when one or more of these signals appear:

```text
normalizer branches continue to grow
individual branches become substantial or hard to test independently
payload kinds need different collaborators or dependencies
conversation flattening becomes materially different from document normalization
development-session normalization gains tool-call, command, or repository-specific rules
adding a canonical kind repeatedly requires editing a large central normalizer
```

Step 5 is an explicit checkpoint for this decision because it introduces the first non-document normalization logic. The Step 5 implementation showed that conversation normalization can still be handled clearly by the current central normalizer, so a Strategy / ABC split remains deferred until complexity actually justifies it.

## Canonical Item Categories

Initial canonical categories:

```text
Document
Conversation
DevSession
```

A future category may include:

```text
ProjectEvent
```

Possible source mapping:

```text
Plain Text    -> Document
Markdown      -> Document
PDF           -> Document
Image         -> Document
Notion        -> Document

ChatGPT       -> Conversation
Claude        -> Conversation
Gemini        -> Conversation

Codex CLI     -> DevSession
Claude Code   -> DevSession

GitHub        -> ProjectEvent
```

The current direction is a common envelope combined with typed payloads.

```text
CanonicalItem
- provider
- external_id
- title
- event_at
- payload
```

Initial payload types:

```text
DocumentPayload
ConversationPayload
DevSessionPayload
```

Potential future fields include:

```text
external_created_at
external_updated_at
metadata
attachments
```

They should be added only when concrete source implementations demonstrate the need.

## Source Tracking and External Entry Identity

External imports need stable source identity to support synchronization and duplicate prevention.

A future persistent `Source` model may still evolve toward:

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

Step 5 established a concrete Entry-level identity rule before a full Source model was necessary.

When an external provider supplies a stable identifier for a mutable resource, persist normalized Entry identity using:

```text
(user_id, provider, external_id)
```

The default persistence behavior for such resources is upsert:

```text
matching identity not found
→ INSERT

matching identity found
→ UPDATE with the latest normalized provider data
```

This allows repeated or incremental exports to refresh existing external resources while creating only newly discovered ones.

Example:

```text
First export
A, B, C

Later export
A(updated), B, C, D, E

Result
A -> UPDATE
B -> UPDATE
C -> UPDATE
D -> INSERT
E -> INSERT
```

This is a default for mutable external resources with stable IDs, not a universal rule for every future record type. Immutable events, append-only histories, or providers without stable identifiers may require a different persistence policy.

Raw artifact preservation remains independent from normalized Entry identity. Multiple uploaded archives may therefore be retained even when they contain overlapping external resources.

Durable details of this policy are recorded in `DECISIONS.md`.

## User-provided Document Sources

User-provided content should support both direct text entry and file-based input.

Potential source models may evolve toward source-specific input types such as:

```text
PlainTextSource
- content
- title?

MarkdownSource
- content
- filename?
- title?
- original object reference?

PdfSource
- original file / object reference
- filename
- title?

ImageSource
- original file / object reference
- filename
- title?
```

The parser should not be responsible for how uploaded files were transported or stored.

```text
HTTP Upload / S3 / Local File
          |
          v
Application layer preserves original file when applicable
          |
          v
Application layer resolves contents or object reference
          |
          v
Source-specific parser
```

## Attachments and Raw Import Artifacts

Imported sources may contain or reference files.

Entry-level files should reuse the Attachment and S3 architecture introduced in Step 3 rather than introducing source-specific file storage.

The original import input should also be preserved in S3 when it is a file or archive.

Examples:

```text
notes.md
chatgpt-export.zip
notion-export.zip
gemini-takeout.zip
```

Raw import artifacts exist to support:

```text
re-import with a newer parser
bug investigation
recovery from normalization mistakes
auditing what input produced stored Entries
user download of the preserved original
```

Initial model:

```text
ImportArtifact
- id
- user_id
- s3_key
- filename
- mime_type
- size
- created_at
```

The secure retrieval flow mirrors the ownership and presigned-download principles already learned for Entry attachments.

## Initial Implementation

Use Plain Text and Markdown as the first two document importers.

```text
PlainTextImporter ---\
                     +--> DocumentPayload --> CanonicalItem
MarkdownImporter ----/
```

For file-based Markdown import, preserve the original `.md` file in S3 while parsing its text into a Canonical Document.

## Potential Importers

```text
PlainTextImporter
MarkdownImporter
PdfImporter
ImageImporter

ChatGPTImporter
ClaudeImporter
GeminiImporter
NotionImporter
CodexImporter
ClaudeCodeImporter
GitHubImporter
```

## Learning Topics

- Adapter pattern
- Parser boundaries
- Generic importer interfaces
- Canonical data models
- Data normalization
- Source-specific vs domain-specific models
- External identifiers
- Source tracking
- Extensible application architecture
- Structured vs flattened representations
- File storage vs content ingestion
- Raw artifact preservation and reprocessing
- Raw artifact ownership and secure download
- Strategy / ABC refactoring driven by observed complexity
- Version-tolerant parsing
- Unit testing importer behavior

## Completion Criteria

Plain Text and Markdown can both be converted through the common importer framework:

```text
Plain Text / Markdown
        |
        v
Source-specific parser
        |
        v
Canonical Document Item
        |
        v
Entry Normalizer
        |
        v
lifhop Entry
```

When Markdown is supplied as a file, the original `.md` file is preserved in S3 independently of the normalized Entry representation, its metadata is persisted as an `ImportArtifact`, and the owning user can securely request a presigned download URL for the original.

---

# Step 5 — ChatGPT Export Import

## Status

Complete as of 2026-09-03.

## Goal

Use the import framework from Step 4 with the first complex real-world provider.

Import ChatGPT conversation history from exported account data while preserving raw source history and preventing duplicate normalized conversations.

## Implemented Pipeline

```text
ChatGPT Export ZIP
        |
        +--> Preserve original ZIP in S3
        |        |
        |        v
        |   ImportArtifact
        |        |
        |        v
        |   ImportJob
        |
        v
Source Factory
        |
        v
ChatGPTSource
        |
        v
ChatGPTImporter
        |
        v
Canonical ConversationPayload
        |
        v
Entry Normalizer
        |
        v
CONVERSATION Entries
```

The source factory owns ZIP/container concerns. `ChatGPTImporter` owns ChatGPT-specific conversation structure.

ChatGPT exports use a node-based mapping. The initial importer reconstructs the active branch by following `current_node` through parent links and then reversing that chain. User and assistant text messages on that branch are normalized into a `ConversationPayload`.

The raw export remains available even if parsing policy changes later.

## ImportArtifact and ImportJob

Step 5 established separate source and processing concepts:

```text
ImportArtifact
- original uploaded source/archive
- preserved independently from normalized Entries

ImportJob
- one processing attempt for an artifact
- status and counters
- processing error information
```

The relationship allows one preserved artifact to support multiple processing attempts in the future.

Current `ImportJob` states:

```text
PENDING
RUNNING
COMPLETED
FAILED
PARTIAL
```

Current counters:

```text
total_items
processed_items
failed_items
```

## External Identity and Idempotent Upsert

ChatGPT supplies a stable `conversation_id`, which is stored as the Entry's `external_id`.

```text
provider    = chatgpt
external_id = conversation_id
```

The database protects normalized external identity using:

```text
UNIQUE(user_id, provider, external_id)
```

Repeated imports use upsert semantics rather than insert-only or skip-only semantics:

```text
conversation does not exist
→ INSERT

conversation already exists
→ UPDATE title/content/event data from the newer normalized source
```

This matters because a later ChatGPT export can contain an existing conversation that has continued since the previous export.

Example:

```text
Export #1
A, B, C

Export #2
A(updated), B, C, D, E

Normalized result
A, B, C, D, E
```

Both raw ZIP uploads remain preserved as separate `ImportArtifact` records.

Exact raw-file duplicate detection is intentionally a separate concern. A future SHA-256 checksum may be stored for diagnostics or exact-file detection, but ZIP equality is not used as the primary normalized conversation identity.

## Failure Semantics

Archive/job state is persisted before Entry processing so failures remain observable.

```text
S3 upload
→ ImportArtifact
→ ImportJob RUNNING
→ commit
→ parse/process Entries
```

Import-wide failure:

```text
invalid ZIP / archive-level failure
→ rollback Entry-processing transaction
→ ImportJob FAILED
→ error recorded
```

Item-level failure:

```text
valid archive
→ process conversations independently
→ successful items remain
→ failed_items increment
→ ImportJob PARTIAL
```

All conversations successful:

```text
ImportJob COMPLETED
```

The test session infrastructure uses savepoints so these multiple application `commit()` / `rollback()` boundaries can be tested without leaking test data.

## Normalizer Design Checkpoint

Conversation normalization was added to the existing `EntryNormalizer`.

The implementation remains small enough that introducing payload-specific Strategy / ABC normalizers would add more abstraction than value at this point.

Keep the current central normalizer and revisit when additional canonical kinds or substantially more complex rules make the branching harder to maintain.

## Learning Topics

- Batch/archive processing
- Raw import artifact storage in S3
- Reprocessing from preserved source data
- Structured conversation parsing
- External identity
- Upsert semantics
- Idempotency
- Transaction boundaries
- Import progress/state
- Whole-job vs item-level failure handling
- Savepoints in integration tests
- Recognizing when conditional dispatch should evolve into Strategy / ABC polymorphism

## Completion Criteria

A ChatGPT export can be uploaded and its original archive is retained securely in S3.

Its active conversations are parsed into canonical `ConversationPayload` values and normalized into `CONVERSATION` Entries.

Repeated exports do not duplicate conversations. Existing conversations are updated by stable external identity and newly discovered conversations are inserted.

Raw uploaded archives remain preserved independently from normalized Entry deduplication.

Import processing records `COMPLETED`, `PARTIAL`, or `FAILED` results with appropriate counters/error information, and the full regression suite passes.

The normalizer design has been reviewed and remains intentionally simple for now.

---

# Step 6 — Async Processing with SQS

## Goal

Move expensive imports away from API request processing while preserving the synchronous Step 5 behavior as the contract to reproduce asynchronously.

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
Preserve ImportArtifact
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
Load preserved artifact
 |
 v
Importer / Normalizer / Upsert
```

## AWS

Introduce:

- SQS
- Dead Letter Queue

Workers may initially continue running locally in Docker.

## Required behavioral continuity

Moving work to SQS must not change the external-data identity rules established in Step 5.

The worker must retain:

```text
(user_id, provider, external_id) identity
upsert behavior
ImportArtifact preservation
ImportJob lifecycle
PARTIAL / FAILED semantics
```

At-least-once queue delivery means consumers must remain idempotent. Redelivering a job must not create duplicate Entries.

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

Before semantic indexing, source content must exist in searchable textual form.

For ordinary text, Markdown, and conversation sources this happens during import. For binary documents such as PDFs and images, introduce content extraction when needed.

Potential document-processing capabilities:

```text
PDF text extraction
Image OCR
Vision-based image description / understanding
Extracted text normalization
Attachment -> searchable Entry content
```

These capabilities may be implemented immediately before or during Step 8 depending on which real user documents are being indexed. If their scope grows substantially, promote them into a dedicated roadmap step rather than hiding them inside the RAG implementation.

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

- Document content extraction
- OCR / vision boundaries
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

Connected mutable resources with stable IDs should reuse the external-identity/upsert policy established in Step 5 unless the provider's semantics require a different strategy.

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

GitHub also provides a useful counterexample to blindly applying upsert to every external record: immutable event-like records may use append-only persistence rather than mutable-resource upsert. Provider semantics should determine the policy.

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

External providers with stable mutable-resource IDs should normally reuse the Step 5 upsert persistence boundary instead of implementing provider-specific duplicate logic.

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

Keep concise:

```text
Current milestone
Completed work
In-progress work
Next tasks
Known issues
Last update
```

## DECISIONS.md

Record durable design decisions, rationale, alternatives when relevant, and conditions under which they should be revisited.

Current import-related decisions include:

```text
raw ImportArtifact preservation vs normalized Entry identity
stable external resource identity and upsert
ImportArtifact vs ImportJob lifecycle
processing transaction boundaries
FAILED vs PARTIAL semantics
```

---

# Learning-Oriented Tests

Some tests may be added primarily to make a framework behavior, language feature, or architectural concept explicit during the learning process.

Examples may include:

```text
verifying that an abstract base class cannot be instantiated
demonstrating discriminated-union validation behavior
testing framework behavior already guaranteed by Python or a mature library
```

These tests are useful while a concept is being introduced because they make assumptions visible and provide fast feedback.

They should not automatically become permanent regression tests.

As the project matures, review learning-oriented tests and remove tests that:

```text
primarily verify Python or framework behavior rather than lifhop behavior
no longer protect a meaningful application contract
duplicate stronger integration or implementation-level tests
add maintenance cost without meaningful regression protection
```

Permanent tests should primarily protect lifhop-specific behavior, boundaries, failure cases, and user-visible requirements.

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
