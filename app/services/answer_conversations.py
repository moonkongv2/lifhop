"""Short transactions for saved conversation ownership, state and restoration."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import defer
from app.models.answer_conversation import AnswerConversation as Conversation, AnswerTurn as Turn, AnswerTurnSource as Source, TERMINAL
from app.models.user import User
from app.models.ai_usage import AiUsageAttempt
from app.services.conversation_context import anchor, key, availability, validate, shared_lock

FORMAT = 'dialogue-v1'
CONSENT = 'dialogue-consent-v1'


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def conversation(db, owner, cid, lock=False):
    query = select(Conversation).where(Conversation.id == cid, Conversation.user_id == owner)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(404, 'Conversation unavailable')
    return row


def turn(db, owner, cid, tid, request_id=None, lock=False):
    query = select(Turn).options(defer(Turn.answer), defer(Turn.resolved_q)).where(
        Turn.id == tid, Turn.conversation_id == cid, Turn.user_id == owner)
    if request_id is not None:
        query = query.where(Turn.request_id == request_id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise HTTPException(404, 'Turn unavailable')
    return row


def sources(db, tid):
    return list(db.scalars(select(Source).where(Source.turn_id == tid).order_by(Source.selection_order.nullslast(), Source.id)))


def bump(c):
    c.revision += 1
    c.updated_at = now()


def summary(c):
    return dict(id=c.id, title=c.title, state=c.state, revision=c.revision, updated_at=c.updated_at)


def list_conversations(db, owner, cursor=None):
    query = select(Conversation).where(Conversation.user_id == owner)
    if cursor:
        try:
            updated, cid = json.loads(bytes.fromhex(cursor))
            updated = datetime.fromisoformat(updated)
            if len(cid) != 32:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, 'Invalid cursor') from None
        query = query.where(or_(Conversation.updated_at < updated,
            and_(Conversation.updated_at == updated, Conversation.id < cid)))
    rows = list(db.scalars(query.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(51)))
    visible = rows[:50]
    token = json.dumps([visible[-1].updated_at.isoformat(), visible[-1].id]).encode().hex() if len(rows) > 50 else None
    return dict(items=[summary(c) for c in visible], next_cursor=token)


def view_turn(db, owner, t, rows=None):
    rows = sources(db, t.id) if rows is None else rows
    states = availability(db, owner, [anchor(a) for a in rows])
    status = 'deleted' if t.redacted or 'deleted' in states.values() else (
        'updated' if 'updated' in states.values() else 'excluded' if 'excluded' in states.values() else 'available')
    visible = status != 'deleted'
    run_ids = [s.get('run_id') for s in t.stages.values() if s.get('run_id')]
    usages = []
    if run_ids:
        usages = [dict(id=r.id, purpose=r.purpose, status=r.status,
            reserved_micro_usd=r.reserved_micro_usd, spent_micro_usd=r.spent_micro_usd)
            for r in db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner,
                AiUsageAttempt.run_id.in_(run_ids)))]
    return dict(id=t.id, seq=t.seq, request_id=t.request_id, epoch=t.epoch, q=t.q,
        base_turn_id=t.base_turn_id, state=t.state, outcome=t.outcome, branch=t.branch,
        answer=t.answer if visible else None, answer_status=t.answer_status,
        error_code=t.error_code, availability=status,
        citations=[{k: v for k,v in anchor(a).items() if k != 'projection_version'} for a in rows if a.cited] if visible else [],
        context_summary=t.context_summary, usage=usages, lease_expires_at=t.lease_expires_at,
        action_expires_at=t.action_expires_at)


def detail(db, owner, cid, before=None):
    shared_lock(db, owner)
    c = conversation(db, owner, cid)
    query = select(Turn).options(defer(Turn.answer), defer(Turn.resolved_q)).where(Turn.conversation_id == cid, Turn.user_id == owner)
    if before is not None:
        query = query.where(Turn.seq < before)
    rows = list(db.scalars(query.order_by(Turn.seq.desc()).limit(51)))
    selected = rows[:50]
    unfinished = db.scalar(select(Turn).options(defer(Turn.answer), defer(Turn.resolved_q)).where(
        Turn.conversation_id == cid, Turn.user_id == owner, Turn.state.not_in(TERMINAL)))
    return dict(**summary(c), filters=c.filters, turns=[view_turn(db, owner, t) for t in reversed(selected)],
        next_before=selected[-1].seq if len(rows) > 50 else None,
        unfinished=view_turn(db, owner, unfinished) if unfinished else None)


def claim(db, owner, cid, data):
    if not data.confirm_external_ai:
        raise HTTPException(403, 'ANSWER_CONSENT_REQUIRED')
    shared_lock(db, owner)
    c = conversation(db, owner, cid, True)
    fingerprint = digest(dict(data.model_dump(mode='json'), consent=CONSENT))
    existing = db.scalar(select(Turn).options(defer(Turn.answer), defer(Turn.resolved_q)).where(Turn.user_id == owner, Turn.request_id == data.request_id))
    if existing:
        if existing.conversation_id != cid:
            raise HTTPException(404, 'Turn unavailable')
        if existing.fingerprint != fingerprint:
            raise HTTPException(409, 'REQUEST_ID_CONFLICT')
        return existing
    if c.revision != data.expected_revision:
        raise HTTPException(409, 'CONVERSATION_REVISION_CONFLICT')
    if c.state != 'active':
        raise HTTPException(409, 'CONVERSATION_CLOSED')
    if db.scalar(select(Turn.id).where(Turn.conversation_id == cid, Turn.state.not_in(TERMINAL))):
        raise HTTPException(409, 'CONVERSATION_BUSY')
    seq = (db.scalar(select(func.max(Turn.seq)).where(Turn.conversation_id == cid)) or 0) + 1
    tid = uuid4().hex
    histories, reference, root, epoch = [], None, tid, c.context_epoch
    if data.context_mode == 'fresh':
        epoch += 1
        c.context_epoch = epoch
    else:
        previous = list(db.scalars(select(Turn).options(defer(Turn.answer), defer(Turn.resolved_q)).where(
            Turn.conversation_id == cid, Turn.user_id == owner, Turn.epoch == epoch,
            Turn.state == 'completed').order_by(Turn.seq.desc()).limit(2)))
        if data.base_turn_id:
            reference = turn(db, owner, cid, data.base_turn_id)
            if reference.state != 'completed' or reference.outcome != 'answer':
                raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')
            histories = [reference]
            root = reference.context_root_turn_id
        else:
            histories = previous
            if previous:
                root = previous[0].context_root_turn_id
                ref_id = previous[0].evidence_reference_turn_id
                pending = previous[0].outcome == 'clarification'
                if pending and previous[0].redacted:
                    raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')
                if pending:
                    origin = previous[0].context_summary.get('pending_origin')
                    if origin and origin not in [h.id for h in histories]:
                        histories.append(turn(db,owner,cid,origin))
                if pending and ref_id:
                    reference = turn(db, owner, cid, ref_id)
                else:
                    reference = db.scalar(select(Turn).options(defer(Turn.answer), defer(Turn.resolved_q)).where(
                        Turn.conversation_id == cid, Turn.epoch == epoch, Turn.state == 'completed', Turn.outcome == 'answer',
                        Turn.id.in_(select(Source.turn_id).where(Source.direct_selected.is_(True))))
                        .order_by(Turn.seq.desc()).limit(1))
                if reference and reference.id not in [h.id for h in histories]:
                    histories.append(reference)
        if root != tid and root not in [h.id for h in histories]:
            histories.append(turn(db, owner, cid, root))
    inherited = {}
    for history in histories:
        if history.redacted or history.format_version != FORMAT:
            raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')
        for a in sources(db, history.id):
            inherited[key(a)] = anchor(a)
    validate(db, owner, list(inherited.values()))
    t = Turn(id=tid, conversation_id=cid, user_id=owner, seq=seq, request_id=data.request_id,
        fingerprint=fingerprint, base_revision=c.revision, epoch=epoch, q=data.q,
        base_turn_id=data.base_turn_id, evidence_reference_turn_id=reference.id if reference else None,
        context_root_turn_id=root, history_ids=list(dict.fromkeys(h.id for h in histories)),
        policy_revision=db.scalar(select(User.policy_revision).where(User.id == owner)),
        action_expires_at=now() + timedelta(seconds=120), stages={}, context_summary={})
    db.add(t)
    db.flush()
    for a in inherited.values():
        db.add(Source(turn_id=tid, **a, inherited=True))
    if seq == 1:
        c.title = data.q[:100]
    bump(c)
    db.flush()
    return t


def change(db, owner, cid, action, revision=None, tid=None, request_id=None):
    c = conversation(db, owner, cid, True)
    if action == 'delete':
        db.delete(c)
        return
    if revision is not None and c.revision != revision:
        raise HTTPException(409, 'CONVERSATION_REVISION_CONFLICT')
    if action in {'close', 'reopen'}:
        if db.scalar(select(Turn.id).where(Turn.conversation_id == cid, Turn.state.not_in(TERMINAL))):
            raise HTTPException(409, 'CONVERSATION_BUSY')
        state = 'closed' if action == 'close' else 'active'
        if c.state != state:
            c.state = state
            bump(c)
        return
    t = turn(db, owner, cid, tid, request_id, True)
    if t.state in TERMINAL:
        return
    if action == 'interrupt' and now() < t.action_expires_at and (t.lease_expires_at is None or now() < t.lease_expires_at):
        raise HTTPException(409, 'TURN_NOT_EXPIRED')
    t.state = 'stopped' if action == 'stop' else 'interrupted'
    bump(c)
