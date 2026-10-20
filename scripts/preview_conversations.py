"""Loopback-only saved-conversation demo in a disposable test schema; no AI egress."""
import argparse
import json
import threading
from types import SimpleNamespace
from uuid import uuid4
import httpx
import uvicorn
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select, text, func
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.main import app
from app.models.entry import Entry, EntryType
from app.models.user import User
from app.models.ai_usage import AiUsageAttempt
from app.security import hash_password
from app.services.source_history import record_version, select_version, source_policy
from app.services.embedding_store import slice_anchors, publish_embeddings
from app.models.passage import EntryPassage
from app.services import conversation_stages as stages
from app.services.answer_transport import MODEL
from app.services.embedding_transport import MODEL as EMBEDDING_MODEL


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url',default='postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test')
    parser.add_argument('--port',type=int,default=8003)
    args=parser.parse_args(argv)
    url=make_url(args.database_url)
    if url.host not in {'localhost','127.0.0.1','::1'} or not (url.database or '').endswith('_test'):
        parser.error('Only loopback disposable databases ending in _test are allowed')
    bind=create_engine(url)
    schema='conversation_demo_'+uuid4().hex
    with bind.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        config=Config('alembic.ini',toml_file='pyproject.toml')
        config.attributes['connection']=connection
        command.upgrade(config,'head')
    def checkout(connection,record,proxy):
        previous=connection.autocommit
        connection.autocommit=True
        try:
            with connection.cursor() as cursor:cursor.execute(f'SET search_path TO "{schema}", public')
        finally:connection.autocommit=previous
    event.listen(bind,'checkout',checkout)
    release=threading.Event()
    calls={'plan':0,'query':0,'answer':0}
    lock=threading.Lock()
    def count(stage):
        with lock:calls[stage]+=1
    def raw(result):
        return dict(model=MODEL,status='completed',usage=dict(input_tokens=10,output_tokens=10,total_tokens=20),
            output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(dict(result=result)))])])
    def fake_query(inputs):
        count('query')
        return dict(model=EMBEDDING_MODEL,data=[dict(index=0,embedding=[1.0]+[0.0]*1535)],
            usage=dict(prompt_tokens=1,total_tokens=1))
    def fake_plan(value):
        count('plan')
        q=json.loads(value['input'])['question']
        if 'ambiguous' in q.lower():return raw(dict(branch='clarify',question='Which synthetic company do you mean?'))
        branch='search' if any(x in q.lower() for x in ['later','cancel']) else 'reuse'
        return raw(dict(branch=branch,resolved_question=q))
    def fake_answer(value):
        count('answer')
        content=json.loads(value['input'])
        if 'slow' in content['question'].lower():
            release.clear();release.wait(20)
        first=content['excerpts'][0]
        return raw(dict(parts=[dict(request='Synthetic recorded fact.',kind='answered',facts=[dict(
            text='[Synthetic] '+first['text'][:120],evidence=[dict(id=first['id'],quote=first['text'][:120])])])]))
    def forbidden(*args,**kwargs):
        raise RuntimeError('External AI and AWS calls are disabled in the synthetic demo')
    try:
        # Even routes outside this demo's workflow must not connect to the personal engine.
        import app.db as database
        event.listen(database.engine, 'do_connect', forbidden)
        database.engine=bind
        settings.jwt_secret_key='disposable-conversation-'+uuid4().hex
        runtime=SimpleNamespace(embedding_mode='openai',answer_mode='openai',openai_api_key=SecretStr('synthetic-key'),
            embedding_monthly_limit_micro_usd=1000000,embedding_billing_scope='demo-'+uuid4().hex)
        with Session(bind) as db:
            assert db.scalar(text('SELECT current_schema()'))==schema
            for email in ['demo@example.test','other@example.test']:
                user=User(email=email,password_hash=hash_password('demo-password'))
                db.add(user);db.flush()
                if email.startswith('other'):continue
                source_policy(db,user.id,'manual').external_ai_allowed=True
                for title,body in [('[Synthetic] Worker location','The worker runs on the deployment server.'),
                    ('[Synthetic] Company comparison','Company Alpha was compared with Company Beta. A booking request was recorded.'),
                    ('[Synthetic] Later cancellation','A later cancellation request was recorded. Completion was not confirmed.')]:
                    entry=Entry(user_id=user.id,provider='manual',type=EntryType.NOTE,title=title,content=body,external_ai_allowed=True)
                    db.add(entry);select_version(db,entry,record_version(db,entry));db.flush()
                    revision=db.get(User,user.id).policy_revision
                    anchors=[a for pid in db.scalars(select(EntryPassage.id).where(EntryPassage.version_id==entry.current_version_id,
                        EntryPassage.field=='content')) for a in slice_anchors(db,user_id=user.id,passage_id=pid,revision=revision)]
                    publish_embeddings(db,user_id=user.id,revision=revision,anchors=anchors,vectors=[[1.0]+[0.0]*1535 for _ in anchors])
            db.commit()
        import app.api.answer_conversations as api
        import app.api.answers as answers
        import app.api.semantic as semantic
        api.engine=bind;api.settings=runtime
        answers.settings=runtime;semantic.settings=runtime
        stages.planner_sender=fake_plan;stages.query_sender=fake_query;stages.answer_sender=fake_answer
        # Provider fallback must fail locally even if demo transport wiring regresses.
        httpx.AsyncClient.send=forbidden
        import boto3
        boto3.client=boto3.resource=boto3.Session=forbidden
        def demo_db():
            with Session(bind) as db:yield db
        app.dependency_overrides[get_db]=demo_db
        @app.get('/__demo/status')
        def status():
            with Session(bind) as db:
                rows=list(db.execute(select(AiUsageAttempt.status,func.count()).group_by(AiUsageAttempt.status)))
            return dict(synthetic=True,calls=calls.copy(),usage=dict(rows))
        @app.post('/__demo/release')
        def release_call():
            release.set();return dict(released=True)
        print(f'Synthetic conversation API http://127.0.0.1:{args.port}; schema {schema}',flush=True)
        print('Demo login: demo@example.test / demo-password; second user: other@example.test / demo-password',flush=True)
        uvicorn.run(app,host='127.0.0.1',port=args.port,log_level='warning',access_log=False)
    finally:
        release.set()
        app.dependency_overrides.clear()
        event.remove(bind,'checkout',checkout)
        with bind.begin() as connection:connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        bind.dispose()


if __name__=='__main__':main()
