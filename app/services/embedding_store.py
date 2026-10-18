"""Publish only current allowed slices; never call a provider from storage."""
import math
from array import array
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage, PassageIndexState
from app.models.passage_embedding import PassageEmbedding
from app.services.ai_policy import embedding_inputs
from app.services.ai_sources import allowed_type
from app.services.embedding_transport import CONFIG, DIMENSIONS, MODEL
from app.services.passage_index import PROJECTION_VERSION, text_hash
from app.services.passage_search import read_passage
from app.services.semantic_chunks import CHUNKING, section_ranges
from app.services.source_history import owner_lock

STORAGE_CONFIG = CONFIG + ":" + CHUNKING + ":" + PROJECTION_VERSION


def eligible_embeddings(user_id: int):
    """Live policy joins are required even if derivative cleanup was delayed."""
    return (select(PassageEmbedding)
        .join(EntryPassage, EntryPassage.id == PassageEmbedding.passage_id)
        .join(EntryVersion, EntryVersion.id == EntryPassage.version_id)
        .join(Entry, Entry.id == EntryVersion.entry_id)
        .join(PassageIndexState, PassageIndexState.entry_id == Entry.id)
        .join(SourcePolicy, (SourcePolicy.user_id == Entry.user_id) &
            (SourcePolicy.provider == func.coalesce(Entry.provider, "unknown")) &
            (SourcePolicy.scope == Entry.source_scope))
        .where(Entry.user_id == user_id, Entry.external_ai_allowed.is_(True),
            SourcePolicy.external_ai_allowed.is_(True), Entry.source_state != "deleted",
            allowed_type(),
            Entry.current_version_id == EntryVersion.id,
            EntryPassage.field == "content", EntryPassage.work_only.is_(False),
            EntryPassage.projection_version == PROJECTION_VERSION,
            EntryPassage.passage_hash == PassageEmbedding.parent_hash,
            EntryPassage.text == func.substring(EntryVersion.content,
                EntryPassage.start + 1, EntryPassage.end - EntryPassage.start),
            PassageIndexState.indexed_version_id == EntryVersion.id,
            PassageIndexState.content_hash == EntryVersion.content_hash,
            PassageIndexState.projection_version == PROJECTION_VERSION,
            PassageIndexState.status.in_(["ready", "partial"]),
            PassageEmbedding.start >= EntryPassage.start,
            PassageEmbedding.end <= EntryPassage.end,
            PassageEmbedding.model == MODEL, PassageEmbedding.config == STORAGE_CONFIG))


def slice_anchors(db: Session, *, user_id: int, passage_id: int, revision: int) -> list[dict]:
    """Prepare exact slices from a bounded primary body passage."""
    owner_lock(db, user_id)
    parent = read_passage(db, user_id, passage_id)
    anchor = dict(id=parent.id, passage_hash=parent.passage_hash)
    value = embedding_inputs(db, user_id=user_id, passages=[anchor], revision=revision)[0]
    return [dict(anchor, start=parent.start + left, end=parent.start + right,
        slice_hash=text_hash(value[left:right])) for left, right in section_ranges(value)
        if value[left:right].strip()]


def publish_embeddings(db: Session, *, user_id: int, revision: int,
                       anchors: list[dict], vectors: list) -> int:
    """Caller commits; every input is validated before the first INSERT."""
    if not 1 <= len(anchors) <= 16 or len(anchors) != len(vectors):
        raise ValueError("EMBEDDING_PUBLICATION_INVALID")
    owner_lock(db, user_id)
    texts = embedding_inputs(db, user_id=user_id, passages=anchors, revision=revision)
    rows = []
    expected = {}
    for anchor, value, vector in zip(anchors, texts, vectors):
        if anchor["id"] not in expected:
            expected[anchor["id"]] = slice_anchors(db, user_id=user_id,
                passage_id=anchor["id"], revision=revision)
        if anchor not in expected[anchor["id"]]:
            raise HTTPException(409, "EMBEDDING_SLICE_INVALID")
        try:
            if len(vector) != DIMENSIONS or any(isinstance(v, (bool, str)) for v in vector):
                raise ValueError()
            values = list(array("f", [float(v) for v in vector]))
            if any(not math.isfinite(v) for v in values) or not any(values):
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            raise ValueError("EMBEDDING_VECTOR_INVALID") from None
        rows.append(dict(passage_id=anchor["id"], parent_hash=anchor["passage_hash"],
            start=anchor["start"], end=anchor["end"], slice_hash=text_hash(value),
            model=MODEL, config=STORAGE_CONFIG, vector=values))
    statement = insert(PassageEmbedding).values(rows).on_conflict_do_nothing(
        constraint="uq_passage_embedding_slice").returning(PassageEmbedding.id)
    return len(list(db.scalars(statement)))


def prune_embeddings(db: Session, user_id: int) -> None:
    """Called under the existing owner lock, inside a source/policy transaction."""
    owned = (select(EntryPassage.id).join(EntryVersion, EntryVersion.id == EntryPassage.version_id)
        .join(Entry, Entry.id == EntryVersion.entry_id).where(Entry.user_id == user_id))
    valid = eligible_embeddings(user_id).with_only_columns(PassageEmbedding.id)
    db.execute(delete(PassageEmbedding).where(PassageEmbedding.passage_id.in_(owned),
        PassageEmbedding.id.not_in(valid)).execution_options(synchronize_session=False))
