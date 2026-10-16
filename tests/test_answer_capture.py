"""Synthetic pilot capture through real answer accounting; never a provider call."""
import json
from unittest.mock import Mock
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ai_usage import AiUsageAttempt
from app.services.answer_call import answer as paid_answer
from app.evaluation.storage import read_private
from app.evaluation.answer_run import capturing_answer
from test_answers import answer_client, ask, response
from test_embedding_jobs import actor


@pytest.mark.parametrize("write_failure", [False, True])
def test_private_reason_and_safe_log_preserve_spent_failure(answer_client,tmp_path,monkeypatch,caplog,write_failure):
    import app.api.answers as api
    import app.evaluation.answer_run as runner
    client,headers,_,vector,bind,owner,_=answer_client
    provider=Mock(side_effect=lambda value:response(value,ids=[999999]))
    original=runner.write_private
    def write(path,value,**kw):
        if write_failure and path.name.endswith('-diagnostic.json'):
            raise OSError('synthetic disk failure')
        return original(path,value,**kw)
    monkeypatch.setattr(runner,'write_private',write)
    def captured(*a,**kw):
        return capturing_answer(api.settings,tmp_path,{kw['request_id']:'case'},
            caller=paid_answer,provider=provider,root=tmp_path)(*a,**kw)
    monkeypatch.setattr(api,'answer',captured)
    data=ask(vector)
    result=client.post('/answers',headers=headers,json=data)
    assert result.status_code==503 and result.json()==dict(detail='ANSWER_OUTPUT_INVALID')
    rows=[r for r in caplog.records if r.message=='answer_output_rejected']
    assert len(rows)==1 and rows[0].reason=='unknown_citation'
    assert rows[0].getMessage()=='answer_output_rejected' and rows[0].exc_info is None
    assert 'Synthetic answer' not in caplog.text and data['q'] not in caplog.text
    path=tmp_path/'case-diagnostic.json'
    if write_failure:
        assert not path.exists()
    else:
        assert read_private(path,tmp_path)==dict(run_id=rows[0].run_id,reason='unknown_citation')
        assert path.stat().st_mode & 0o777==0o600
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,AiUsageAttempt.purpose=='answer'))
        assert row.status=='spent' and row.spent_micro_usd>0
    assert client.post('/answers',headers=headers,json=data).status_code==409
    assert provider.call_count==1


def test_raw_capture_failure_preserves_uncertain_attempt_and_no_replay(answer_client,tmp_path,monkeypatch):
    import app.api.answers as api
    import app.evaluation.answer_run as runner
    client,headers,_,vector,bind,owner,_=answer_client
    provider=Mock(side_effect=response)
    monkeypatch.setattr(runner,'write_private',Mock(side_effect=OSError('synthetic capture failure')))
    def captured(*a,**kw):
        return capturing_answer(api.settings,tmp_path,{kw['request_id']:'case'},
            caller=paid_answer,provider=provider,root=tmp_path)(*a,**kw)
    monkeypatch.setattr(api,'answer',captured)
    data=ask(vector)
    with pytest.raises(OSError,match='synthetic capture failure'):
        client.post('/answers',headers=headers,json=data)
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,AiUsageAttempt.purpose=='answer'))
        assert row.status=='uncertain' and row.reserved_micro_usd>0
    assert client.post('/answers',headers=headers,json=data).status_code==409
    assert provider.call_count==1
