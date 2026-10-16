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


def test_multi_case_failure_marks_remaining_unsent(tmp_path):
    p,r,c=fixture()
    from copy import deepcopy
    second = deepcopy(r[0]); second["id"] = "second"
    r.append(second)
    frozen = deepcopy(p["cases"][0]); frozen["id"] = "second"
    p["cases"].append(frozen)
    p.update(call_limit=2,max_micro_usd=20000)
    p.pop("digest");p["digest"]=digest(p)
    c.post.return_value=SimpleNamespace(status_code=503,json=lambda:dict(detail="ANSWER_OUTPUT_INVALID"))
    report=run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    assert report["unsent_cases"] == ["second"] and c.post.call_count == 1


@pytest.mark.parametrize("change", ["short_cases", "duplicate_cases", "configuration"])
def test_invalid_run_shape_or_config_never_dispatches(tmp_path,change):
    p,r,c=fixture()
    if change=="short_cases": p["cases"]=[]
    elif change=="duplicate_cases": r.append(r[0])
    else: p["configuration_hash"]="old"
    p.pop("digest");p["digest"]=digest(p)
    with pytest.raises(EvaluationError,match="APPROVAL_INVALID"):
        run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    c.post.assert_not_called()
    assert not (tmp_path/"run-start.json").exists()


def test_crash_after_marker_never_restarts(tmp_path):
    p,r,c=fixture()
    c.post.side_effect=RuntimeError("synthetic lost connection")
    with pytest.raises(RuntimeError):
        run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    with pytest.raises(EvaluationError,match="OUTPUT_EXISTS"):
        run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    assert c.post.call_count == 1


def test_report_joins_safe_reason_by_run_id(tmp_path):
    import hashlib
    from app.evaluation.storage import write_private
    p,r,c=fixture()
    p["owner_id"]=7;p.pop("digest");p["digest"]=digest(p)
    request_id=digest(["answer-validation-v1",p["digest"],"case"])[:32]
    run_id=hashlib.sha256(f"answer-v1:7:{request_id}".encode()).hexdigest()[:32]
    write_private(tmp_path/"case-diagnostic.json",dict(run_id=run_id,reason="refusal"),root=tmp_path)
    c.post.return_value=SimpleNamespace(status_code=503,json=lambda:dict(detail="ANSWER_OUTPUT_INVALID"))
    report=run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    assert report["cases"][0]["reason"]=="refusal" and report["unsent_cases"]==[]


def test_report_joins_sanitized_provider_rejection(tmp_path):
    import hashlib
    from app.evaluation.storage import write_private
    p,r,c=fixture()
    p["owner_id"]=7;p.pop("digest");p["digest"]=digest(p)
    request_id=digest(["answer-validation-v1",p["digest"],"case"])[:32]
    run_id=hashlib.sha256(f"answer-v1:7:{request_id}".encode()).hexdigest()[:32]
    provider=dict(http_status=400,error_type="invalid_request_error",error_code="invalid_json_schema",error_param="text.format.schema")
    write_private(tmp_path/"case-rejection.json",dict(run_id=run_id,provider=provider),root=tmp_path)
    c.post.return_value=SimpleNamespace(status_code=503,json=lambda:dict(detail="ANSWER_PROVIDER_REJECTED"))
    report=run_answers(p,r,approval_digest=p["digest"],client=c,output=tmp_path,root=tmp_path)
    assert report["cases"][0]["provider"]==provider
    assert report["state"]=="stopped_after_failure" and c.post.call_count==1
