"""Bounded pilot guards; offline/dry-run completion is not semantic acceptance."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt
from app.services import answer_transport as at, followup_transport as ft, embedding_transport as et

ROOT=Path(__file__).resolve().parents[2]


class PilotError(Exception):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def preflight(proposal, approval_digest, fresh):
    content={k:v for k,v in proposal.items() if k!='digest'}
    if proposal.get('digest')!=digest(content) or proposal!=fresh:
        raise PilotError('FOLLOWUP_PROPOSAL_STALE')
    if approval_digest!=proposal['digest']:
        raise PilotError('FOLLOWUP_APPROVAL_REQUIRED')
    limits={
        'followup-validation-synthetic-v1':(18,79537,dict(document=1,planner=6,query=4,answer=7)),
        'followup-quality-recheck-v1':(7,29279,dict(document=1,planner=1,query=2,answer=3)),
    }
    if (proposal.get('version') not in limits or
            (proposal['max_total_calls'],proposal['max_micro_usd'],proposal['max_calls'])!=limits[proposal['version']]):
        raise PilotError('FOLLOWUP_LIMIT_MISMATCH')


class PilotGuard:
    def __init__(self,proposal,output,*,fresh,ledger_engine,owner,dry_run):
        self.proposal=proposal;self.output=Path(output);self.fresh=fresh
        self.ledger_engine=ledger_engine;self.owner=owner;self.dry_run=dry_run
        self.stage=None;self.turn=None;self.action_deadline=None;self.calls=[];self.started=time.monotonic()
        caps=proposal['max_calls']
        self.maxima={'document':caps['document'],'plan':caps['planner'],'search':caps['query'],'answer':caps['answer']}

    def check(self):
        preflight(self.proposal,self.proposal['digest'],self.fresh())
        if time.monotonic()-self.started>1200:
            raise PilotError('FOLLOWUP_RUN_DEADLINE')

    def ledger(self):
        with Session(self.ledger_engine) as db:
            rows=list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==self.owner)))
            return [dict(id=r.id,run_id=r.run_id,status=r.status,purpose=r.purpose,
                reserved_micro_usd=r.reserved_micro_usd,spent_micro_usd=r.spent_micro_usd,
                input_upper_bound=r.input_upper_bound,output_upper_bound=r.output_upper_bound,
                input_tokens=r.input_usage_tokens,output_tokens=r.output_usage_tokens,
                model=r.model,configuration_hash=r.configuration_hash) for r in rows]

    def before_reserve(self,owner,run_id,stage,value,upper):
        self.check()
        if owner!=self.owner or stage!=self.stage:
            raise PilotError('FOLLOWUP_STAGE_SCOPE')
        if any(c['run_id']==run_id for c in self.calls):
            raise PilotError('FOLLOWUP_REPLAY_BLOCKED')
        if sum(c['stage']==stage for c in self.calls)>=self.maxima[stage] or len(self.calls)>=self.proposal['max_total_calls']:
            raise PilotError('FOLLOWUP_CALL_LIMIT')
        if stage=='plan' and (self.turn is None or not self.turn['planner']):
            raise PilotError('FOLLOWUP_UNAPPROVED_PLANNER')
        expected_upper=(et.input_bound(value,query=stage=='search') if stage in {'document','search'} else
            len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())+1024)
        if upper!=expected_upper:
            raise PilotError('FOLLOWUP_INPUT_BOUND_MISMATCH')
        if stage in {'plan','answer'}:
            if (value.get('model')!=self.proposal['models']['generation'] or value.get('store') is not False or
                    value.get('max_output_tokens')!=(1024 if stage=='plan' else 4096) or
                    upper>(25600 if stage=='plan' else 66560)):
                raise PilotError('FOLLOWUP_WIRE_LIMIT')
        rows=self.ledger()
        if any(r['status'] in {'reserved','uncertain'} for r in rows):
            raise PilotError('FOLLOWUP_OUTSTANDING_USAGE')
        amount=(ft.cost_micro(upper,1024) if stage=='plan' else at.cost_micro(upper,4096)
            if stage=='answer' else et.cost_micro(upper))
        charged=sum(r['spent_micro_usd'] for r in rows if r['status']=='spent')
        if charged+amount>self.proposal['max_micro_usd']:
            raise PilotError('FOLLOWUP_PILOT_BUDGET')
        if stage=='document':
            if value!=[r['content'] for r in self.proposal['corpus']]:
                raise PilotError('FOLLOWUP_DOCUMENT_SCOPE')
        elif stage=='plan':
            if json.loads(value['input'])['question']!=self.turn['q']:
                raise PilotError('FOLLOWUP_QUESTION_SCOPE')
        elif stage=='search':
            et.input_bound(value,query=True)
        elif stage=='answer':
            payload=json.loads(value['input'])
            if self.turn['context_mode']=='fresh' and payload['dialogue']:
                raise PilotError('FOLLOWUP_FRESH_CONTEXT_LEAK')
            corpus=[r['content'] for r in self.proposal['corpus']]
            if not payload['excerpts'] or any(p['text'] not in corpus for p in payload['excerpts']):
                raise PilotError('FOLLOWUP_SOURCE_SCOPE')
        item=dict(index=len(self.calls)+1,stage=stage,turn=self.turn['id'] if self.turn else None,
            run_id=run_id,payload_hash=digest(value),input_upper=upper,max_micro_usd=amount)
        self.calls.append(item)
        self.write(f'{item["index"]:02}-{stage}-request.json',dict(audit=item,payload=value))

    def transport(self,stage,value,key):
        import asyncio
        self.check()
        start=time.monotonic()
        remaining=(self.action_deadline-datetime.now(timezone.utc)).total_seconds() if self.action_deadline else 120
        if remaining<=0:raise PilotError('FOLLOWUP_ACTION_DEADLINE')
        if not self.dry_run:
            async def dispatch():
                async with asyncio.timeout(min(remaining,10 if stage in {'document','search'} else 45 if stage=='answer' else 30)):
                    return await (et.request_embeddings(value,key) if stage in {'document','search'} else
                        at.request(value,key,timeout=min(remaining,45 if stage=='answer' else 30)))
            raw=asyncio.run(dispatch())
        elif stage in {'document','search'}:
            raw=dict(model=et.MODEL,data=[dict(index=i,embedding=[1.0]+[0.0]*1535) for i in range(len(value))],
                usage=dict(prompt_tokens=len(value),total_tokens=len(value)))
        else:
            if stage=='plan':
                result=(dict(branch='clarify',question='알파와 베타 중 어느 업체인가요?') if self.turn['branch']=='clarify'
                    else dict(branch=self.turn['branch'],resolved_question=self.turn['q']))
            else:
                excerpts=json.loads(value['input'])['excerpts']
                result=dict(parts=[dict(kind='answered',request='합성 실행기 검사',facts=[dict(text='[Synthetic] 실행기 검사용 답변입니다.',
                    evidence=[dict(id=excerpts[0]['id'],quote=excerpts[0]['text'][:100])])])])
            raw=dict(model=at.MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),
                output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(result=result)))])])
        item=self.calls[-1]
        self.write(f'{item["index"]:02}-{stage}-response.json',dict(raw=raw,elapsed_seconds=time.monotonic()-start))
        return raw

    def write(self,name,value):
        path=self.output/name
        with path.open('x',encoding='utf-8') as f:
            import os
            os.chmod(path,0o600)
            json.dump(value,f,ensure_ascii=False,indent=2,default=str)
