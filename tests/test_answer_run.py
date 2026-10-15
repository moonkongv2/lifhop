from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.evaluation.answer_run import run_answers
from app.evaluation.schemas import digest, EvaluationError
from app.services.answer_transport import CONFIG_HASH


def fixture():
    review=[dict(id="case",question="Synthetic question",excerpts=[dict(id=1,text="Synthetic text")])]
    protocol=dict(configuration_hash=CONFIG_HASH,call_limit=1,max_micro_usd=10000,
        automatic_retry=False,validation_runs=1,cases=[dict(id="case",question_digest=digest("Synthetic question"),
        selected=[dict(embedding_id=1,text_digest=digest("Synthetic text"))])])
    protocol["digest"]=digest(protocol)
    client=Mock()
    client.post.return_value=SimpleNamespace(status_code=200,json=lambda:dict(status="supported",answer="Synthetic answer"))
    return protocol,review,client


def test_run_marker_prevents_second_paid_run(tmp_path):
    p,r,c=fixture()
    assert run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)["state"]=="completed"
    with pytest.raises(EvaluationError,match="OUTPUT_EXISTS"):
        run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    assert c.post.call_count==1


def test_changed_excerpt_and_wrong_approval_never_post(tmp_path):
    p,r,c=fixture()
    with pytest.raises(EvaluationError,match="APPROVAL_INVALID"):
        run_answers(p,r,approval_digest="wrong",client=c,output=tmp_path,root=tmp_path)
    r[0]["excerpts"][0]["text"]="changed"
    with pytest.raises(EvaluationError,match="INPUT_CHANGED"):
        run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    c.post.assert_not_called()


def test_provider_failure_stops_without_retry(tmp_path):
    p,r,c=fixture()
    c.post.return_value=SimpleNamespace(status_code=503,json=lambda:dict(detail="ANSWER_OUTPUT_INVALID"))
    assert run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)["state"]=="stopped_after_failure"
    assert c.post.call_count==1
