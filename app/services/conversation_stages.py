"""Durable once-only stages. Provider I/O holds source guards, never turn row locks."""
import asyncio
import json
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.answer_conversation import AnswerTurn as Turn, AnswerTurnSource as Source, TERMINAL
from app.models.user import User
from app.models.passage import EntryPassage
from app.models.passage_embedding import PassageEmbedding
from app.services import answer_transport as at, followup_transport as ft, embedding_transport as et
from app.services.ai_usage import call_slot, reserve, settle
from app.services.answer_conversations import conversation, turn, sources, now, bump, digest, FORMAT
from app.services.conversation_context import shared_lock, validate, anchor, key, excerpts
from app.services.semantic_search import candidates as search_candidates, index_coverage

# Test transports replace only provider I/O, retaining guards and accounting.
answer_sender = None
planner_sender = None
query_sender = None
STATES = {'plan': ('created','planning'), 'search': ('planned','searching'),
          'evidence': ('planned','selecting'), 'answer': ('ready','answering')}


def check_live(db, owner, cid, tid, request_id, stage, *, lock=False, dispatch=False):
    c = conversation(db, owner, cid, lock)
    t = turn(db, owner, cid, tid, request_id, lock)
    if t.state != STATES[stage][1] or t.redacted or c.state != 'active':
        raise HTTPException(409, 'TURN_STAGE_CONFLICT')
    if t.lease_expires_at <= now() or (dispatch and t.action_expires_at <= now()):
        raise HTTPException(409, 'TURN_EXPIRED')
    if db.scalar(select(User.policy_revision).where(User.id == owner)) != t.policy_revision:
        raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')
    return c, t


def checked(db, owner, cid, tid, rid, stage):
    shared_lock(db, owner)
    c, t = check_live(db, owner, cid, tid, rid, stage)
    deps = sources(db, tid)
    validate(db, owner, [anchor(s) for s in deps])
    return c, t, deps


def dialogue(db, t):
    values, optional = [], []
    ids = t.history_ids
    for hid in ids:
        h = turn(db, t.user_id, t.conversation_id, hid)
        if h.redacted or h.format_version != FORMAT:
            raise HTTPException(409, 'CONVERSATION_CONTEXT_UNAVAILABLE')
        root_only = hid == t.context_root_turn_id and hid != t.evidence_reference_turn_id
        item = dict(turn_id=h.id, question=h.q)
        if not root_only:
            item.update(answer=h.answer, outcome=h.outcome)
        values.append(item)
        if hid not in {t.context_root_turn_id, t.evidence_reference_turn_id} and h.outcome != 'clarification':
            optional.append(hid)
    omitted = []
    while len(json.dumps(values, ensure_ascii=False).encode()) > 16*1024:
        if not optional:
            raise et.EmbeddingError('CONVERSATION_CONTEXT_LIMIT')
        # IDs are selected newest first; remove the oldest optional candidate.
        removed = optional.pop()
        values = [v for v in values if v['turn_id'] != removed]
        omitted.append(removed)
    return values, omitted, optional


def prepare(db, owner, cid, tid, rid, stage):
    c, t, deps = checked(db, owner, cid, tid, rid, stage)
    history, omitted, optional = dialogue(db, t)
    if stage == 'search':
        if t.branch != 'search':
            raise HTTPException(409, 'TURN_STAGE_CONFLICT')
        upper = et.input_bound([t.resolved_q], query=True)
        return [t.resolved_q], upper, dict(history_ids=[], omitted=[])
    selected = [s for s in deps if s.direct_selected]
    bodies = excerpts(db, owner, selected) if stage == 'answer' else None
    while True:
        try:
            value, upper = (ft.payload(t.q, history) if stage == 'plan' else
                at.payload(t.resolved_q or t.q, bodies, dialogue=history))
            break
        except et.EmbeddingError:
            if not optional:
                raise
            removed = optional.pop()
            history = [h for h in history if h['turn_id'] != removed]
            omitted.append(removed)
    return value, upper, dict(history_ids=[h['turn_id'] for h in history], omitted=omitted)


def paid(engine, config, owner, cid, tid, rid, stage):
    purpose = {'plan':'followup', 'search':'query', 'answer':'answer'}[stage]
    profile = {'plan':'planner-v1', 'search':None, 'answer':'dialogue-v1'}[stage]
    run_id = digest([owner,cid,tid,rid,stage])[:32]
    # Isolated validation corpora can share the application's durable billing ledger.
    ledger_engine = getattr(config, 'ledger_engine', engine)
    with call_slot(ledger_engine, config.embedding_billing_scope) as connection:
        # Prepare and release the owner guard before acquiring billing locks.
        with Session(engine) as db:
            value, upper, context = prepare(db,owner,cid,tid,rid,stage)
        output = value['max_output_tokens'] if stage != 'search' else None
        before_reserve = getattr(config, 'before_reserve', None)
        if before_reserve is not None:
            before_reserve(owner, run_id, stage, value, upper)
        with Session(connection) as db:
            attempt = reserve(db,scope=config.embedding_billing_scope, owner_id=owner,run_id=run_id,
                purpose=purpose,upper=upper,output_limit=output,profile=profile,
                monthly_limit=config.embedding_monthly_limit_micro_usd,
                run_limit={'plan':4000,'search':1000,'answer':10000}[stage],call_limit=1)
            db.commit()
            settle(db,attempt,status='uncertain',error_code='DISPATCH_PENDING')
            db.commit()
        sent = False
        spent = False
        try:
            with Session(engine) as guard:
                checked_value, _, checked_context = prepare(guard,owner,cid,tid,rid,stage)
                if checked_value != value:
                    raise HTTPException(409,'CONVERSATION_CONTEXT_UNAVAILABLE')
                # This separate short transaction never obtains the owner or billing lock.
                with Session(engine) as state:
                    c,t=check_live(state,owner,cid,tid,rid,stage,lock=True,dispatch=True)
                    t.stages = {**t.stages,stage:{**t.stages[stage], 'run_id':run_id,
                        'usage_id':attempt,'payload_hash':digest(value),'dispatch_intent':True}}
                    t.context_summary = {**t.context_summary,stage:checked_context}
                    if stage == 'answer':
                        for source in sources(state,tid):
                            if source.direct_selected:
                                source.dispatch_intent=True
                    remaining=(t.action_expires_at-now()).total_seconds()
                    bump(c)
                    state.commit()
                sent=True
                if stage == 'search':
                    async def query_request():
                        async with asyncio.timeout(min(10, remaining)):
                            return await et.request_embeddings(value,config.openai_api_key.get_secret_value())
                    raw = query_sender(value) if query_sender else asyncio.run(query_request())
                    result,tokens = et.validate_response(raw,1,upper)
                else:
                    sender = planner_sender if stage == 'plan' else answer_sender
                    timeout=min(30 if stage=='plan' else 45,remaining)
                    raw = sender(value) if sender else asyncio.run(at.request(value,config.openai_api_key.get_secret_value(),timeout=timeout))
                    tokens=at.usage(raw,upper,output_limit=output)
            with Session(connection) as db:
                settle(db,attempt,status='spent',**(dict(tokens=tokens) if stage=='search' else
                    dict(input_tokens=tokens[0],output_tokens=tokens[1])))
                db.commit()
            spent=True
            if stage=='search':
                return result[0]
            if stage=='plan':
                return ft.parse(raw)
            return at.parse(raw,{x['id'] for x in json.loads(value['input'])['excerpts']},
                question=json.loads(value['input'])['question'],
                excerpts={x['id']:x['text'] for x in json.loads(value['input'])['excerpts']})
        except BaseException:
            if not spent:
                with Session(connection) as db:
                    settle(db,attempt,status='uncertain' if sent else 'released',
                        error_code='DISPATCH_FAILED' if sent else 'PRE_SEND_BLOCKED')
                    db.commit()
            raise


def begin(engine, owner, cid, tid, data, stage):
    with Session(engine) as db:
        # No source bodies are loaded before their metadata gate.
        shared_lock(db,owner)
        c=conversation(db,owner,cid,True)
        t=turn(db,owner,cid,tid,data.request_id,True)
        if stage in t.stages:
            return False
        if t.state != STATES[stage][0] or t.state in TERMINAL or c.state!='active':
            raise HTTPException(409,'TURN_STAGE_CONFLICT')
        if stage in {'search','evidence'} and t.branch != ('search' if stage=='search' else 'reuse'):
            raise HTTPException(409,'TURN_STAGE_CONFLICT')
        if t.action_expires_at<=now():
            raise HTTPException(409,'TURN_EXPIRED')
        try:
            validate(db,owner,[anchor(s) for s in sources(db,tid)])
        except HTTPException:
            t.state='failed'; t.error_code='CONVERSATION_CONTEXT_UNAVAILABLE'; bump(c); db.commit()
            raise
        t.state=STATES[stage][1]
        t.lease_expires_at=now()+timedelta(seconds=120)
        t.stages={**t.stages,stage:{'claimed':True,'run_id':digest([owner,cid,tid,data.request_id,stage])[:32]}}
        bump(c)
        db.commit()
        return True


def save_selection(db, owner, c, t, vector, config):
    deps=sources(db,t.id)
    existing={key(a):a for a in deps}
    reference=[]
    if t.evidence_reference_turn_id:
        reference=[anchor(a) for a in sources(db,t.evidence_reference_turn_id) if a.direct_selected]
    fresh=[]
    if vector is not None:
        filters={k:date.fromisoformat(v) if k in {"date_from","date_to"} and v else v for k,v in c.filters.items()}
        coverage=index_coverage(db,owner,filters,config)
        if coverage.policy_revision != t.policy_revision or coverage.state!='available':
            raise HTTPException(409,'CONVERSATION_CONTEXT_UNAVAILABLE')
        # Preserve semantic grouping before the top20 limit, without loading source bodies.
        base=search_candidates(owner,filters).add_columns(
            PassageEmbedding.vector.cosine_distance(vector).label('distance')).cte('dialogue_candidates')
        grouped=select(base,func.row_number().over(partition_by=base.c.group_id,
            order_by=[base.c.event_at.desc().nulls_last(),base.c.entry_id.desc(),base.c.embedding_id]).label('position'),
            func.min(base.c.distance).over(partition_by=base.c.group_id).label('group_distance')).cte('dialogue_groups')
        rows=db.execute(select(grouped.c.entry_id,EntryPassage.version_id,EntryPassage.field,EntryPassage.start,
            EntryPassage.end,EntryPassage.passage_hash,EntryPassage.projection_version,EntryPassage.group_key)
            .join(EntryPassage,EntryPassage.id==grouped.c.passage_id).where(grouped.c.position==1)
            .order_by(grouped.c.group_distance,grouped.c.event_at.desc().nulls_last(),grouped.c.embedding_id)
            .limit(20)).mappings()
        seen=set()
        for raw in rows:
            a=dict(raw)
            group=a.pop('group_key')
            identity=('group',group) if group else key(a)
            if identity not in seen:
                fresh.append(a);seen.add(identity)
    candidates=[]
    for a in [*fresh[:1], *reference[:1], *fresh[1:], *reference[1:]]:
        if key(a) not in {key(x) for x in candidates}:
            candidates.append(a)
    validate(db,owner,[anchor(a) for a in deps]+[a for a in candidates if key(a) not in existing])
    if len(set(existing)|{key(a) for a in candidates[:5]})>500:
        raise HTTPException(409,'CONVERSATION_CONTEXT_LIMIT')
    history, omitted, optional=dialogue(db,t)
    selected=[]; omissions=[]
    priority=2 if fresh and reference and key(fresh[0])!=key(reference[0]) else min(1,len(candidates))
    for a in candidates:
        if len(selected)>=5:
            omissions.append('count_limit'); continue
        proxy=Source(**a,selection_order=len(selected))
        # All candidates have passed metadata checks before the first body read.
        body=excerpts(db,owner,[proxy])[0]
        trial=selected+[body]
        while True:
            try:
                at.payload(t.resolved_q or t.q,trial,dialogue=history)
                selected=trial
                row=existing.get(key(a))
                if row is None:
                    row=Source(turn_id=t.id,**a)
                    db.add(row); existing[key(a)]=row
                row.direct_selected=True; row.selection_order=len(selected)-1
                break
            except et.EmbeddingError:
                if optional:
                    removed=optional.pop()
                    history=[h for h in history if h['turn_id']!=removed]; omitted.append(removed)
                else:
                    omissions.append('byte_limit')
                    if len(selected)<priority:
                        selected=[]
                    break
        if not selected and 'byte_limit' in omissions:
            break
    if not selected:
        t.state='completed'; t.outcome='no_evidence'
        t.error_code='byte_limit' if 'byte_limit' in omissions else 'no_hits'
        t.answer='No usable evidence was selected within this question and scope. No answer call was made.'
    else:
        t.state='ready'
    t.context_summary={**t.context_summary,'selection':dict(history_ids=[h['turn_id'] for h in history],
        omitted=omitted,omissions=omissions,selected=len(selected),new_candidates=len(fresh))}


def execute(engine, config, owner, cid, tid, data, stage):
    if not data.confirm_external_ai:
        raise HTTPException(403,'ANSWER_CONSENT_REQUIRED')
    # Existence/ownership is checked before exposing configuration or entering a paid slot.
    with Session(engine) as db:
        conversation(db,owner,cid)
        existing=turn(db,owner,cid,tid,data.request_id)
        if stage in existing.stages:
            return
    if stage == 'search' and config.embedding_mode != 'openai':
        raise HTTPException(503,'EMBEDDING_DISABLED')
    if config.answer_mode!='openai' or not config.openai_api_key or config.embedding_monthly_limit_micro_usd==0:
        raise HTTPException(503,'ANSWER_DISABLED')
    if not begin(engine,owner,cid,tid,data,stage):
        return
    try:
        local_plan=False
        if stage=='plan':
            with Session(engine) as db:
                t=turn(db,owner,cid,tid,data.request_id)
                local_plan=not t.history_ids
        result=None
        if stage=='search':
            with Session(engine) as db:
                c,t,_=checked(db,owner,cid,tid,data.request_id,stage)
                filters={k:date.fromisoformat(v) if k in {'date_from','date_to'} and v else v for k,v in c.filters.items()}
                coverage=index_coverage(db,owner,filters,config)
                if coverage.state!='available':
                    raise HTTPException(409,'CONVERSATION_INDEX_UNAVAILABLE')
        if stage!='evidence' and not local_plan:
            result=paid(engine,config,owner,cid,tid,data.request_id,stage)
        with Session(engine) as db:
            shared_lock(db,owner)
            c,t=check_live(db,owner,cid,tid,data.request_id,stage,lock=True)
            validate(db,owner,[anchor(s) for s in sources(db,tid)])
            if stage=='plan':
                result=result or dict(branch='search',resolved_question=t.q)
                t.branch=result['branch']
                if t.branch=='clarify':
                    pending = [turn(db,owner,cid,hid) for hid in t.history_ids]
                    last = next((h for h in pending if h.outcome=='clarification'),None)
                    origin = last.context_summary.get('pending_origin', last.id) if last else t.id
                    t.context_summary={**t.context_summary,'pending_origin':origin}
                    t.answer=result['question']; t.outcome='clarification'; t.state='completed'
                else:
                    t.resolved_q=result['resolved_question']; t.state='planned'
            elif stage in {'search','evidence'}:
                save_selection(db,owner,c,t,result,config)
            else:
                t.answer=result['answer']; t.answer_status=result['status']; t.outcome='answer'; t.state='completed'
                for source in sources(db,tid):
                    if source.direct_selected:
                        source.cited=(source.selection_order+1) in result['citation_ids']
            bump(c)
            db.commit()
    except BaseException as error:
        with Session(engine) as db:
            try:
                c=conversation(db,owner,cid,True)
                t=turn(db,owner,cid,tid,data.request_id,True)
                if t.state not in TERMINAL:
                    t.state='failed'
                    t.error_code=(error.detail if isinstance(error,HTTPException) else str(error)
                        if isinstance(error,et.EmbeddingError) else 'CONVERSATION_STAGE_FAILED')[:64]
                    bump(c); db.commit()
            except HTTPException:
                pass # Deletion won; never recreate the conversation or turn.
        raise
