"""Only egress boundary for future AI callers; no provider is configured here."""
from dataclasses import dataclass
from typing import Callable, Literal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entry import Entry
from app.models.user import User
from app.models.history import EntryVersion
from app.services.source_history import owner_lock, source_policy

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
