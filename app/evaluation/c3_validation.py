"""Finite C3 protocol, corpus and dispatch guards. No implicit execution approval."""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.evaluation.schemas import digest
from app.evaluation.retrieval import database_identity
from app.evaluation.storage import PRIVATE_ROOT, read_private, write_private
from app.models.ai_usage import AiUsageAttempt
from app.models.answer_conversation import AnswerTurn, AnswerTurnSource
from app.models.passage import EntryPassage
from app.models.user import User
from app.api.passages import search_filters
from app.services.semantic_search import candidates
from app.services.conversation_context import anchor, excerpts
from app.services import answer_transport as at, followup_transport as ft, embedding_transport as et

ROOT=Path(__file__).resolve().parents[2]


class C3Error(Exception):
    pass


def normalized(value):
    return json.loads(json.dumps(value,default=str))


def code_hashes():
    files=[*ROOT.glob('app/**/*.py'),*ROOT.glob('scripts/**/*.py'),ROOT/'tests/test_c3_validation.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files) if p.is_file()}


def corpus_metadata(db,owner):
    base=candidates(owner,search_filters()).subquery()
    rows=db.execute(select(base,EntryPassage.field,EntryPassage.start.label('parent_start'),
        EntryPassage.end.label('parent_end'),EntryPassage.passage_hash.label('parent_hash'),
        EntryPassage.projection_version).join(EntryPassage,EntryPassage.id==base.c.passage_id)
        .order_by(base.c.embedding_id)).mappings()
    return normalized([dict(r) for r in rows])


def ledger_rows(db,ids=None):
    query=select(AiUsageAttempt.__table__).order_by(AiUsageAttempt.id)
    if ids is not None:query=query.where(AiUsageAttempt.id.in_(ids))
    return normalized([dict(r) for r in db.execute(query).mappings()])


def validate_protocol(protocol,approval=None,*,dry_run=False):
    if digest({k:v for k,v in protocol.items() if k!='digest'})!=protocol.get('digest'):
        raise C3Error('C3_PROTOCOL_CHANGED')
    if not dry_run and approval!=protocol['digest']:
        raise C3Error('C3_APPROVAL_REQUIRED')
    if protocol.get('version')!='phase33-c3-executable-v1' or protocol['code_hashes']!=code_hashes():
        raise C3Error('C3_CODE_CHANGED')
    scope=protocol['scope']
    if digest({k:v for k,v in scope.items() if k!='digest'})!=scope['digest']:
        raise C3Error('C3_SCOPE_CHANGED')
    if (scope['limits']['calls']!=13 or scope['limits']['max_micro_usd']!=64205 or
        scope['max_calls']!=dict(answer=7,planner=1,query=5) or
        [a['id'] for a in scope['actions']]!=['S1','R1','R2','R3','R4','R5','R6'] or
        sum(sum(a['max_calls'].values()) for a in scope['actions'])!=13 or
        sum(a['max_micro_usd'] for a in scope['actions'])!=64205):
        raise C3Error('C3_ENVELOPE_CHANGED')
    if protocol['configs']!=dict(answer=at.DIALOGUE_CONFIG_HASH,planner=ft.CONFIG_HASH,embedding=et.CONFIG):
        raise C3Error('C3_CONFIG_CHANGED')


def check_source(engine,protocol):
    with engine.connect().execution_options(isolation_level='REPEATABLE READ',postgresql_readonly=True) as connection:
        with connection.begin(),Session(connection) as db:
            if (database_identity(db)!=protocol['scope']['database'] or
                db.scalar(select(User.policy_revision).where(User.id==protocol['scope']['owner_id']))!=protocol['scope']['policy_revision'] or
                corpus_metadata(db,protocol['scope']['owner_id'])!=protocol['metadata']['rows']):
                raise C3Error('C3_CORPUS_OR_POLICY_CHANGED')
            if digest(ledger_rows(db,protocol['old_usage_ids']))!=protocol['old_usage_digest']:
                raise C3Error('C3_OLD_USAGE_CHANGED')


def prepare_protocol(scope_path,source_engine):
    scope=read_private(scope_path,PRIVATE_ROOT)
    metadata=read_private(scope_path.parent/'corpus-metadata.json',PRIVATE_ROOT)
    if (digest({k:v for k,v in scope.items() if k!='digest'})!=scope['digest'] or
        digest({k:v for k,v in metadata.items() if k!='digest'})!=metadata['digest'] or
        metadata['digest']!=scope['corpus_metadata_digest']):
        raise C3Error('C3_SCOPE_CHANGED')
    with source_engine.connect().execution_options(isolation_level='REPEATABLE READ',postgresql_readonly=True) as connection:
        with connection.begin(),Session(connection) as db:
            old=ledger_rows(db)
    result=dict(version='phase33-c3-executable-v1',state='prepared-not-authorized',scope=scope,
        metadata=metadata,code_hashes=code_hashes(),
        configs=dict(answer=at.DIALOGUE_CONFIG_HASH,planner=ft.CONFIG_HASH,embedding=et.CONFIG),
        old_usage_ids=[r['id'] for r in old],old_usage_digest=digest(old))
    result['digest']=digest(result)
    validate_protocol(result,dry_run=True)
    check_source(source_engine,result)
    return result


class C3Guard:
    def __init__(self,protocol,output,source_engine,work_engine,ledger_engine,*,dry_run):
        self.protocol=protocol;self.output=output;self.source_engine=source_engine
        self.work_engine=work_engine;self.ledger_engine=ledger_engine;self.dry_run=dry_run
        self.started=time.monotonic();self.calls=[];self.action=None;self.stage=None
        self.cid=None;self.tid=None;self.deadline=None;self.base_tid=None

    def write(self,name,value):
        write_private(self.output/name,normalized(value),root=PRIVATE_ROOT)

    def check(self):
        validate_protocol(self.protocol,self.protocol['digest'],dry_run=self.dry_run)
        if time.monotonic()-self.started>1200:raise C3Error('C3_RUN_DEADLINE')
        check_source(self.source_engine,self.protocol)

    def usage(self):
        ids=[c['run_id'] for c in self.calls]
        with Session(self.ledger_engine) as db:
            return list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.run_id.in_(ids))))

    def before_reserve(self,owner,run_id,stage,value,upper):
        self.check()
        action=self.action;scope=self.protocol['scope'];purpose={'plan':'planner','search':'query','answer':'answer'}[stage]
        expected_owner=(-int(self.protocol['digest'][:7],16)-1 if action['id']=='S1' else scope['owner_id'])
        if owner!=expected_owner or stage!=self.stage:raise C3Error('C3_STAGE_SCOPE')
        if run_id in {c['run_id'] for c in self.calls}:raise C3Error('C3_REPLAY')
        if sum(c['purpose']==purpose for c in self.calls)>=scope['max_calls'][purpose]:raise C3Error('C3_CALL_LIMIT')
        if sum(c['action']==action['id'] and c['purpose']==purpose for c in self.calls)>=action['max_calls'].get(purpose,0):
            raise C3Error('C3_ACTION_CALL_LIMIT')
        expected_upper=et.input_bound(value,query=True) if stage=='search' else len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())+1024
        if upper!=expected_upper:raise C3Error('C3_INPUT_BOUND')
        if stage!='search' and (value.get('store') is not False or value.get('model')!=at.MODEL or
            value.get('max_output_tokens')!=(1024 if stage=='plan' else 4096) or
            upper>(25600 if stage=='plan' else 66560)):
            raise C3Error('C3_WIRE_SCOPE')
        rows=self.usage()
        if any(r.status in {'reserved','uncertain'} for r in rows):raise C3Error('C3_OUTSTANDING_USAGE')
        cost=et.cost_micro(upper) if stage=='search' else ft.cost_micro(upper,1024) if stage=='plan' else at.cost_micro(upper,4096)
        if sum(r.spent_micro_usd for r in rows)+cost>64205:raise C3Error('C3_BUDGET')
        if sum(c['max_micro_usd'] for c in self.calls if c['action']==action['id'])+cost>action['max_micro_usd']:
            raise C3Error('C3_ACTION_BUDGET')
        if action['id']=='S1':
            if value!=action['request']:raise C3Error('C3_SYNTHETIC_SCOPE')
        else:
            with Session(self.work_engine) as db:
                t=db.get(AnswerTurn,self.tid)
                if not t or t.q!=action['question'] or t.conversation_id!=self.cid or t.user_id!=owner:
                    raise C3Error('C3_QUESTION_SCOPE')
                body=json.loads(value['input']) if stage!='search' else None
                if action['context_mode']=='fresh' and (t.history_ids or t.base_turn_id or t.evidence_reference_turn_id):
                    raise C3Error('C3_FRESH_CONTEXT_LEAK')
                if action['id']=='R5' and (t.base_turn_id!=self.base_tid or set(t.history_ids)!={self.base_tid}):
                    raise C3Error('C3_BASE_SCOPE')
                if stage=='search':
                    if value!=[action['question']] or t.resolved_q!=action['question']:raise C3Error('C3_QUERY_SCOPE')
                else:
                    from app.services.conversation_stages import dialogue
                    history,_,_=dialogue(db,t)
                    # prepare may remove optional turns; this protocol has exactly one required base.
                    if body.get('dialogue')!=history:raise C3Error('C3_HISTORY_SCOPE')
                    if stage=='plan':
                        expected,_=ft.payload(action['question'],history)
                    else:
                        selected=list(db.scalars(select(AnswerTurnSource).where(AnswerTurnSource.turn_id==self.tid,
                            AnswerTurnSource.direct_selected.is_(True)).order_by(AnswerTurnSource.selection_order)))
                        allowed={(r['entry_id'],r['version_id'],r['field'],r['parent_start'],r['parent_end'],r['parent_hash'],r['projection_version']) for r in self.protocol['metadata']['rows']}
                        for source in selected:
                            a=anchor(source)
                            if tuple(a[k] for k in ['entry_id','version_id','field','start','end','passage_hash','projection_version']) not in allowed:
                                raise C3Error('C3_SOURCE_SCOPE')
                        expected,_=at.payload(t.resolved_q or t.q,excerpts(db,owner,selected),dialogue=history)
                    if value!=expected:raise C3Error('C3_PAYLOAD_SCOPE')
        item=dict(action=action['id'],stage=stage,purpose=purpose,run_id=run_id,input_upper=upper,
            max_micro_usd=cost,payload_hash=digest(value))
        self.calls.append(item)
        self.write(f'{len(self.calls):02}-{stage}-request.json',dict(audit=item,payload=value))

    def transport(self,stage,value,key):
        self.check()
        if not self.calls or self.calls[-1]['payload_hash']!=digest(value) or self.calls[-1]['stage']!=stage:
            raise C3Error('C3_UNGUARDED_TRANSPORT')
        remaining=(self.deadline-datetime.now(timezone.utc)).total_seconds()
        if remaining<=0:raise C3Error('C3_ACTION_DEADLINE')
        start=time.monotonic()
        if self.dry_run:
            if stage=='search':
                raw=dict(model=et.MODEL,data=[dict(index=0,embedding=[1.0]+[0.0]*1535)],usage=dict(prompt_tokens=1,total_tokens=1))
            else:
                body=json.loads(value['input'])
                result=(dict(branch='reuse',resolved_question=self.action['question']) if stage=='plan' else
                    dict(parts=[dict(kind='answered',request='Dry-run wiring only',facts=[dict(text='[Dry run] Not a quality judgment.',
                        evidence=[dict(id=body['excerpts'][0]['id'],quote=body['excerpts'][0]['text'][:100])])])]))
                raw=dict(model=at.MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),
                    output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(result=result)))])])
        else:
            async def send():
                async with asyncio.timeout(min(remaining,10 if stage=='search' else 30 if stage=='plan' else 45)):
                    return await (et.request_embeddings(value,key) if stage=='search' else at.request(value,key,
                        timeout=min(remaining,30 if stage=='plan' else 45)))
            raw=asyncio.run(send())
        self.write(f'{len(self.calls):02}-{stage}-response.json',dict(raw=raw,seconds=time.monotonic()-start))
        return raw
