"""Exact current allowed cosine retrieval; no query persistence or provider call."""
from fastapi import HTTPException
from sqlalchemy import String, case, cast, func, literal, select
from app.models.embedding_job import EmbeddingJob, EmbeddingRun
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage
from app.models.passage_embedding import PassageEmbedding as Vector
from app.models.user import User
from app.schemas.semantic import SemanticCoverage, SemanticHit, SemanticLocation, SemanticLocations, SemanticResponse
from app.services.embedding_jobs import allowed_selection
from app.services.embedding_store import eligible_embeddings
from app.services.entry_search import search_components
from app.services.passage_index import text_hash
from app.services.passage_search import read_passage


def filtered_vectors(owner_id, filters):
    conditions, _, _, _ = search_components(user_id=owner_id, **filters)
    return eligible_embeddings(owner_id).where(*conditions)


def index_coverage(db, owner_id, filters, config):
    conditions, _, _, _ = search_components(user_id=owner_id, **filters)
    selection = select(Entry.id).where(*conditions, Entry.source_state != "deleted")
    matched = db.scalar(select(func.count()).select_from(selection.subquery()))
    permitted = selection.join(SourcePolicy, (SourcePolicy.user_id == Entry.user_id) &
        (SourcePolicy.provider == func.coalesce(Entry.provider, "unknown")) & (SourcePolicy.scope == Entry.source_scope))
    allowed = db.scalar(select(func.count()).select_from(permitted.where(*allowed_selection(owner_id)).subquery()))
    vectors = filtered_vectors(owner_id, filters).with_only_columns(Vector.id, Entry.id.label("entry_id")).subquery()
    ready, records = db.execute(select(func.count(), func.count(func.distinct(vectors.c.entry_id))).select_from(vectors)).one()
    jobs = dict(db.execute(select(EmbeddingJob.status, func.count()).join(EmbeddingRun).where(
        EmbeddingRun.owner_id == owner_id, EmbeddingJob.entry_id.in_(selection)).group_by(EmbeddingJob.status)).all())
    state = "available" if ready else "indexing" if jobs.get("pending", 0) or jobs.get("running", 0) else "unindexed"
    if config.embedding_mode != "openai" or config.embedding_monthly_limit_micro_usd == 0:
        state = "disabled"
    elif not config.openai_api_key:
        state = "unavailable"
    return SemanticCoverage(state=state, matched_records=matched, allowed_records=allowed,
        indexed_records=records, ready_slices=ready, jobs=jobs,
        policy_revision=db.scalar(select(User.policy_revision).where(User.id == owner_id)))


def group_key():
    # group_key presence certifies a validated GitHub document projection. Group
    # exact slices by repository/path, including slices in differently sized parents.
    return case((EntryPassage.group_key.is_not(None), cast(func.json_build_array(
        Entry.source_scope, EntryVersion.payload["path"].astext, Vector.slice_hash, Vector.end-Vector.start), String)),
        else_=literal("slice:") + cast(Vector.id, String))


def candidates(owner_id, filters):
    return filtered_vectors(owner_id, filters).with_only_columns(Vector.id.label("embedding_id"),
        Vector.passage_id, Vector.start, Vector.end, Vector.slice_hash,
        Entry.id.label("entry_id"), EntryVersion.id.label("version_id"), Entry.event_at,
        group_key().label("group_id"))


def read_slice(db, owner_id, embedding_id):
    row = db.execute(eligible_embeddings(owner_id).with_only_columns(Vector.passage_id,
        Vector.start, Vector.end, Vector.slice_hash).where(Vector.id == embedding_id)).first()
    if row is None:
        raise HTTPException(404, "SEMANTIC_SLICE_UNAVAILABLE")
    parent = read_passage(db, owner_id, row.passage_id)
    value = parent.text[row.start-parent.start:row.end-parent.start]
    if text_hash(value) != row.slice_hash:
        raise HTTPException(404, "SEMANTIC_SLICE_UNAVAILABLE")
    return parent.model_copy(update=dict(text=value, start=row.start, end=row.end, passage_hash=row.slice_hash))


def search_vectors(db, owner_id, filters, vector, coverage):
    base = candidates(owner_id, filters).add_columns(Vector.vector.cosine_distance(vector).label("distance")).cte("semantic_candidates")
    grouped = select(base, func.row_number().over(partition_by=base.c.group_id,
        order_by=[base.c.event_at.desc().nulls_last(), base.c.entry_id.desc(), base.c.embedding_id]).label("position"),
        func.min(base.c.distance).over(partition_by=base.c.group_id).label("group_distance"),
        func.count().over(partition_by=base.c.group_id).label("alias_total")).cte("semantic_groups")
    rows = db.execute(select(grouped).where(grouped.c.position == 1).order_by(
        grouped.c.group_distance, grouped.c.event_at.desc().nulls_last(), grouped.c.embedding_id).limit(21)).mappings().all()
    items = []
    for row in rows[:20]:
        passage = read_slice(db, owner_id, row["embedding_id"])
        passage.alias_total = row["alias_total"]
        if passage.alias_total > 1:
            passage.snapshot_count = db.scalar(select(func.count(func.distinct(base.c.entry_id))).where(
                base.c.group_id == row["group_id"]))
        items.append(SemanticHit(embedding_id=row["embedding_id"], distance=row["group_distance"], passage=passage))
    return SemanticResponse(items=items, coverage=coverage, truncated=len(rows) > 20)


def locations(db, owner_id, embedding_id, filters, limit, offset):
    read_slice(db, owner_id, embedding_id)
    base = candidates(owner_id, filters).cte("semantic_locations")
    key = db.scalar(select(base.c.group_id).where(base.c.embedding_id == embedding_id))
    if key is None:
        raise HTTPException(404, "SEMANTIC_SLICE_UNAVAILABLE")
    total = db.scalar(select(func.count()).select_from(base).where(base.c.group_id == key))
    rows = db.execute(select(base).where(base.c.group_id == key).order_by(
        base.c.event_at.desc().nulls_last(), base.c.entry_id.desc(), base.c.embedding_id).limit(limit).offset(offset)).mappings()
    return SemanticLocations(items=[SemanticLocation.model_validate(dict(row)) for row in rows],
        total=total, limit=limit, offset=offset)
