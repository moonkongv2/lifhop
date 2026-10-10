"""Freeze one new fusion rule on existing captures; validate without reselection."""
from datetime import datetime
from app.evaluation.schemas import EvaluationError, digest
from app.evaluation.rank_decision import summarize, POLICY as SCORE_POLICY
from app.evaluation.fusion_replay import RULE_DIGEST

POLICY=dict(version="fusion-decision-v1",tie_order=["R","P","S"],max_early_losses=1,
    recall20_min=SCORE_POLICY["recall20_min"],all20_min=SCORE_POLICY["all20_min"],
    preserve_lexical=True,recover_korean=True,
    quality_order=["recall20","all20","recall10","recall5"])
BINDING=("owner_id","database_fingerprint","policy_revision","corpus_digest","family_map_digest","source_config_digest")


def summaries(reports):
    if not reports or any(r["rule_digest"]!=RULE_DIGEST or r["status"]!="measured" for r in reports):
        raise EvaluationError("FUSION_DECISION_INVALID")
    if any(tuple(r[k] for k in BINDING)!=tuple(reports[0][k] for k in BINDING) for r in reports):
        raise EvaluationError("FUSION_BINDING_CHANGED")
    baselines=[c for r in reports for c in r["variants"]["B0"]["cases"]]
    ids=[c["case_id"] for c in baselines]
    if len(set(ids))!=len(ids):
        raise EvaluationError("FUSION_DUPLICATE_CASE")
    result={}
    baseline={c["case_id"]:c for c in baselines}
    for variant in ("B0","R","P","S"):
        cases=[c for r in reports for c in r["variants"][variant]["cases"]]
        if [c["case_id"] for c in cases]!=ids:
            raise EvaluationError("FUSION_CASES_CHANGED")
        value=summarize(cases)
        for k in (5,10):
            lost=[c["case_id"] for c in cases if c["expected_outcome"]=="supported"
                and baseline[c["case_id"]]["methods"]["hybrid"]["scores"][f"group_recall_at_{k}"]==1
                and c["methods"]["hybrid"]["scores"][f"group_recall_at_{k}"]!=1]
            value[f"lost_at_{k}"]=lost
            value["eligible"] &= len(lost)<=POLICY["max_early_losses"]
        result[variant]=value
    return result


def select_fusion(reports, validation_dataset):
    if not reports:
        raise EvaluationError("FUSION_DECISION_INVALID")
    if (any(c.status!="reviewed" for c in validation_dataset.cases)
            or validation_dataset.owner_id!=reports[0]["owner_id"]
            or validation_dataset.database_fingerprint!=reports[0]["database_fingerprint"]):
        raise EvaluationError("VALIDATION_REVIEW_REQUIRED")
    first_replay=min(datetime.fromisoformat(r["replayed_at"]) for r in reports)
    if any(c.reviewed_at>first_replay for c in validation_dataset.cases):
        raise EvaluationError("VALIDATION_REVIEW_TOO_LATE")
    if validation_dataset.digest in {r["dataset_digest"] for r in reports}:
        raise EvaluationError("VALIDATION_IS_TUNING")
    values=summaries(reports)
    candidates=[n for n in POLICY["tie_order"] if values[n]["eligible"]]
    selected=max(candidates,key=lambda n:tuple(values[n][k] for k in POLICY["quality_order"]),default=None)
    result=dict(schema="lifhop-fusion-freeze-v1",policy=POLICY,rule_digest=RULE_DIGEST,
        binding={k:reports[0][k] for k in BINDING},
        inputs=[dict(dataset_digest=r["dataset_digest"],capture_digest=r["capture_digest"],report_digest=digest(r)) for r in reports],
        validation_digest=validation_dataset.digest,summaries=values,selected=selected,
        selected_mode="semantic" if selected=="S" else "hybrid" if selected else None,
        status="frozen" if selected else "no_candidate",b2_gate="independent_validation_required")
    result["digest"]=digest(result)
    return result


def validate_fusion(frozen, report):
    if (frozen.get("digest")!=digest({k:v for k,v in frozen.items() if k!="digest"})
            or frozen["rule_digest"]!=RULE_DIGEST or frozen["policy"]!=POLICY
            or frozen["validation_digest"]!=report["dataset_digest"]
            or frozen["binding"]!={k:report[k] for k in BINDING}):
        raise EvaluationError("FUSION_FREEZE_CHANGED")
    if frozen["selected"] not in POLICY["tie_order"] or frozen["status"]!="frozen":
        raise EvaluationError("NO_FROZEN_CANDIDATE")
    value=summaries([report])[frozen["selected"]]
    return dict(schema="lifhop-fusion-validation-v1",freeze_digest=frozen["digest"],
        capture_digest=report["capture_digest"],selected=frozen["selected"],summary=value,
        b2_gate="owner_review_required" if value["eligible"] else "criteria_not_met")
