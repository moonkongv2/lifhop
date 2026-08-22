# Agent Instructions

This repository may be developed using multiple AI-assisted tools, including ChatGPT, Codex CLI, Antigravity CLI, and other coding agents.

The repository documentation is the source of truth. Do not rely on previous conversational context being available.

---

# Before Starting Work

Before modifying code:

1. Read `README.md`.
2. Read `ROADMAP.md`.
3. Read `CURRENT.md` if it exists.
4. Read `DECISIONS.md` if it exists.
5. Check the current Git status.
6. Inspect relevant existing code before proposing structural changes.

If repository documentation and the user's current explicit instruction disagree, follow the user's current instruction and update repository documentation when appropriate.

---

# Current Milestone Rule

Work primarily within the current milestone defined in `CURRENT.md`.

If `CURRENT.md` does not yet exist, use the earliest incomplete milestone in `ROADMAP.md`.

Do not implement later roadmap features merely because they may eventually be useful.

Examples:

- Do not add Redis before a real requirement exists.
- Do not introduce SQS before asynchronous processing is being learned.
- Do not introduce Kubernetes.
- Do not introduce OpenSearch while PostgreSQL search is sufficient.
- Do not introduce microservices without a concrete reason.

Prefer the simplest architecture that satisfies the current milestone.

---

# Learning-First Development

This is a learning project.

When introducing a significant concept or technology, make the reason understandable.

Preferred sequence:

```text
1. Identify the current limitation or requirement.
2. Explain the relevant concept.
3. Implement the smallest useful solution.
4. Add tests.
5. Demonstrate or test failure behavior where relevant.
6. Document important conclusions.
```

Avoid hiding important behavior behind excessive abstraction.

Prefer readable implementations over clever implementations.

---

# Architecture Changes

Do not silently change architecture.

Examples of significant changes:

- changing the database;
- changing authentication strategy;
- replacing the queue system;
- introducing a new AWS service;
- changing the Entry data model substantially;
- changing the importer architecture;
- introducing a new infrastructure platform.

When such a change is needed:

1. Explain why.
2. Evaluate alternatives when meaningful.
3. Record the decision in `DECISIONS.md` if it has long-term impact.
4. Update `ROADMAP.md` if the project direction changes.

---

# Dependencies

Do not add dependencies without a clear reason.

Before adding a package:

1. Check whether the existing stack already solves the problem.
2. Prefer mature and actively maintained libraries.
3. Avoid overlapping packages that provide the same capability.
4. Mention the reason for significant new dependencies in the work summary.

---

# Database Changes

Use migrations for persistent schema changes.

Do not depend on an undocumented local database state.

When modifying database models:

1. Update the model.
2. Add or update the Alembic migration.
3. Verify upgrade behavior.
4. Add relevant tests.

Avoid destructive migrations unless explicitly required.

---

# API Design

Prefer predictable REST semantics.

Use `GET`, `POST`, `PATCH`, and `DELETE` appropriately.

Return meaningful HTTP status codes.

Use explicit request and response schemas.

Validate external input.

Do not expose internal database objects directly when a response schema is appropriate.

---

# External Data Imports

External providers must not leak provider-specific assumptions throughout the core application.

Prefer:

```text
Provider Data
     |
     v
Importer Adapter
     |
     v
Normalizer
     |
     v
Common Internal Model
```

Provider-specific raw fields may be preserved in metadata when useful.

Imports should eventually support idempotent processing.

Do not assume external schemas are stable.

---

# Async Jobs

When asynchronous processing is introduced:

- assume messages may be delivered more than once;
- design consumers to be idempotent;
- distinguish transient and permanent failures;
- avoid acknowledging successful processing before durable state is written;
- make failures observable.

Do not introduce asynchronous infrastructure before the roadmap reaches the relevant milestone unless explicitly requested.

---

# AWS

AWS services should be introduced to solve concrete requirements and support learning goals.

Prefer understanding a service before automating it completely.

Use IAM roles instead of embedding long-lived AWS credentials in application code.

Apply least privilege where practical.

Do not make databases or internal services publicly accessible without a clear reason.

Be conscious of AWS cost.

Avoid creating expensive resources casually, including:

- unnecessary NAT Gateways;
- oversized RDS instances;
- always-running services that are not needed;
- large OpenSearch clusters.

Mention potential recurring cost when introducing infrastructure that may incur meaningful charges.

---

# Security

Never commit:

- passwords;
- API keys;
- AWS credentials;
- JWT secrets;
- private keys;
- database credentials;
- exported personal data.

Use environment variables or secret management systems.

Ensure `.gitignore` covers local secret files.

Treat imported personal archives as sensitive data.

---

# Testing

Behavior changes should normally include corresponding tests.

Prefer tests that validate observable behavior rather than implementation details.

Before completing a task:

1. Run relevant tests.
2. Run the full test suite when practical.
3. Report failures honestly.

Do not claim tests passed unless they were actually executed successfully.

---

# Code Quality

Prefer:

- small functions;
- clear names;
- explicit typing;
- simple control flow;
- obvious dependencies;
- focused modules.

Avoid premature abstraction.

Do not create interfaces with only hypothetical future implementations unless the roadmap specifically calls for extensibility.

Comments should explain **why**, not restate obvious code.

---

# Git Discipline

Before making changes:

```bash
git status
```

Avoid modifying unrelated files.

Keep changes focused on the requested task.

Do not rewrite unrelated user work.

Do not force push.

Do not perform destructive Git operations unless explicitly requested.

Suggested commit style:

```text
feat: add entry creation API
fix: prevent duplicate imported conversations
test: add entry repository tests
docs: update current milestone status
refactor: extract importer normalization
```

Commits should describe meaningful units of work.

---

# Documentation Updates

At the end of a meaningful development session:

## CURRENT.md

Update:

- current milestone;
- completed items;
- work in progress;
- next tasks;
- known issues.

Keep this document short.

Example:

```text
# Current Status

## Current Milestone
Step 1 - Entry CRUD

## Completed
- FastAPI initialized
- PostgreSQL Docker Compose added
- SQLAlchemy configured
- Entry model created

## In Progress
- POST /entries

## Next
1. GET /entries
2. GET /entries/{id}
3. PATCH /entries/{id}
4. DELETE /entries/{id}
5. CRUD tests

## Known Issues
None
```

## DECISIONS.md

Update only when there is a durable architectural or design decision worth preserving.

## ROADMAP.md

Do not update merely to reflect minor progress.

Update it when:

- milestone scope changes;
- milestone order changes;
- a major technology decision changes the planned direction.

---

# Before Finishing a Task

Before reporting completion:

1. Review the diff.
2. Run relevant tests.
3. Check Git status.
4. Update `CURRENT.md` when appropriate.
5. Update `DECISIONS.md` if a durable decision was made.
6. Summarize what changed.
7. State tests executed and their result.
8. State unresolved issues or follow-up work.

Never hide unfinished work.

---

# First Development Session

If this repository only contains the initial documentation, begin with **Step 0 — Project Bootstrap** from `ROADMAP.md`.

Expected first development sequence:

```text
Python project initialization
        |
        v
FastAPI application
        |
        v
GET /health
        |
        v
PostgreSQL with Docker Compose
        |
        v
SQLAlchemy connection
        |
        v
Alembic initialization
        |
        v
Basic tests
        |
        v
Create CURRENT.md
```

Do not implement authentication, AWS infrastructure, imports, or search during the initial milestone unless explicitly instructed by the user.
