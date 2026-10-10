from copy import deepcopy
import pytest
from app.evaluation.rank_decision import select_tuning, validate_frozen
from app.evaluation.rank_replay import RULE_DIGEST
from app.evaluation.schemas import EvaluationError


def case(cid, lang, lexical, hybrid, outcome="supported"):
    scores = lambda hit:dict(group_recall_at_5=hit, group_recall_at_10=hit,
        group_recall_at_20=hit, all_groups_hit_at_20=hit)
    return dict(case_id=cid,language=lang,expected_outcome=outcome,
        status="measured" if outcome=="supported" else "negative_review_required",
        methods=dict(lexical=dict(scores=scores(lexical)),hybrid=dict(scores=scores(hybrid),
            distinct_families=4,max_family_results=3)))


def report(dataset_digest="t"):
    return dict(status="measured",rule_digest=RULE_DIGEST,capture_digest="capture",
        dataset_digest=dataset_digest,
        variants={n:dict(cases=[case("ko","ko",0,1),case("en","en",1,1),
            case("negative","en",None,None,"insufficient_evidence")]) for n in "ABCD"})


def test_ties_prefer_baseline_and_negatives_do_not_enter_recall():
    frozen=select_tuning(report(),tuning_digest="t",validation_digest="v")
    assert frozen["selected"]=="A"
    result=validate_frozen(frozen,report("v"),validation_digest="v")
    assert result["summary"]["recall20"]==1
    assert result["summary"]["positive_cases"]==2
    assert result["negative_case_ids"]==["negative"]
    assert result["b2_gate"]=="owner_review_required"


def test_d_only_success_cannot_select_product_candidate():
    value=report()
    for n in "ABC":
        value["variants"][n]["cases"][0]=case("ko","ko",0,0)
    frozen=select_tuning(value,tuning_digest="t",validation_digest="v")
    assert frozen["selected"] is None and frozen["status"]=="no_candidate"
    with pytest.raises(EvaluationError,match="NO_FROZEN_CANDIDATE"):
        validate_frozen(frozen,report("v"),validation_digest="v")


def test_validation_failure_cannot_change_selected_variant():
    value=report()
    value["variants"]["A"]["cases"][0]=case("ko","ko",0,0)
    frozen=select_tuning(value,tuning_digest="t",validation_digest="v")
    assert frozen["selected"]=="C"
    heldout=report("v")
    heldout["variants"]["C"]["cases"][1]=case("en","en",1,0)
    result=validate_frozen(frozen,heldout,validation_digest="v")
    assert result["selected"]=="C" and result["b2_gate"]=="criteria_not_met"
    with pytest.raises(EvaluationError,match="FROZEN_CONFIGURATION_CHANGED"):
        validate_frozen(frozen,heldout,validation_digest="other")
    changed=deepcopy(frozen); changed["selected"]="B"
    with pytest.raises(EvaluationError,match="FROZEN_CONFIGURATION_CHANGED"):
        validate_frozen(changed,heldout,validation_digest="v")
    with pytest.raises(EvaluationError,match="FROZEN_CONFIGURATION_CHANGED"):
        validate_frozen(frozen,report("t"),validation_digest="v")
