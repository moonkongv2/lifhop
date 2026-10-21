"""Synthetic-only recovery dry-run. No live mode, personal corpus or external AI."""
import argparse
from copy import deepcopy
from importlib.util import module_from_spec,spec_from_file_location
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.main import app
from app.models.user import User
from app.models.entry import Entry,EntryType
from app.models.ai_usage import AiUsageAttempt
from app.models.passage import EntryPassage
from app.services.source_history import source_policy,record_version,select_version
from app.services.embedding_store import slice_anchors,publish_embeddings
from app.services import answer_transport as at,embedding_transport as et
from app.evaluation.conversation_recovery import Assessment,RecoveryCase,RecoverySession
from app.evaluation.storage import PRIVATE_ROOT,write_private,private_directory
from app.security import create_access_token

_spec=spec_from_file_location('recovery_fixture',Path(__file__).with_name('run_c3_validation.py'))
_module=module_from_spec(_spec);_spec.loader.exec_module(_module)


class DryTransport:
    def __init__(self,fixture,owner,session):
        self.fixture=fixture;self.owner=owner;self.session=session;self.calls=[];self.attempt=0;self.stage=None

    def before_reserve(self,owner,run_id,stage,value,upper):
        if owner!=self.owner or stage!=self.stage:raise ValueError('RECOVERY_STAGE_SCOPE')
        if any(c['run_id']==run_id for c in self.calls):raise ValueError('RECOVERY_REPLAY')
        limit=0 if stage=='plan' and self.attempt==0 else 1
        if sum(c['attempt']==self.attempt and c['stage']==stage for c in self.calls)>=limit:
            raise ValueError('RECOVERY_CALL_LIMIT')
        if len(self.calls)>=self.session.case.envelope()['total_max_calls']:raise ValueError('RECOVERY_CALL_LIMIT')
        expected=et.input_bound(value,query=True) if stage=='search' else len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())+1024
        if expected!=upper:raise ValueError('RECOVERY_INPUT_BOUND')
        if stage!='search':
            body=json.loads(value['input'])
            if stage=='plan' and body['question']!=self.session.questions[-1]:raise ValueError('RECOVERY_QUESTION_SCOPE')
            if stage=='answer' and any(e['text'] not in [self.fixture['decision'],self.fixture['commit'],*self.fixture['fillers']] for e in body['excerpts']):
                raise ValueError('RECOVERY_SOURCE_SCOPE')
        self.calls.append(dict(attempt=self.attempt,stage=stage,run_id=run_id,payload=deepcopy(value)))

    def transport(self,stage,value,key):
        assert self.calls[-1]['payload']==value and self.calls[-1]['stage']==stage
        if stage=='search':
            # Deliberately scripted vectors validate branching, not retrieval accuracy.
            vector=[1.0,0.0] if self.attempt==0 else [0.0,1.0]
            return dict(model=et.MODEL,data=[dict(index=0,embedding=vector+[0.0]*1534)],
                usage=dict(prompt_tokens=1,total_tokens=1))
        body=json.loads(value['input'])
        if stage=='plan':
            assert body['dialogue'] and body['dialogue'][0]['question']==self.fixture['case']['initial_question']
            result=dict(branch='search',resolved_question='Find the implementation commit for the optional linked deletion policy.')
        else:
            commit=next((e for e in body['excerpts'] if e['text']==self.fixture['commit']),None)
            if commit:
                result=dict(parts=[dict(request='Implementation record',kind='answered',facts=[dict(
                    text=commit['text'],evidence=[dict(id=commit['id'],quote=commit['text'])])])])
            else:
                decision=next(e for e in body['excerpts'] if e['text']==self.fixture['decision'])
                result=dict(parts=[dict(request='Policy and implementation record',kind='unresolved',known=[dict(
                    text=decision['text'],evidence=[dict(id=decision['id'],quote=decision['text'])])],
                    gap='The implementation commit is not established in these selected excerpts.')])
        return dict(model=at.MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),
            output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(result=result)))])])


def seed(bind,fixture,owner):
    bodies=[fixture['decision'],*fixture['fillers'],fixture['commit']]
    with Session(bind) as db:
        db.add(User(id=owner,email='recovery@example.test',password_hash='not-a-login'));db.flush()
        source_policy(db,owner,'manual').external_ai_allowed=True
        entries=[]
        for index,body in enumerate(bodies):
            entry=Entry(user_id=owner,provider='manual',type=EntryType.NOTE,title='Synthetic fixture '+str(index),
                content=body,external_ai_allowed=True)
            db.add(entry);select_version(db,entry,record_version(db,entry));db.flush();entries.append(entry.id)
        db.commit()
        revision=db.get(User,owner).policy_revision
        for index,eid in enumerate(entries):
            entry=db.get(Entry,eid)
            anchors=[a for pid in db.scalars(select(EntryPassage.id).where(EntryPassage.version_id==entry.current_version_id,
                EntryPassage.field=='content')) for a in slice_anchors(db,user_id=owner,passage_id=pid,revision=revision)]
            pair=[1.0,0.0] if index==0 else [0.0,1.0] if index==len(bodies)-1 else [1.0,0.2]
            publish_embeddings(db,user_id=owner,revision=revision,anchors=anchors,vectors=[pair+[0.0]*1534 for _ in anchors])
        db.commit()
    return entries[-1]


def dry_run(database_url,output):
    fixture=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/conversation_recovery.json').read_text())
    session=RecoverySession(RecoveryCase.model_validate(fixture['case']),synthetic=True)
    output=output.absolute()
    if output.exists():raise ValueError('RECOVERY_OUTPUT_EXISTS')
    private_directory(output,PRIVATE_ROOT)
    owner=-734201
    with _module.fixture_database(database_url) as (bind,schema):
        commit_entry=seed(bind,fixture,owner)
        guard=DryTransport(fixture,owner,session)
        runtime=SimpleNamespace(answer_mode='openai',embedding_mode='openai',openai_api_key=SecretStr('synthetic-key'),
            embedding_billing_scope='recovery-dry-'+uuid4().hex,embedding_monthly_limit_micro_usd=1000000,
            ledger_engine=bind,before_reserve=guard.before_reserve)
        snapshots=[]
        with _module.wiring(bind,runtime,guard,dry_run=True),TestClient(app) as client:
            headers={'Authorization':'Bearer '+create_access_token(owner)}
            def request(method,path,body=None):
                response=client.request(method,path,headers=headers,json=body)
                if response.status_code not in {200,201}:raise ValueError('RECOVERY_HTTP_'+str(response.status_code))
                return response.json()
            c=request('POST','/answer-conversations',{});base='/answer-conversations/'+c['id']
            question=session.start();branch='search';first=None
            while question is not None:
                c=request('POST',base+'/turns',dict(q=question,request_id=uuid4().hex,
                    expected_revision=c['revision'],context_mode='continue',confirm_external_ai=True))
                tid=c['turns'][-1]['id']
                def step(stage):
                    guard.stage=stage
                    return request('POST',base+f'/turns/{tid}/{stage}',dict(request_id=c['turns'][-1]['request_id'],confirm_external_ai=True))
                c=step('plan');assert c['turns'][-1]['branch']==branch
                c=step('search' if branch=='search' else 'evidence')
                assert c['turns'][-1]['state']=='ready'
                c=step('answer');t=c['turns'][-1]
                assert t['state']=='completed' and t['outcome']=='answer'
                if first is None:first=deepcopy(t)
                recovered=fixture['commit'] in t['answer'] and any(a['entry_id']==commit_entry for a in t['citations'])
                if guard.attempt==0:assert not recovered and t['answer_status']=='partial'
                else:assert c['turns'][0]==first
                # Fixture truth is kept outside provider inputs and is never a live quality score.
                session.record(Assessment(verdict='passed' if recovered else 'partial',reviewer='synthetic-oracle',
                    notes='Synthetic wiring check: commit statement plus exact source citation.' if recovered else
                    'Synthetic initial selection omitted the commit.'))
                snapshots.append(c)
                followup=session.next_followup()
                question=followup.question if followup else None
                branch=followup.branch if followup else 'search';guard.attempt+=1
            with Session(bind) as db:
                usage=[dict(status=r.status,purpose=r.purpose,spent_micro_usd=r.spent_micro_usd) for r in db.scalars(select(AiUsageAttempt))]
        report=session.report()
        assert report['first_response']['verdict']=='partial' and report['conversation_verdict']=='passed'
        assert report['followups_used']==1 and len(guard.calls)==5 and all(r['status']=='spent' for r in usage)
        report.update(state='completed',provider_calls=0,personal_db_reads=0,personal_db_writes=0,
            synthetic_calls=len(guard.calls),first_turn_unchanged=True,new_search_on_followup=True,
            second_followup_not_sent=True,synthetic_ledger=usage)
        write_private(output/'requests.json',guard.calls,root=PRIVATE_ROOT)
        write_private(output/'saved-conversation.json',snapshots,root=PRIVATE_ROOT)
    report['isolated_schema_removed']=True
    write_private(output/'report.json',report,root=PRIVATE_ROOT)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--database-url',default='postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test')
    args=parser.parse_args(argv)
    report=dry_run(args.database_url,args.out)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
