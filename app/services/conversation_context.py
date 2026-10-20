"""Stable, metadata-first AI gate; historical viewing has a separate policy."""
from fastapi import HTTPException
from sqlalchemy import select, text, func
from app.models.entry import Entry
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage, PassageIndexState
from app.models.answer_conversation import AnswerConversation, AnswerTurn, AnswerTurnSource, TERMINAL
from app.services.ai_sources import allowed_type
from app.services.passage_index import PROJECTION_VERSION

ANCHOR_FIELDS = ('entry_id', 'version_id', 'field', 'start', 'end', 'passage_hash', 'projection_version')


def anchor(value):
    return {k: getattr(value, k) for k in ANCHOR_FIELDS}


def key(value):
    return tuple(value[k] if isinstance(value, dict) else getattr(value, k) for k in ANCHOR_FIELDS)


def shared_lock(db, owner):
    db.execute(text("SET LOCAL lock_timeout = '2s'"))
    db.execute(text("SET LOCAL statement_timeout = '5s'"))
    db.execute(text('SELECT pg_advisory_xact_lock_shared(12022, :owner)'), {'owner': owner})


def availability(db, owner, anchors):
    """Only IDs, policy and projection metadata leave PostgreSQL before permission checks."""
    if not anchors:
        return {}
    if len(anchors) > 500:
        raise HTTPException(409, 'CONVERSATION_CONTEXT_LIMIT')
    ids = {a['entry_id'] for a in anchors}
    rows = db.execute(select(Entry.id, Entry.user_id, Entry.current_version_id, Entry.source_state,
        Entry.external_ai_allowed, SourcePolicy.external_ai_allowed.label('source_allowed'),
        allowed_type().label('type_allowed')).outerjoin(SourcePolicy,
        (SourcePolicy.user_id == Entry.user_id) & (SourcePolicy.provider == func.coalesce(Entry.provider, 'unknown')) &
        (SourcePolicy.scope == Entry.source_scope)).where(Entry.id.in_(ids))).mappings().all()
    entries = {r.id: r for r in rows}
    versions = set(db.execute(select(EntryVersion.entry_id, EntryVersion.id).where(
        EntryVersion.id.in_({a['version_id'] for a in anchors}))).all())
    projections = set(db.execute(select(EntryVersion.entry_id, EntryPassage.version_id, EntryPassage.field,
        EntryPassage.start, EntryPassage.end, EntryPassage.passage_hash, EntryPassage.projection_version)
        .join(EntryVersion, EntryVersion.id == EntryPassage.version_id)
        .join(PassageIndexState, PassageIndexState.entry_id == EntryVersion.entry_id)
        .where(EntryPassage.version_id.in_({a['version_id'] for a in anchors}),
            EntryPassage.field == 'content', EntryPassage.work_only.is_(False),
            EntryPassage.projection_version == PROJECTION_VERSION,
            PassageIndexState.indexed_version_id == EntryVersion.id,
            PassageIndexState.projection_version == PROJECTION_VERSION,
            PassageIndexState.content_hash == EntryVersion.content_hash,
            PassageIndexState.status.in_(['ready', 'partial']))).all())
    result = {}
    for a in anchors:
        r = entries.get(a['entry_id'])
        status = 'available'
        if r is None or r.user_id != owner or (a['entry_id'], a['version_id']) not in versions:
            status = 'deleted'
        elif r.current_version_id != a['version_id']:
            status = 'updated'
        elif (r.source_state == 'deleted' or not r.external_ai_allowed or not r.source_allowed
                or not r.type_allowed or key(a) not in projections):
            status = 'excluded'
        result[key(a)] = status
    return result


def validate(db, owner, anchors):
    if any(v != 'available' for v in availability(db, owner, anchors).values()):
        raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')


def excerpts(db, owner, sources):
    """Caller validates the complete dependency set first under shared_lock."""
    from app.services.passage_search import read_passage
    from app.services.answer_context import current_excerpt
    result = []
    for source in sources:
        a = anchor(source)
        # Resolve an ephemeral ID only after the stable metadata gate. Never persist it.
        pid = db.scalar(select(EntryPassage.id).where(EntryPassage.version_id == a['version_id'],
            EntryPassage.field == a['field'], EntryPassage.start == a['start'], EntryPassage.end == a['end'],
            EntryPassage.passage_hash == a['passage_hash'], EntryPassage.projection_version == a['projection_version']).limit(1))
        if pid is None:
            raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')
        parent = read_passage(db, owner, pid)
        if key(parent) != key(a):
            raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')
        result.append(current_excerpt(parent, reference_id=source.selection_order + 1))
    return result


def redact_sources(db, owner, entry_id):
    """Runs inside the source deletion transaction after its exclusive owner lock."""
    affected = select(AnswerTurnSource.turn_id).where(AnswerTurnSource.entry_id == entry_id)
    conversation_ids = list(db.scalars(select(AnswerTurn.conversation_id).where(
        AnswerTurn.user_id == owner, AnswerTurn.id.in_(affected)).distinct().order_by(AnswerTurn.conversation_id)))
    for cid in conversation_ids:
        conversation = db.scalar(select(AnswerConversation).where(AnswerConversation.id == cid,
            AnswerConversation.user_id == owner).with_for_update())
        if conversation is None:
            continue
        turns = db.scalars(select(AnswerTurn).where(AnswerTurn.conversation_id == cid,
            AnswerTurn.id.in_(affected)).order_by(AnswerTurn.seq).with_for_update())
        for turn in turns:
            turn.answer = turn.resolved_q = None
            turn.redacted = True
            turn.error_code = 'CONVERSATION_SOURCE_DELETED'
            if turn.state not in TERMINAL:
                turn.state = 'failed'
        conversation.revision += 1
