"""Only egress boundary for future AI callers; no provider is configured here."""
from dataclasses import dataclass
from typing import Callable, Literal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entry import Entry, EntryType
from app.models.user import User
from app.models.history import EntryVersion
from app.services.source_history import owner_lock, source_policy
from app.services.passage_search import read_passage
from app.models.history import SourcePolicy

Purpose = Literal["embedding", "rerank", "summary", "answer", "telemetry"]


@dataclass(frozen=True)
class PreparedContext:
    user_id: int
    policy_revision: int
    version_ids: tuple[int, ...]
    include_source_deleted: bool = False


def prepare_context(db: Session, *, user_id: int, version_ids: list[int],
                    include_source_deleted: bool = False) -> PreparedContext:
    owner_lock(db, user_id)
    context = PreparedContext(user_id, db.scalar(select(User.policy_revision).where(User.id == user_id)),
                              tuple(sorted(set(version_ids))), include_source_deleted)
    _records(db, context)
    return context


def _records(db: Session, context: PreparedContext) -> list[EntryVersion]:
    if not context.version_ids:
        raise HTTPException(403, "Derived context needs all source dependencies")
    if db.scalar(select(User.policy_revision).where(User.id == context.user_id)) != context.policy_revision:
        raise HTTPException(409, "Content or policy changed; rebuild the context")
    versions = []
    for version_id in context.version_ids:
        version = db.get(EntryVersion, version_id, populate_existing=True)
        entry = db.get(Entry, version.entry_id, populate_existing=True) if version else None
        if not entry or entry.user_id != context.user_id:
            raise HTTPException(403, "Source dependency is unavailable")
        policy = source_policy(db, context.user_id, entry.provider or "unknown", entry.source_scope)
        if not policy.external_ai_allowed or not entry.external_ai_allowed:
            raise HTTPException(403, "Source or record excludes external AI")
        if entry.source_state == "deleted" and not context.include_source_deleted:
            raise HTTPException(403, "Confirmed source deletions require explicit inclusion")
        versions.append(version)
    return versions


def send_external_ai(db: Session, context: PreparedContext, *, purpose: Purpose,
                     transport: Callable[[dict], object]) -> object:
    if purpose not in {"embedding", "rerank", "summary", "answer", "telemetry"}:
        raise ValueError("Unknown AI purpose")
    owner_lock(db, context.user_id)
    # Hold policy lock until transport returns. Deletion/denial cannot pass between check and send.
    versions = _records(db, context)
    return transport({"purpose": purpose, "sources": [
        {"version_id": v.id, "title": v.title, "content": v.content} for v in versions]})


def embedding_inputs(db: Session, *, user_id: int, passages: list[dict], revision: int) -> list[str]:
    """Revalidate exact current slices under the same lock as deny/delete."""
    owner_lock(db, user_id)
    if db.scalar(select(User.policy_revision).where(User.id == user_id)) != revision:
        raise HTTPException(409, "EMBEDDING_CONTEXT_CHANGED")
    inputs = []
    for anchor in passages:
        p = read_passage(db, user_id, anchor["id"])
        if p.passage_hash != anchor["passage_hash"] or p.field != "content" or p.work_only or p.source_state == "deleted":
            raise HTTPException(409, "EMBEDDING_CONTEXT_CHANGED")
        if db.scalar(select(Entry.type).where(Entry.id == p.entry_id)) not in {EntryType.NOTE, EntryType.DOCUMENT, EntryType.CONVERSATION}:
            raise HTTPException(403, "EMBEDDING_INPUT_TYPE_EXCLUDED")
        allowed = db.scalar(select(SourcePolicy.external_ai_allowed).where(SourcePolicy.user_id == user_id,
            SourcePolicy.provider == p.source, SourcePolicy.scope == db.scalar(
                select(Entry.source_scope).where(Entry.id == p.entry_id))))
        if not allowed or not db.scalar(select(Entry.external_ai_allowed).where(Entry.id == p.entry_id)):
            raise HTTPException(403, "EMBEDDING_POLICY_DENIED")
        inputs.append(p.text)
    return inputs


def send_passage_embeddings(db: Session, *, user_id: int, passages: list[dict], revision: int, transport):
    from app.services.embedding_transport import input_bound
    inputs = embedding_inputs(db, user_id=user_id, passages=passages, revision=revision)
    input_bound(inputs)
    return transport(inputs)


def send_query_embedding(db: Session, *, user_id: int, query: str, confirm_external_ai: bool, transport):
    from app.services.embedding_transport import input_bound
    if confirm_external_ai is not True:
        raise HTTPException(403, "QUERY_CONSENT_REQUIRED")
    if db.get(User, user_id) is None:
        raise HTTPException(403, "OWNER_UNAVAILABLE")
    input_bound([query], query=True)
    return transport([query])
