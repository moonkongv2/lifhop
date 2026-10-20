"""Fresh-process API probe, restricted to a pytest schema and synthetic owner."""
import json
import re
import sys
import os
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from pydantic import SecretStr
from app.main import app
from app.db import get_db, engine as default_engine
from app.config import settings
from app.security import create_access_token
from app.models.ai_usage import AiUsageAttempt
from app.services import conversation_stages as stages, answer_transport, embedding_transport


data=json.load(sys.stdin)
url=make_url(data['database_url'])
assert url.host in {'localhost','127.0.0.1','::1'} and url.database.endswith('_test')
assert re.fullmatch(r'pytest_[0-9a-f]{32}',data['schema'])
assert data['action'] in {'close','reopen','inspect'}
bind=create_engine(url,connect_args={'options':'-csearch_path='+data['schema']+',public'})


def forbidden(*args,**kwargs):
    raise AssertionError('Fresh-process restore must not dispatch provider calls or open the default DB')


event.listen(default_engine,'do_connect',forbidden)
settings.answer_mode='off';settings.openai_api_key=SecretStr('synthetic-key')
stages.answer_sender=stages.planner_sender=stages.query_sender=forbidden
answer_transport.request=embedding_transport.request_embeddings=forbidden
import httpx
httpx.AsyncClient.send=forbidden
import boto3
boto3.client=boto3.resource=boto3.Session=forbidden


def fixture_db():
    with Session(bind) as db:
        assert db.scalar(text('SELECT current_schema()'))==data['schema']
        yield db


def usage():
    with Session(bind) as db:
        return [(r.id,r.status,r.reserved_micro_usd,r.spent_micro_usd) for r in db.scalars(
            select(AiUsageAttempt).where(AiUsageAttempt.owner_id==data['owner']).order_by(AiUsageAttempt.id))]


app.dependency_overrides[get_db]=fixture_db
before=usage()
with TestClient(app) as client:
    headers={'Authorization':'Bearer '+create_access_token(data['owner'])}
    base='/answer-conversations/'+data['conversation_id']
    response=client.get(base,headers=headers)
    assert response.status_code==200,response.text
    conversation=response.json()
    if data['action']!='inspect':
        response=client.post(base+'/'+data['action'],headers=headers,json={'expected_revision':conversation['revision']})
        assert response.status_code==200,response.text
        conversation=response.json()
assert usage()==before
print(json.dumps(dict(pid=os.getpid(),conversation=conversation,usage_rows=len(before),usage_unchanged=True)))
bind.dispose()
