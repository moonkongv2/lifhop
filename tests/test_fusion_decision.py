from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
import pytest
from app.evaluation.schemas import EvaluationError,now
from app.evaluation.fusion_replay import RULE_DIGEST
from app.evaluation.fusion_decision import select_fusion,validate_fusion,summaries
from test_rank_decision import case


def report(dataset="old"):
    return dict(status="measured",rule_digest=RULE_DIGEST,dataset_digest=dataset,capture_digest="capture",
        replayed_at=now().isoformat(),owner_id=1,database_fingerprint="db",policy_revision=1,
        corpus_digest="corpus",family_map_digest="families",source_config_digest="config",
        variants={n:dict(cases=[case("ko","ko",0,1),case("en","en",1,1),
            case("negative","en",None,None,"insufficient_evidence")]) for n in ["B0","R","P","S"]})


def dataset():
    return SimpleNamespace(owner_id=1,database_fingerprint="db",digest="new",
        cases=[SimpleNamespace(status="reviewed",reviewed_at=now()-timedelta(days=1))])


def test_review_required_before_tuning_scores_and_ties_prefer_r():
    frozen=select_fusion([report()],dataset())
    assert frozen["selected"]=="R" and frozen["b2_gate"]=="independent_validation_required"
    pending=dataset();pending.cases[0].status="draft"
    with pytest.raises(EvaluationError,match="VALIDATION_REVIEW_REQUIRED"):
        select_fusion([report()],pending)
    late=dataset();late.cases[0].reviewed_at=now()+timedelta(days=1)
    with pytest.raises(EvaluationError,match="VALIDATION_REVIEW_TOO_LATE"):
        select_fusion([report()],late)
    used=dataset();used.digest="old"
    with pytest.raises(EvaluationError,match="VALIDATION_IS_TUNING"):
        select_fusion([report()],used)


def test_early_rank_regressions_and_bindings_block_selection():
    value=report()
    for v in value["variants"].values():
        v["cases"].append(case("en2","en",1,1))
    for c in value["variants"]["P"]["cases"][:2]:
        c["methods"]["hybrid"]["scores"]["group_recall_at_5"]=0
    assert summaries([value])["P"]["eligible"] is False
    other=deepcopy(value);other["owner_id"]=2
    with pytest.raises(EvaluationError,match="FUSION_BINDING_CHANGED"):
        summaries([value,other])
    with pytest.raises(EvaluationError,match="FUSION_DUPLICATE_CASE"):
        summaries([value,value])


def test_failed_heldout_cannot_reselect_or_change_frozen_dataset():
    frozen=select_fusion([report()],dataset())
    heldout=report("new")
    heldout["variants"]["R"]["cases"][1]=case("en","en",1,0)
    measured=validate_fusion(frozen,heldout)
    assert measured["selected"]=="R" and measured["b2_gate"]=="criteria_not_met"
    heldout["dataset_digest"]="other"
    with pytest.raises(EvaluationError,match="FUSION_FREEZE_CHANGED"):
        validate_fusion(frozen,heldout)
