import re
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas.github_record import (GitHubRepositoryRef, GitHubRepositorySummary,
    GitHubRecordSummary, GitHubRecordsResponse, GitHubDocumentSummary, GitHubDocumentsResponse)

# Only bounded metadata leaves PostgreSQL. Never fetch diff/document bodies for browsing.
METADATA = """
CASE WHEN jsonb_typeof(v.payload->'repository_id')='number'
 AND (v.payload->>'repository_id') ~ '^[1-9][0-9]{0,19}$'
 THEN v.payload->>'repository_id' END AS repository_id,
CASE WHEN jsonb_typeof(v.payload->'repository')='string'
 AND length(v.payload->>'repository') <= 255
 AND (v.payload->>'repository') ~ '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
 THEN v.payload->>'repository' END AS repository,
CASE WHEN jsonb_typeof(v.payload->'sha')='string'
 AND (v.payload->>'sha') ~ '^[a-f0-9]{40}$' THEN v.payload->>'sha' END AS sha,
left(v.payload->>'kind',40) AS payload_kind,
CASE WHEN jsonb_typeof(v.payload->'path')='string'
 AND length(v.payload->>'path') BETWEEN 1 AND 4096
 AND (v.payload->>'path') !~ '(^/|//|/$|(^|/)[.]{1,2}(/|$)|[[:cntrl:]])'
 THEN v.payload->>'path' END AS path
"""

CTES = """gh_base AS (
 SELECT e.id,e.title,e.created_at,e.event_at,e.current_version_id,e.source_scope,
 e.source_state,e.review_required,v.observed_at,v.completeness,
 """ + METADATA + """
 FROM entries e LEFT JOIN entry_versions v ON v.id=e.current_version_id AND v.entry_id=e.id
 WHERE e.user_id=:owner AND e.provider='github' AND e.source_scope ~ '^repo:[1-9][0-9]{0,19}$'
), gh_records AS (
 SELECT *, CASE WHEN source_scope='repo:'||repository_id AND sha IS NOT NULL
   AND payload_kind='github_commit' THEN 'commit'
   WHEN source_scope='repo:'||repository_id AND sha IS NOT NULL
   AND payload_kind='github_document' AND path IS NOT NULL THEN 'document'
   ELSE 'unclassified' END AS record_kind
 FROM gh_base
), gh_repositories AS (
 SELECT source_scope, max(created_at) AS sort_time,max(id) AS sort_id,
 count(*) FILTER (WHERE record_kind='commit') AS commit_count,
 count(DISTINCT path) FILTER (WHERE record_kind='document') AS document_count,
 count(*) FILTER (WHERE record_kind='document') AS snapshot_count,
 count(*) FILTER (WHERE record_kind='unclassified') AS unclassified_count,
 count(*) FILTER (WHERE event_at IS NULL) AS unknown_date_count,
 min(event_at) AS start_at,max(event_at) AS end_at,
 bool_or(coalesce(completeness,'unknown') <> 'complete' OR record_kind='unclassified') AS partial,
 bool_or(review_required) AS review_required,
 (array_agg(repository ORDER BY observed_at DESC NULLS LAST,id DESC)
   FILTER (WHERE repository IS NOT NULL AND source_scope='repo:'||repository_id))[1] AS repository
 FROM gh_records GROUP BY source_scope
)"""


def repository_ref(provider, scope, metadata):
    if provider != "github" or not re.fullmatch(r"repo:[1-9][0-9]{0,19}", scope or ""):
        return None
    data = dict(metadata)
    match = scope == f"repo:{data.get('repository_id')}"
    kind = "unclassified"
    if match and data.get("sha"):
        if data.get("payload_kind") == "github_commit":
            kind = "commit"
        elif data.get("payload_kind") == "github_document" and data.get("path"):
            kind = "document"
    return GitHubRepositoryRef(source_scope=scope, repository=data.get("repository") if match else None,
        kind=kind, path=data.get("path") if kind == "document" else None)


def repository_summaries(db: Session, owner: int, scopes: list[str]):
    rows = db.execute(text("WITH " + CTES + " SELECT * FROM gh_repositories WHERE source_scope=ANY(:scopes)"),
        {"owner": owner, "scopes": scopes}).mappings()
    return {r["source_scope"]: GitHubRepositorySummary.model_validate(dict(r)) for r in rows}


def repository_summary(db: Session, owner: int, scope: str):
    result = repository_summaries(db, owner, [scope]).get(scope)
    if result is None:
        raise HTTPException(404, "No retained records in this repository")
    return result


def record_summary(row):
    data = dict(row)
    title = " ".join((data["title"].splitlines() or [""])[0].split()) or "Untitled record"
    data["title"] = title[:100].rstrip() + "…" if len(title) > 100 else title
    data["partial"] = data["completeness"] != "complete" or data["record_kind"] == "unclassified"
    return GitHubRecordSummary.model_validate(data)


def repository_records(db: Session, owner: int, scope: str, kind: str, limit: int, offset: int, path: str | None = None):
    repository_summary(db, owner, scope)
    args = {"owner": owner, "scope": scope, "kind": kind, "path": path, "limit": limit, "offset": offset}
    where = " FROM gh_records WHERE source_scope=:scope AND record_kind=:kind"
    if path is not None:
        where += " AND path=:path"
    total = db.scalar(text("WITH " + CTES + " SELECT count(*)" + where), args)
    rows = db.execute(text("WITH " + CTES + " SELECT *" + where +
        " ORDER BY event_at DESC NULLS LAST,id DESC LIMIT :limit OFFSET :offset"), args).mappings()
    return GitHubRecordsResponse(items=[record_summary(r) for r in rows], total=total, limit=limit, offset=offset)


def repository_documents(db: Session, owner: int, scope: str, limit: int, offset: int):
    repository_summary(db, owner, scope)
    args = {"owner": owner, "scope": scope, "limit": limit, "offset": offset}
    ranked = ", gh_documents AS (SELECT *,count(*) OVER(PARTITION BY path) AS snapshot_count," \
        " row_number() OVER(PARTITION BY path ORDER BY event_at DESC NULLS LAST,id DESC) AS rank" \
        " FROM gh_records WHERE source_scope=:scope AND record_kind='document')"
    total = db.scalar(text("WITH " + CTES + ranked + " SELECT count(*) FROM gh_documents WHERE rank=1"), args)
    rows = db.execute(text("WITH " + CTES + ranked +
        ' SELECT * FROM gh_documents WHERE rank=1 ORDER BY path COLLATE "C" LIMIT :limit OFFSET :offset'), args).mappings()
    return GitHubDocumentsResponse(items=[GitHubDocumentSummary(path=r["path"], snapshot_count=r["snapshot_count"],
        latest=record_summary(r)) for r in rows], total=total, limit=limit, offset=offset)
