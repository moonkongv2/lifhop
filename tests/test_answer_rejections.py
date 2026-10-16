"""Real HTTP transport with synthetic streams; no external requests."""
import asyncio
import json
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt
from app.services.answer_transport import AnswerProviderError, request, payload
from app.evaluation.answer_run import capturing_answer
from app.evaluation.storage import read_private
from test_answers import answer_client, ask
from test_embedding_jobs import actor


SECRET='private source text / synthetic-secret'


def mock_http(monkeypatch, handler):
    original=httpx.AsyncClient
    calls=[]
    def tracked(req):
        calls.append(req)
        return handler(req)
    def client(**kwargs):
        assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        return original(transport=httpx.MockTransport(tracked), **kwargs)
    monkeypatch.setattr(httpx,'AsyncClient',client)
    return calls


def rejected_body():
    return dict(error=dict(type='invalid_request_error',code='invalid_json_schema',
        param='text.format.schema',message=SECRET),extra=SECRET)


def test_http_rejection_keeps_only_allowlisted_metadata(monkeypatch):
    calls=mock_http(monkeypatch,lambda req:httpx.Response(400,json=rejected_body()))
    value,_=payload('Synthetic question?', [dict(id=4,text='Synthetic evidence')])
    with pytest.raises(AnswerProviderError) as error:
        asyncio.run(request(value,'synthetic-api-key'))
    assert str(error.value)=='ANSWER_PROVIDER_REJECTED'
    assert error.value.diagnostic()==dict(http_status=400,error_type='invalid_request_error',
        error_code='invalid_json_schema',error_param='text.format.schema')
    assert SECRET not in repr(vars(error.value))
    assert len(calls)==1 and str(calls[0].url)=='https://api.openai.com/v1/responses'


@pytest.mark.parametrize('body', [
    '<html>'+SECRET+'</html>',
    'x'*8193,
    json.dumps(dict(error=dict(type=SECRET,code=SECRET,param=SECRET,message=SECRET))),
    json.dumps(dict(error=[SECRET])),
    '['+SECRET,
    '[]',
])
def test_unknown_non_json_or_oversized_rejection_keeps_status_only(monkeypatch,body):
    calls=mock_http(monkeypatch,lambda req:httpx.Response(502,content=body))
    with pytest.raises(AnswerProviderError) as error:
        asyncio.run(request({},'synthetic-api-key'))
    assert error.value.diagnostic()==dict(http_status=502,error_type=None,error_code=None,error_param=None)
    assert SECRET not in repr(vars(error.value)) and len(calls)==1


class BrokenStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"error":'
        raise httpx.ReadError(SECRET)


def test_partial_read_failure_keeps_known_http_status(monkeypatch):
    calls=mock_http(monkeypatch,lambda req:httpx.Response(503,stream=BrokenStream()))
    with pytest.raises(AnswerProviderError) as error:
        asyncio.run(request({},'synthetic-api-key'))
    assert error.value.http_status==503 and error.value.error_code is None
    assert str(error.value)=='ANSWER_PROVIDER_REJECTED' and len(calls)==1


@pytest.mark.parametrize('write_failure',[False,True])
def test_rejection_private_capture_log_and_unknown_billing_no_retry(answer_client,tmp_path,monkeypatch,caplog,write_failure):
    import app.api.answers as api
    import app.evaluation.answer_run as runner
    client,headers,_,vector,bind,owner,_=answer_client
    calls=mock_http(monkeypatch,lambda req:httpx.Response(400,json=rejected_body()))
    original=runner.write_private
    def write(path,value,**kw):
        if write_failure:raise OSError(SECRET)
        return original(path,value,**kw)
    monkeypatch.setattr(runner,'write_private',write)
    # Exercise the paid caller through a transport with mocked HTTP, not api.answer's fixture wrapper.
    from app.services.answer_call import answer as paid_answer
    def captured(*a,**kw):
        return capturing_answer(api.settings,tmp_path,{kw['request_id']:'case'},caller=paid_answer,
            provider=lambda value:asyncio.run(request(value,'synthetic-api-key')),root=tmp_path)(*a,**kw)
    monkeypatch.setattr(api,'answer',captured)
    data=ask(vector)
    response=client.post('/answers',headers=headers,json=data)
    assert response.status_code==503 and response.json()==dict(detail='ANSWER_PROVIDER_REJECTED')
    rows=[r for r in caplog.records if r.message.startswith('answer_provider_rejected ')]
    assert len(rows)==1 and rows[0].provider['http_status']==400
    assert rows[0].provider['error_code']=='invalid_json_schema' and rows[0].exc_info is None
    assert 'http_status=400' in caplog.text and 'error_code=invalid_json_schema' in caplog.text
    assert SECRET not in caplog.text and data['q'] not in caplog.text
    path=tmp_path/'case-rejection.json'
    if write_failure:assert not path.exists()
    else:
        saved=read_private(path,tmp_path)
        assert saved==dict(run_id=rows[0].run_id,provider=rows[0].provider)
        assert SECRET not in str(saved) and path.stat().st_mode&0o777==0o600
    assert not (tmp_path/'case-provider.json').exists()
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,AiUsageAttempt.purpose=='answer'))
        assert row.status=='uncertain' and row.spent_micro_usd==0 and row.reserved_micro_usd>0
    assert client.post('/answers',headers=headers,json=data).status_code==409
    assert len(calls)==1
