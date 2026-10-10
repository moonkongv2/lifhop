import json
import os
from array import array
import pytest
from app.evaluation.rank_replay import RankCapture, load_capture, replay, RULES
from app.evaluation.semantic import prepare, compare, group_rank, fuse
from app.evaluation.schemas import EvaluationError
from test_semantic import fixture, data, bounded_test_process


def capture_fixture(db, user, tmp_path):
    entry = fixture(db,user)
    snap,dataset = data(db,user,entry)
    experiment = prepare(snap,dataset,provider="manual",scope="default")
    capture = RankCapture(experiment)
    report = compare(experiment, lambda batch,run:[array("f",[1,0]) for _ in batch],
                     lambda query,run:array("f",[1,0]),rank_sink=capture.collect)
    report["usage"] = []
    path = capture.publish(tmp_path/"capture",report,root=tmp_path)
    return entry,experiment,report,path,snap,dataset


def test_capture_is_private_body_free_and_replays_exactly(db_session,user,tmp_path):
    entry,experiment,report,path,snap,dataset = capture_fixture(db_session,user,tmp_path)
    header,cases = load_capture(path,experiment,root=tmp_path)
    result = replay(experiment,header,cases)
    assert result["provider_calls"] == 0
    assert set(result["variants"]) == set(RULES)
    assert result["b2_gate"] == "independent_validation_required"
    original = report["cases"][0]["methods"]
    restored = result["variants"]["A"]["cases"][0]["methods"]
    for method,output in original.items():
        assert restored[method]["scores"] == output["scores"]
        assert [h["id"] for h in restored[method]["hits"]] == output["passage_ids"]
    for file in path.parent.glob("*.json"):
        raw = file.read_text()
        assert entry.content not in raw and "서버 어디" not in raw and "Private title" not in raw
        assert os.stat(file).st_mode & 0o777 == 0o600
    assert os.stat(path.parent).st_mode & 0o777 == 0o700


def test_stale_or_tampered_capture_is_rejected(db_session,user,tmp_path):
    entry,experiment,report,path,snap,dataset = capture_fixture(db_session,user,tmp_path)
    entry.external_ai_allowed = False
    db_session.flush()
    fresh = prepare(snap,dataset,provider="manual",scope="default")
    with pytest.raises(EvaluationError,match="CAPTURE_STALE"):
        load_capture(path,fresh,root=tmp_path)
    case_path = path.parent/"case-00.json"
    value = json.loads(case_path.read_text())
    value["semantic_ids"] = [999999]
    case_path.write_text(json.dumps(value))
    with pytest.raises(EvaluationError,match="CAPTURE_INVALID"):
        load_capture(path,experiment,root=tmp_path)


def test_capture_limits_fail_before_publishing_index(db_session,user,tmp_path,monkeypatch):
    from app.evaluation import rank_replay as module
    entry,experiment,report,path,snap,dataset = capture_fixture(db_session,user,tmp_path)
    capture = RankCapture(experiment)
    case_id = experiment.cases[0].id
    rows = experiment.rows
    hits = group_rank(rows,[r["id"] for r in rows])
    capture.collect(case_id,[r["id"] for r in rows],[r["id"] for r in rows],dict(lexical=hits,semantic=hits,hybrid=fuse(hits,hits)))
    monkeypatch.setattr(module,"MAX_RUN_BYTES",1)
    with pytest.raises(EvaluationError,match="CAPTURE_SIZE_LIMIT"):
        capture.publish(tmp_path/"oversized",report,root=tmp_path)
    assert not (tmp_path/"oversized/capture.json").exists()


def test_four_conditions_separate_early_and_final_quota(db_session,user,tmp_path):
    entry,experiment,report,path,snap,dataset = capture_fixture(db_session,user,tmp_path)
    original = experiment.rows[0]
    # Three disjoint chunks of one Entry prove which stage removes the third.
    rows = [dict(original,id=i,group_id=f"g{i}",start=(i-1)*10,end=i*10) for i in (1,2,3)]
    experiment.rows = rows
    experiment.lexical = {experiment.cases[0].id:[1,2,3]}
    group = next(iter(experiment.gold[experiment.cases[0].id]))
    anchor = experiment.gold[experiment.cases[0].id][group][0]
    experiment.gold[experiment.cases[0].id] = {group:[dict(anchor,start=20,end=30)]}
    capture = RankCapture(experiment)
    lex = group_rank(rows,[1,2,3])
    capture.collect(experiment.cases[0].id,[1,2,3],[1,2,3],dict(lexical=lex,semantic=lex,hybrid=fuse(lex,lex)))
    report["run_id"] = "synthetic-quota"
    path = capture.publish(tmp_path/"quota",report,root=tmp_path)
    header,cases = load_capture(path,experiment,root=tmp_path)
    result = replay(experiment,header,cases)
    ranks = {name:variant["cases"][0]["methods"]["hybrid"]["scores"]["group_ranks"][group]
             for name,variant in result["variants"].items()}
    assert ranks == {"A":None,"B":None,"C":None,"D":3}
    assert result["variants"]["B"]["cases"][0]["methods"]["semantic"]["scores"]["group_ranks"][group] == 3
    assert result["variants"]["D"]["product_candidate"] is False


def test_negative_case_keeps_hits_without_claiming_support(db_session,user,tmp_path):
    entry,experiment,report,path,snap,dataset = capture_fixture(db_session,user,tmp_path)
    case = experiment.cases[0].model_copy(update={"expected_outcome":"insufficient_evidence",
        "claims":[], "evidence_groups":[]})
    experiment.cases = [case]
    experiment.gold = {case.id:{}}
    capture = RankCapture(experiment)
    report = compare(experiment,lambda batch,run:[array("f",[1,0]) for _ in batch],
        lambda query,run:array("f",[1,0]),rank_sink=capture.collect)
    assert report["cases"][0]["status"] == "negative_review_required"
    assert report["b2_gate"] == "criteria_not_met"
    report["usage"] = []
    path = capture.publish(tmp_path/"negative",report,root=tmp_path)
    header,cases = load_capture(path,experiment,root=tmp_path)
    output = replay(experiment,header,cases)["variants"]["A"]["cases"][0]
    assert output["status"] == "negative_review_required"
    assert output["methods"]["hybrid"]["hits"]
    assert output["methods"]["hybrid"]["scores"]["group_recall_at_20"] is None
