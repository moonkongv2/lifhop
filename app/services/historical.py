"""Local keyword review of latest observed versions at a cutoff, never past-state inference."""
from datetime import timedelta
from itertools import islice
from fastapi import HTTPException
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import defer
from app.evaluation.schemas import digest
from app.models.entry import Entry, EntrySource, EntryType
from app.models.history import EntryVersion, SourcePolicy
from app.models.user import User
from app.schemas.historical import HistoricalExcerpt, HistoricalPreview
from app.schemas.passage import CitationAnchor
from app.services.answer_transport import CONFIG_HASH, payload
from app.services.citation_read import read_citation
from app.services.embedding_transport import EmbeddingError
from app.services.entry_search import date_boundary
from app.services.passage_index import content_ranges, split_ranges, text_hash
from app.services.passage_search import query_tokens
from app.services.source_history import owner_lock

MAX_CONTENT_BYTES = 1024 * 1024
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
CANDIDATES = 20
ALLOWED_TYPES = [EntryType.NOTE, EntryType.DOCUMENT, EntryType.CONVERSATION]


def cutoff(scope):
    return date_boundary(scope.as_of + timedelta(days=1))


def scoped_conditions(owner_id, scope):
    conditions = [Entry.user_id == owner_id]
    if scope.source == EntrySource.UNKNOWN:
        conditions.append(or_(Entry.provider.is_(None), ~Entry.provider.in_([s.value for s in EntrySource if s != EntrySource.UNKNOWN])))
    elif scope.source:
        conditions.append(func.coalesce(Entry.provider, 'unknown') == scope.source.value)
    if scope.type:
        conditions.append(Entry.type == scope.type)
    return conditions


def snapshots(owner_id, scope):
    ranked = select(EntryVersion.id.label('version_id'), func.row_number().over(
        partition_by=EntryVersion.entry_id, order_by=[EntryVersion.observed_at.desc(), EntryVersion.id.desc()]).label('rank')
        ).join(Entry, Entry.id == EntryVersion.entry_id).where(*scoped_conditions(owner_id, scope),
            EntryVersion.observed_at < cutoff(scope)).cte('observed_versions')
    return select(EntryVersion.id).join(ranked, ranked.c.version_id == EntryVersion.id).where(ranked.c.rank == 1)


def allowed_versions(owner_id, scope):
    return snapshots(owner_id, scope).join(Entry, Entry.id == EntryVersion.entry_id).join(SourcePolicy,
        (SourcePolicy.user_id == Entry.user_id) & (SourcePolicy.provider == func.coalesce(Entry.provider, 'unknown')) &
        (SourcePolicy.scope == Entry.source_scope)).where(Entry.external_ai_allowed.is_(True),
            SourcePolicy.external_ai_allowed.is_(True), Entry.source_state != 'deleted', Entry.type.in_(ALLOWED_TYPES),
            EntryVersion.entry_type.in_([value.value for value in ALLOWED_TYPES]),
            *([EntryVersion.entry_type == scope.type.value] if scope.type else []))


def terms(scope):
    return query_tokens(scope.q) or [scope.q.casefold()]


def read_version(db, version_id):
    # Bound materialization before Python normalization, including Codex payloads.
    version = db.scalar(select(EntryVersion).where(EntryVersion.id == version_id,
        func.coalesce(func.octet_length(EntryVersion.content), 0) <= MAX_CONTENT_BYTES,
        func.coalesce(func.octet_length(cast(EntryVersion.payload, Text)), 0) <= MAX_PAYLOAD_BYTES))
    if version is None:
        return None, None
    entry = db.scalar(select(Entry).options(defer(Entry.content), defer(Entry.primary_content)).where(Entry.id == version.entry_id))
    return entry, version


def excerpts(passages):
    return [dict(id=p.version_id, text=p.text, version_id=p.version_id,
        observed_at=p.observed_at.isoformat(), event_at=p.event_at.isoformat() if p.event_at else None,
        completeness=p.completeness) for p in passages]


def preview(db, owner_id, scope):
    scope_count = db.scalar(select(func.count()).select_from(Entry).where(*scoped_conditions(owner_id, scope)))
    observed = snapshots(owner_id, scope)
    allowed = allowed_versions(owner_id, scope)
    count = lambda statement: db.scalar(select(func.count()).select_from(statement.subquery()))
    matches = []
    for token in terms(scope):
        escaped = token.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        matches.append(EntryVersion.content.ilike(f'%{escaped}%', escape='\\'))
    matching = allowed.where(or_(*matches))
    ids = list(db.scalars(matching.order_by(EntryVersion.observed_at.desc(), EntryVersion.id.desc()).limit(CANDIDATES)))
    selected, input_skipped, byte_skipped, examined = [], 0, 0, 0
    for version_id in ids:
        examined += 1
        entry, version = read_version(db, version_id)
        if version is None:
            input_skipped += 1
            continue
        spans, gaps = content_ranges(entry, version)
        if gaps:
            input_skipped += 1
            continue
        ranges = ((left, right) for start, end, work in spans if not work
            for left, right in split_ranges(version.content or '', start, end))
        for start, end in islice(ranges, 512):
            value = version.content[start:end]
            if not any(term in value.casefold() for term in terms(scope)):
                continue
            anchor = CitationAnchor(version_id=version_id, field='content', start=start, end=end, passage_hash=text_hash(value))
            p = HistoricalExcerpt(**read_citation(db, owner_id, anchor).model_dump(), passage_hash=anchor.passage_hash)
            try:
                payload(scope.q, excerpts([*selected, p]), historical_as_of=str(scope.as_of))
            except EmbeddingError:
                byte_skipped += 1
            else:
                selected.append(p)
            break  # One complete matching range per version; never truncate to fit.
        if len(selected) == 5:
            break
    revision = db.scalar(select(User.policy_revision).where(User.id == owner_id))
    counts = [scope_count, count(observed), count(allowed), count(matching), examined, input_skipped, byte_skipped]
    protocol = dict(owner_id=owner_id, configuration=CONFIG_HASH, selection='observed-keyword-v1',
        scope=scope.model_dump(mode='json'), revision=revision, counts=counts,
        passages=[p.model_dump(mode='json') for p in selected])
    return HistoricalPreview(scope=scope, policy_revision=revision, preview_digest=digest(protocol),
        scope_records=counts[0], observed_records=counts[1], allowed_records=counts[2], matching_records=counts[3],
        examined_records=examined, input_skipped=input_skipped, byte_skipped=byte_skipped, passages=selected)


def checked_passages(db, owner_id, anchors, revision, scope):
    """Called before reservation, at dispatch under owner lock, and before returning output."""
    owner_lock(db, owner_id)
    if db.scalar(select(User.policy_revision).where(User.id == owner_id)) != revision:
        raise HTTPException(409, 'ANSWER_CONTEXT_CHANGED')
    permitted = allowed_versions(owner_id, scope)
    result = []
    for value in anchors:
        anchor = CitationAnchor.model_validate({key: value[key] for key in CitationAnchor.model_fields})
        if anchor.field != 'content' or db.scalar(permitted.where(EntryVersion.id == anchor.version_id)) is None:
            raise HTTPException(409, 'ANSWER_CONTEXT_CHANGED')
        entry, version = read_version(db, anchor.version_id)
        if version is None:
            raise HTTPException(409, 'ANSWER_CONTEXT_CHANGED')
        spans, gaps = content_ranges(entry, version)
        if gaps or not any(not work and start <= anchor.start < anchor.end <= end for start, end, work in spans):
            raise HTTPException(409, 'ANSWER_CONTEXT_CHANGED')
        p = read_citation(db, owner_id, anchor)
        result.append(HistoricalExcerpt(**p.model_dump(), passage_hash=anchor.passage_hash))
    return result
