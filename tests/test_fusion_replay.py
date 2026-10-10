import pytest
from app.evaluation.fusion_replay import rank_candidates,replay_fusion,write_fusion_report,load_fusion_report
from app.evaluation.rank_replay import load_capture
from app.evaluation.schemas import EvaluationError,canonical_bytes
from test_rank_replay import capture_fixture
from test_semantic import bounded_test_process


def hit(i,entry=None,group=None):
    return dict(id=str(i),group_id=group or str(i),entry_id=entry or i,
        gold_locations=[dict(entry_id=entry or i,version_id=1,field="content",start=0,end=10)])


def test_protects_lane_leader_that_equal_rrf_pushes_out():
    lex=[hit(i) for i in range(1,101)]
    sem=[hit(999),*lex[:99]]
    ordinary,_=rank_candidates(lex,sem,"R")
    protected,trace=rank_candidates(lex,sem,"P")
    assert "999" not in [h["id"] for h in ordinary]
    assert "999" in [h["id"] for h in protected[:10]]
    leaders={h["group_id"] for h in lex[:5]+sem[:5]}
    assert leaders<={h["group_id"] for h in protected}
    row=next(r for r in trace if r["group_id"]=="999")
    assert row["protected"] and row["semantic_rank"]==1 and row["lexical_contribution"]==0
    assert len(protected)==20 and len({h["group_id"] for h in protected})==20


def test_removes_final_quota_keeps_alias_union_and_empty_lane():
    items=[hit(i,entry=1) for i in range(1,4)]
    assert len(rank_candidates(items,items,"B0")[0])==2
    assert len(rank_candidates(items,items,"P")[0])==3
    a,b=hit(1,group="shared"),hit(2,group="shared")
    result,_=rank_candidates([a],[b],"P")
    assert result[0]["id"]=="2" and len(result[0]["gold_locations"])==2
    assert len(rank_candidates([],items,"P")[0])==3
    assert rank_candidates(items,[],"S")[0]==[]
    assert rank_candidates([],[],"P")==([],[])
    with pytest.raises(EvaluationError,match="FUSION_DUPLICATE_GROUP"):
        rank_candidates([a,a],[],"P")


def test_ties_are_deterministic_and_results_ignore_unrelated_metadata():
    a,b=hit(1),hit(2)
    first=rank_candidates([a,b],[b,a],"P")[0]
    other=rank_candidates([dict(a,text="unrelated",language="ko"),b],[b,a],"P")[0]
    assert [h["id"] for h in first]==[h["id"] for h in other]==["1","2"]


def test_legacy_binding_and_bounded_body_free_publication(db_session,user,tmp_path,monkeypatch):
    entry,ex,report,path,snap,dataset=capture_fixture(db_session,user,tmp_path)
    header,cases=load_capture(path,ex,root=tmp_path)
    result=replay_fusion(ex,header,cases)
    assert result["provider_calls"]==0 and set(result["variants"])=={"B0","R","P","S"}
    assert entry.content.encode() not in canonical_bytes(result)
    index=write_fusion_report(tmp_path/"fusion",result,root=tmp_path)
    assert index.exists()
    assert load_fusion_report(index,root=tmp_path)==result
    assert all(p.stat().st_mode&0o777==0o600 for p in index.parent.glob("*.json"))
    from app.evaluation import fusion_replay as module
    monkeypatch.setattr(module,"MAX_DATASET_BYTES",1)
    with pytest.raises(EvaluationError,match="FUSION_REPORT_SIZE_LIMIT"):
        write_fusion_report(tmp_path/"too-large",result,root=tmp_path)
    assert not (tmp_path/"too-large/report.json").exists()
    case_path=index.parent/"P-00.json"
    case_path.write_text('{}')
    with pytest.raises(EvaluationError,match="FUSION_REPORT_INVALID"):
        load_fusion_report(index,root=tmp_path)
