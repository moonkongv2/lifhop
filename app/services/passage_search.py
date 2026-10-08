"""Owner-scoped, current-only retrieval. No remote model or lazy writes."""
import json
import re
from functools import reduce
from sqlalchemy import String, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.entry import Entry
from app.models.history import EntryVersion
from app.models.passage import EntryPassage, PassageIndexState
from app.schemas.passage import PassageLocation, PassageResponse, PassageSearchResponse, PassageSnapshotsResponse
from app.services.codex_presentation import session_ref
from app.services.entry_search import search_components
from app.services.github_repositories import METADATA, DISCUSSION_METADATA, METADATA_NAMES, repository_ref
from app.services.passage_index import PROJECTION_VERSION, text_hash
from sqlalchemy import literal_column

SEARCH_VERSION = "local-passages-v1"
STOPWORDS = frozenset("a an the is are was were be been being do does did how what why when where which who to of for in on at and or with my our i we it this that".split())
CONFIGURATION_HASH = text_hash(json.dumps([SEARCH_VERSION, PROJECTION_VERSION, sorted(STOPWORDS), 16, 2, 5, 2000]))


def query_tokens(q: str) -> list[str]:
    return list(dict.fromkeys(token.casefold() for token in re.findall(r"[^\W_]+(?:[_./:-][^\W_]+)*", q)
        if token.casefold() not in STOPWORDS))[:16]


def eligible_conditions(user_id: int, filters: dict):
    conditions, _, _, _ = search_components(user_id=user_id, **filters)
    if filters.get("source_state") is None:
        conditions.append(Entry.source_state != "deleted")
    conditions.extend([Entry.current_version_id == EntryVersion.id, EntryVersion.entry_id == Entry.id,
        EntryPassage.version_id == EntryVersion.id, EntryPassage.projection_version == PROJECTION_VERSION,
        PassageIndexState.entry_id == Entry.id, PassageIndexState.indexed_version_id == EntryVersion.id,
        PassageIndexState.content_hash == EntryVersion.content_hash,
        PassageIndexState.projection_version == PROJECTION_VERSION,
        PassageIndexState.status.in_(["ready", "partial"])])
    if not filters.get("include_work_commentary"):
        conditions.append(EntryPassage.work_only.is_(False))
    return conditions


def candidate_query(user_id: int, q: str, filters: dict):
    conditions = eligible_conditions(user_id, filters)
    escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    phrase = EntryPassage.text.ilike(f"%{escaped}%", escape="\\")
    tokens = [func.plainto_tsquery("simple", token) for token in query_tokens(q)]
    token_matches = [EntryPassage.search_vector.op("@@")(token) for token in tokens]
    query = reduce(lambda a, b: a.op("||")(b), tokens) if tokens else None
    conditions.append(or_(phrase, EntryPassage.search_vector.op("@@")(query)) if query is not None else phrase)
    token_count = sum((case((matched, 1), else_=0) for matched in token_matches), literal(0))
    body = EntryPassage.field == "content"
    return select(EntryPassage.id, EntryPassage.version_id, Entry.id.label("entry_id"),
        Entry.event_at, EntryPassage.field, EntryPassage.start, EntryPassage.end, EntryPassage.passage_hash,
        func.coalesce(EntryPassage.group_key, literal("p:") + cast(EntryPassage.id, String)).label("group_id"),
        case((phrase & body, 3), (phrase, 1), else_=0).label("phrase_score"),
        case((body, token_count), else_=0).label("body_tokens"),
        (func.ts_rank_cd(EntryPassage.search_vector, query) if query is not None else literal(0)).label("relevance"),
    ).select_from(EntryPassage).join(EntryVersion, EntryVersion.id == EntryPassage.version_id).join(
        Entry, Entry.id == EntryVersion.entry_id).join(PassageIndexState, PassageIndexState.entry_id == Entry.id).where(*conditions)


def score_order(c):
    return [c.phrase_score.desc(), c.body_tokens.desc(), c.relevance.desc(), c.event_at.desc().nulls_last(), c.entry_id.desc(), c.id.asc()]


def display_query(base):
    # Group before Entry quotas and pagination. No unbounded body materialization.
    ranked = select(base, func.row_number().over(partition_by=base.c.group_id,
        order_by=[base.c.event_at.desc().nulls_last(), base.c.entry_id.desc(), base.c.id.asc()]).label("group_rank"),
        func.count().over(partition_by=base.c.group_id).label("alias_total")).cte("grouped_passages")
    representatives = select(ranked).where(ranked.c.group_rank == 1).cte("representatives")
    limited = select(representatives, func.row_number().over(partition_by=representatives.c.entry_id,
        order_by=score_order(representatives.c)).label("entry_rank")).cte("limited_passages")
    return select(limited).where(limited.c.entry_rank <= 2)


def coverage(db: Session, user_id: int) -> dict[str, int]:
    status = case((PassageIndexState.indexed_version_id == Entry.current_version_id,
        case((PassageIndexState.projection_version == PROJECTION_VERSION, PassageIndexState.status), else_="pending")), else_="pending")
    return dict(db.execute(select(status, func.count()).select_from(Entry).outerjoin(
        PassageIndexState, PassageIndexState.entry_id == Entry.id).where(Entry.user_id == user_id).group_by(status)).all())


def read_passage(db: Session, user_id: int, passage_id: int) -> PassageResponse:
    version = EntryVersion.__table__.alias("v")
    # Compare the stored text with its pinned source range inside PostgreSQL;
    # only a bounded slice and metadata leave the database, even for huge records.
    source = case((EntryPassage.field == "title", version.c.title), else_=version.c.content)
    row = db.execute(select(EntryPassage, Entry.id.label("entry_id"), Entry.title,
        Entry.provider, Entry.source_scope, Entry.external_id, Entry.created_at, Entry.event_at,
        Entry.source_state, version.c.completeness, PassageIndexState.status, PassageIndexState.gap_codes,
        case(((func.jsonb_typeof(version.c.payload["thread_id"]) == "string") &
            (func.length(version.c.payload["thread_id"].astext) <= 1024), version.c.payload["thread_id"].astext), else_=None).label("thread_id"),
        *[literal_column(column) for column in (METADATA.rstrip() + ",\n" + DISCUSSION_METADATA.strip()).strip().split(",\n")])
        .select_from(EntryPassage).join(version, version.c.id == EntryPassage.version_id)
        .join(Entry, (Entry.id == version.c.entry_id) & (Entry.current_version_id == version.c.id))
        .join(PassageIndexState, PassageIndexState.entry_id == Entry.id)
        .where(EntryPassage.id == passage_id, Entry.user_id == user_id,
            func.length(EntryPassage.text) <= 2000,
            EntryPassage.projection_version == PROJECTION_VERSION,
            PassageIndexState.projection_version == PROJECTION_VERSION,
            PassageIndexState.indexed_version_id == version.c.id,
            PassageIndexState.content_hash == version.c.content_hash,
            PassageIndexState.status.in_(["ready", "partial"]),
            EntryPassage.text == func.substring(source, EntryPassage.start + 1, EntryPassage.end - EntryPassage.start))).first()
    if row is None or text_hash(row[0].text) != row[0].passage_hash:
        raise HTTPException(404, "Passage unavailable. Run your search again.")
    p = row[0]
    metadata = dict(zip(METADATA_NAMES, row[13:]))
    return PassageResponse(id=p.id, entry_id=row.entry_id, version_id=p.version_id, field=p.field,
        start=p.start, end=p.end, passage_hash=p.passage_hash, title=row.title, text=p.text,
        source=row.provider or "unknown", created_at=row.created_at, event_at=row.event_at,
        source_state=row.source_state, completeness=row.completeness, index_status=row.status,
        gap_codes=row.gap_codes.split(",") if row.gap_codes else [], work_only=p.work_only,
        projection_version=p.projection_version,
        session_ref=session_ref(row.provider, row.source_scope, {"thread_id": row.thread_id}),
        repository_ref=repository_ref(row.provider, row.source_scope, metadata, row.external_id))


def aliases_for(db: Session, base, group_id: str, limit: int, offset: int = 0):
    rows = db.execute(select(base).where(base.c.group_id == group_id).order_by(
        base.c.event_at.desc().nulls_last(), base.c.entry_id.desc(), base.c.id.asc()).limit(limit).offset(offset)).mappings()
    return [PassageLocation.model_validate(dict(row)) for row in rows]


def ranked_passages(db: Session, user_id: int, q: str, filters: dict, limit: int = 20, offset: int = 0):
    base = candidate_query(user_id, q, filters).cte("passage_candidates")
    display = display_query(base).cte("display_passages")
    total = db.scalar(select(func.count()).select_from(display)) or 0
    rows = db.execute(select(display).order_by(*score_order(display.c)).offset(offset).limit(limit)).mappings().all()
    return base, rows, total


def search_passages(db: Session, *, user_id: int, q: str, limit: int = 20, offset: int = 0, **filters) -> PassageSearchResponse:
    if not q.strip() or len(q) > 256 or not 1 <= limit <= 50 or offset < 0:
        raise HTTPException(422, "Enter a query of 1–256 characters and a valid page.")
    base, rows, total = ranked_passages(db, user_id, q, filters, limit, offset)
    items = []
    for row in rows:
        item = read_passage(db, user_id, row["id"])
        item.alias_total = row["alias_total"]
        item.aliases = aliases_for(db, base, row["group_id"], 5)
        item.snapshot_count = db.scalar(select(func.count(func.distinct(base.c.entry_id))).where(base.c.group_id == row["group_id"])) or 1
        items.append(item)
    result = PassageSearchResponse(items=items, total=total, limit=limit, offset=offset,
        coverage=coverage(db, user_id), search_version=SEARCH_VERSION, projection_version=PROJECTION_VERSION,
        configuration_hash=CONFIGURATION_HASH)
    if len(result.model_dump_json().encode()) > 1024 * 1024:
        raise HTTPException(503, "search_response_budget")
    return result


def search_snapshots(db: Session, *, user_id: int, passage_id: int, q: str, limit: int = 20, offset: int = 0, **filters):
    read_passage(db, user_id, passage_id)
    base = candidate_query(user_id, q, filters).cte("alias_candidates")
    group_id = db.scalar(select(base.c.group_id).where(base.c.id == passage_id))
    if group_id is None:
        raise HTTPException(404, "Passage is outside this search.")
    total = db.scalar(select(func.count()).select_from(base).where(base.c.group_id == group_id)) or 0
    return PassageSnapshotsResponse(items=aliases_for(db, base, group_id, limit, offset),
        total=total, limit=limit, offset=offset)
