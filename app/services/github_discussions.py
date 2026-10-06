"""Owner-scoped discussion grouping over bounded current-version metadata."""
from fastapi import HTTPException
from sqlalchemy import text
from app.schemas.github_record import (GitHubDiscussionSummary, GitHubDiscussionRecord,
    GitHubDiscussionsResponse, GitHubThreadResponse)
from app.services.github_repositories import CTES, repository_summary, record_summary

THREAD_CTES = CTES + """, gh_threads AS (
 SELECT *, substring(payload_kind from 8) AS discussion_kind,
 CASE WHEN payload_kind IN ('github_pull_request','github_issue')
 THEN substring(payload_kind from 8) ELSE parent_kind END AS group_kind,
 CASE WHEN payload_kind IN ('github_pull_request','github_issue')
 THEN object_id ELSE parent_id END AS group_id,
 payload_kind IN ('github_pull_request','github_issue') AS is_root
 FROM gh_records WHERE record_kind='discussion'
), gh_groups AS (
 SELECT source_scope,group_kind AS parent_kind,group_id AS parent_id,
 max(object_number) AS number,max(id) FILTER(WHERE is_root) AS root_entry_id,
 max(title) FILTER(WHERE is_root) AS title,
 coalesce(max(object_state) FILTER(WHERE is_root),'unknown') AS state,
 CASE WHEN bool_or(is_root) THEN max(event_at) FILTER(WHERE is_root)
 ELSE min(event_at) END AS event_at,
 NOT bool_or(is_root) AS orphan,count(*) FILTER(WHERE NOT is_root) AS child_count,
 bool_or(coalesce(completeness,'unknown')<>'complete') AS partial,
 bool_or(review_required) AS review_required
 FROM gh_threads GROUP BY source_scope,group_kind,group_id
)"""


def discussion_summary(row):
    data = dict(row)
    title = data["title"] or f"{'PR' if data['parent_kind'] == 'pull_request' else 'Issue'} #{data['number']} — Parent not retained"
    title = " ".join(title.split())
    data["title"] = title[:100].rstrip() + "…" if len(title) > 100 else title
    return GitHubDiscussionSummary.model_validate(data)


def discussion_list(db, owner, scope, kind, state, date_from, date_to, unknown_date, limit, offset):
    from app.services.entry_search import date_boundary
    from datetime import timedelta
    repository_summary(db, owner, scope)
    args = dict(owner=owner, scope=scope, kind=kind, state=state, limit=limit, offset=offset)
    where = " FROM gh_groups WHERE source_scope=:scope"
    if kind:
        where += " AND parent_kind=:kind"
    if state:
        where += " AND state=:state"
    if unknown_date:
        where += " AND event_at IS NULL"
    if date_from:
        where += " AND event_at>=:date_from"
        args["date_from"] = date_boundary(date_from)
    if date_to:
        where += " AND event_at<:date_to"
        args["date_to"] = date_boundary(date_to + timedelta(days=1))
    total = db.scalar(text("WITH " + THREAD_CTES + " SELECT count(*)" + where), args)
    rows = db.execute(text("WITH " + THREAD_CTES + " SELECT *" + where +
        ' ORDER BY event_at DESC NULLS LAST,parent_kind COLLATE "C",parent_id COLLATE "C" LIMIT :limit OFFSET :offset'), args).mappings()
    return GitHubDiscussionsResponse(items=[discussion_summary(row) for row in rows], total=total, limit=limit, offset=offset)


def thread_records(db, owner, scope, kind, parent_id, limit, offset, focus_entry_id=None):
    args = dict(owner=owner, scope=scope, kind=kind, parent_id=parent_id, limit=limit, offset=offset)
    group = " WHERE source_scope=:scope AND parent_kind=:kind AND parent_id=:parent_id"
    row = db.execute(text("WITH " + THREAD_CTES + " SELECT * FROM gh_groups" + group), args).mappings().first()
    if row is None:
        raise HTTPException(404, "Discussion not retained")
    where = " FROM gh_threads WHERE source_scope=:scope AND group_kind=:kind AND group_id=:parent_id AND NOT is_root"
    order = ' ORDER BY event_at ASC NULLS LAST,external_id COLLATE "C",id'
    if focus_entry_id is not None and focus_entry_id != row["root_entry_id"]:
        args["focus"] = focus_entry_id
        focused = db.scalar(text("WITH " + THREAD_CTES + ", ranked AS (SELECT id,row_number() OVER(" +
            order + ")-1 AS position" + where + ") SELECT position FROM ranked WHERE id=:focus"), args)
        if focused is None:
            raise HTTPException(404, "Focused record is not retained in this discussion")
        offset = args["offset"] = focused // limit * limit
    total = db.scalar(text("WITH " + THREAD_CTES + " SELECT count(*)" + where), args)
    rows = db.execute(text("WITH " + THREAD_CTES + " SELECT *" + where + order + " LIMIT :limit OFFSET :offset"), args).mappings()
    items = [GitHubDiscussionRecord(**record_summary(row).model_dump(), kind=row["discussion_kind"]) for row in rows]
    return GitHubThreadResponse(discussion=discussion_summary(row), items=items, total=total, limit=limit, offset=offset)
