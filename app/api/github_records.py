from typing import Annotated, Literal
from datetime import date
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.db import get_db
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.models.user import User
from app.importers.canonical import GitHubCommitPayload, GitHubDocumentPayload, GitHubEvidence
from app.importers.github_discussions import (GitHubDiscussionPayload, GitHubPullRequestPayload,
    GitHubReviewPayload, GitHubReviewCommentPayload, discussion_locator)
from app.schemas.github_record import GitHubPresentation, GitHubRelatedRecord
from app.schemas.github_record import (RepositoryScope, GitHubRepositorySummary,
    GitHubRecordsResponse, GitHubDocumentsResponse, GitHubDiscussionsResponse, GitHubThreadResponse, GitHubCommitLink)
from app.services.github_repositories import repository_summary, repository_records, repository_documents
from app.services.github_discussions import discussion_list, thread_records

router = APIRouter(tags=["github-records"])
DB = Annotated[Session, Depends(get_db)]
Owner = Annotated[User, Depends(get_current_user)]
Scope = Annotated[RepositoryScope, Query()]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=9007199254740991)]


@router.get("/github-repositories", response_model=GitHubRepositorySummary)
def read_repository(db: DB, owner: Owner, scope: Scope):
    return repository_summary(db, owner.id, scope)


@router.get("/github-repositories/records", response_model=GitHubRecordsResponse)
def read_records(db: DB, owner: Owner, scope: Scope, kind: Literal["commit", "unclassified"] = "commit",
                 limit: Limit = 20, offset: Offset = 0):
    return repository_records(db, owner.id, scope, kind, limit, offset)


@router.get("/github-repositories/documents", response_model=GitHubDocumentsResponse)
def read_documents(db: DB, owner: Owner, scope: Scope, limit: Limit = 20, offset: Offset = 0):
    return repository_documents(db, owner.id, scope, limit, offset)


@router.get("/github-repositories/document-snapshots", response_model=GitHubRecordsResponse)
def read_snapshots(db: DB, owner: Owner, scope: Scope,
                   path: Annotated[str, Query(min_length=1, max_length=4096)], limit: Limit = 20, offset: Offset = 0):
    # Reuse the canonical path validator without constructing a document body.
    try:
        GitHubDocumentPayload.relative_path(path)
    except ValueError:
        raise HTTPException(422, "Invalid repository-relative path")
    return repository_records(db, owner.id, scope, "document", limit, offset, path)


@router.get("/github-repositories/discussions", response_model=GitHubDiscussionsResponse)
def read_discussions(db: DB, owner: Owner, scope: Scope, kind: Literal["pull_request", "issue"] | None = None,
                     state: Literal["open", "closed", "merged", "unknown"] | None = None,
                     date_from: date | None = None, date_to: date | None = None, unknown_date: bool = False,
                     limit: Limit = 20, offset: Offset = 0):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Invalid date range")
    if date_to == date.max:
        raise HTTPException(422, "Date range is outside supported bounds")
    if unknown_date and (date_from or date_to):
        raise HTTPException(422, "Unknown date cannot be combined with a date range")
    return discussion_list(db, owner.id, scope, kind, state, date_from, date_to, unknown_date, limit, offset)


@router.get("/github-repositories/discussions/{parent_kind}/{parent_id}", response_model=GitHubThreadResponse)
def read_thread(parent_kind: Literal["pull_request", "issue"], parent_id: str,
                db: DB, owner: Owner, scope: Scope, limit: Limit = 20, offset: Offset = 0,
                focus_entry_id: Annotated[int | None, Query(ge=1)] = None):
    import re
    if not re.fullmatch(r"[1-9][0-9]{0,19}", parent_id):
        raise HTTPException(422, "Invalid GitHub parent object ID")
    return thread_records(db, owner.id, scope, parent_kind, parent_id, limit, offset, focus_entry_id)


@router.get("/entries/{entry_id}/github-presentation", response_model=GitHubPresentation)
def presentation(entry_id: int, db: Annotated[Session, Depends(get_db)],
                 owner: Annotated[User, Depends(get_current_user)]):
    entry = db.scalar(select(Entry).where(Entry.id == entry_id, Entry.user_id == owner.id))
    if entry is None or entry.provider != "github":
        raise HTTPException(404, "GitHub record not found")
    version = db.scalar(select(EntryVersion).where(EntryVersion.id == entry.current_version_id,
                                                  EntryVersion.entry_id == entry.id))
    payload = None
    try:
        if version:
            payload = TypeAdapter(GitHubEvidence).validate_python(version.payload)
            if entry.source_scope != f"repo:{payload.repository_id}":
                payload = None
    except ValidationError:
        pass  # Legacy canonical documents still use the plain reader.
    related, locator, more, commit_links = [], None, False, []
    if payload:
        if isinstance(payload, GitHubDiscussionPayload):
            locator = discussion_locator(payload)
            roles = {}
            if isinstance(payload, GitHubPullRequestPayload):
                for role, sha in (("base",payload.base_sha),("head",payload.head_sha),("merge",payload.merge_sha)):
                    if sha:
                        roles.setdefault(sha, []).append(role)
                for sha in payload.commits:
                    roles.setdefault(sha, []).append("PR member")
            if isinstance(payload, (GitHubReviewPayload, GitHubReviewCommentPayload)) and payload.commit_id:
                roles.setdefault(payload.commit_id, []).append("review")
            if isinstance(payload, GitHubReviewCommentPayload) and payload.original_commit_id:
                roles.setdefault(payload.original_commit_id, []).append("original review")
            retained = dict(db.execute(select(EntryVersion.payload["sha"].astext, Entry.id)
                .join(Entry, (Entry.current_version_id == EntryVersion.id) & (EntryVersion.entry_id == Entry.id))
                .where(Entry.user_id == owner.id, Entry.provider == "github", Entry.source_scope == entry.source_scope,
                    EntryVersion.payload["kind"].astext == "github_commit", EntryVersion.payload["repository_id"].astext == str(payload.repository_id),
                    EntryVersion.payload["sha"].astext.in_(list(roles)))).all()) if roles else {}
            commit_links = [GitHubCommitLink(sha=sha,roles=names,entry_id=retained.get(sha),
                locator=f"https://github.com/{payload.repository}/commit/{sha}") for sha,names in roles.items()]
            return GitHubPresentation(entry_id=entry.id, version_id=entry.current_version_id, payload=payload,
                locator=locator, related=[], related_has_more=False, commit_links=commit_links)
        import re
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", payload.repository):
            base = "https://github.com/" + payload.repository
            locator = base + ("/commit/" + payload.sha if isinstance(payload, GitHubCommitPayload)
                              else "/blob/" + payload.sha + "/" + quote(payload.path, safe="/"))
        rows = db.execute(select(Entry.id, Entry.title, EntryVersion.payload["kind"].astext)
            .join(EntryVersion, Entry.current_version_id == EntryVersion.id)
            .where(Entry.user_id == owner.id, Entry.provider == "github", Entry.source_scope == entry.source_scope,
                   Entry.id != entry.id, EntryVersion.entry_id == Entry.id,
                   EntryVersion.payload["sha"].astext == payload.sha)
            .order_by(Entry.id).limit(101)).all()
        more = len(rows) > 100
        related = [GitHubRelatedRecord(id=id, title=title, kind=kind) for id, title, kind in rows[:100]]
    return GitHubPresentation(entry_id=entry.id, version_id=entry.current_version_id,
                              payload=payload, locator=locator, related=related, related_has_more=more)
