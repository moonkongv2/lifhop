from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.models.entry import Entry
from app.schemas.codex_session import ArchiveItem, ArchiveResponse, SessionSummary, SessionTurnsResponse, TurnSummary
from app.services.github_repositories import CTES as GITHUB_CTES
from app.schemas.github_record import GitHubRepositorySummary

# Group from the selected current version only. IDs from other versions do not
# create phantom sessions or bypass owner scoping.
BASE = """
WITH base AS (
 SELECT e.id, e.title, e.created_at, e.event_at, e.current_version_id,
 e.provider, e.source_scope, e.review_required,
 v.source_updated_at, v.completeness,
 CASE WHEN jsonb_typeof(v.payload->'thread_name')='string'
   THEN left(v.payload->>'thread_name',255) END AS thread_name,
 CASE WHEN jsonb_typeof(v.payload->'thread_id') = 'string'
   AND length(v.payload->>'thread_id') BETWEEN 1 AND 1024
   THEN v.payload->>'thread_id' END AS thread_id,
 CASE WHEN (v.payload->>'turn_position') ~ '^[0-9]{1,9}$'
   THEN (v.payload->>'turn_position')::integer END AS position,
 v.payload->>'forked_from_id' AS fork,
 CASE WHEN v.payload->>'archived' IN ('true','false')
   THEN (v.payload->>'archived')::boolean END AS archived
 FROM entries e LEFT JOIN entry_versions v ON v.id=e.current_version_id AND v.entry_id=e.id
 WHERE e.user_id=:owner
), groups AS (
 SELECT source_scope, thread_id, count(*) AS turn_count,
 max(created_at) AS sort_time, max(id) AS sort_id,
 min(event_at) AS start_at, max(coalesce(source_updated_at,event_at)) AS end_at,
 bool_or(coalesce(completeness,'unknown') <> 'complete') AS partial,
 bool_or(review_required) AS review_required,
 count(position) <> count(*) OR count(DISTINCT position) <> count(*) AS order_unknown,
 CASE WHEN count(DISTINCT archived)=1 THEN bool_and(archived) END AS archived,
 CASE WHEN count(DISTINCT fork)=1 THEN min(fork) END AS forked_from_id,
 count(DISTINCT archived)>1 OR count(DISTINCT fork)>1 AS metadata_conflict
 FROM base WHERE provider='codex' AND thread_id IS NOT NULL GROUP BY source_scope,thread_id
), summaries AS (
 SELECT g.*, NOT EXISTS(SELECT 1 FROM base n WHERE n.provider='codex'
   AND n.source_scope=g.source_scope AND n.thread_id=g.thread_id
   AND nullif(trim(n.thread_name),'') IS NOT NULL) AS title_inferred,
 EXISTS(SELECT 1 FROM groups parent WHERE parent.source_scope=g.source_scope AND parent.thread_id=g.forked_from_id) AS fork_available,
 (SELECT n.thread_name FROM base n WHERE n.provider='codex' AND n.source_scope=g.source_scope
   AND n.thread_id=g.thread_id AND nullif(trim(n.thread_name),'') IS NOT NULL
   ORDER BY n.source_updated_at DESC NULLS LAST,n.id DESC LIMIT 1) AS saved_title,
 (SELECT b.title FROM base b WHERE b.provider='codex' AND b.source_scope=g.source_scope AND b.thread_id=g.thread_id
  ORDER BY CASE WHEN NOT g.order_unknown THEN b.position END ASC NULLS LAST,b.id ASC LIMIT 1) AS first_question
 FROM groups g
)
"""


def summary(row):
    data = dict(row)
    question = " ".join((data.get("first_question") or "").split())
    name = " ".join((data.get("saved_title") or "").split())
    title = name or question or "Codex session"
    data["title"] = title[:60].rstrip() + "…" if len(title) > 60 else title
    data["preview_text"] = question
    return SessionSummary.model_validate(data)


def archive(db: Session, owner: int, limit: int, offset: int):
    feed = ", " + GITHUB_CTES + """, feed AS (
      SELECT 'codex_session' AS kind, NULL::integer AS entry_id, source_scope,thread_id,sort_time,sort_id FROM summaries
      UNION ALL SELECT 'github_repository',NULL,source_scope,NULL,sort_time,sort_id FROM gh_repositories
      UNION ALL SELECT 'entry',id,NULL,NULL,created_at,id FROM base
      WHERE (provider IS DISTINCT FROM 'codex' OR thread_id IS NULL)
        AND NOT coalesce(provider='github' AND source_scope ~ '^repo:[1-9][0-9]{0,19}$',false)
    ) """
    total = db.scalar(text(BASE + feed + "SELECT count(*) FROM feed"), {"owner": owner})
    rows = db.execute(text(BASE + feed + "SELECT f.kind,f.entry_id,s.*,to_jsonb(r) AS repository_data FROM feed f LEFT JOIN summaries s USING(source_scope,thread_id) LEFT JOIN gh_repositories r ON f.kind='github_repository' AND r.source_scope=f.source_scope ORDER BY f.sort_time DESC,f.sort_id DESC LIMIT :limit OFFSET :offset"),
        {"owner": owner, "limit": limit, "offset": offset}).mappings().all()
    entries = {e.id: e for e in db.scalars(select(Entry).where(Entry.user_id == owner,
        Entry.id.in_([r["entry_id"] for r in rows if r["kind"] == "entry"]))) }
    items = [ArchiveItem(kind=row["kind"], entry=entries[row["entry_id"]] if row["kind"] == "entry" else None,
        session=summary(row) if row["kind"] == "codex_session" else None,
        repository=GitHubRepositorySummary.model_validate(row["repository_data"]) if row["kind"] == "github_repository" else None) for row in rows]
    return ArchiveResponse(items=items, total=total, limit=limit, offset=offset)


def session_turns(db: Session, owner: int, scope: str, thread: str, limit: int, offset: int, focus: int | None):
    args = {"owner": owner, "scope": scope, "thread": thread, "limit": limit, "offset": offset}
    row = db.execute(text(BASE + "SELECT * FROM summaries WHERE source_scope=:scope AND thread_id=:thread"), args).mappings().first()
    if row is None:
        raise HTTPException(404, "No retained turns in this session")
    session = summary(row)
    ordered = """, ordered AS (
      SELECT b.*,row_number() OVER (ORDER BY """ + ("position ASC,id ASC" if not session.order_unknown else "event_at ASC NULLS LAST,id ASC") + """)-1 AS rank
      FROM base b WHERE provider='codex' AND source_scope=:scope AND thread_id=:thread
    ) """
    missing = False
    if focus is not None:
        args["focus"] = focus
        rank = db.scalar(text(BASE + ordered + "SELECT rank FROM ordered WHERE id=:focus"), args)
        missing = rank is None
        args["offset"] = (int(rank) // limit) * limit if rank is not None else 0
    elif offset >= session.turn_count:
        args["offset"] = ((session.turn_count - 1) // limit) * limit
    turns = db.execute(text(BASE + ordered + "SELECT o.id,o.title,o.event_at,o.current_version_id,left(coalesce(e.primary_content,e.content,''),1000) AS preview_text FROM ordered o JOIN entries e ON e.id=o.id AND e.user_id=:owner ORDER BY o.rank LIMIT :limit OFFSET :offset"), args).mappings().all()
    return SessionTurnsResponse(session=session, items=[TurnSummary.model_validate(dict(r)) for r in turns],
        total=session.turn_count, limit=limit, offset=args["offset"], focus_missing=missing)
