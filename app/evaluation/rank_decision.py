"""Select on tuning only, then score one frozen variant on held-out cases."""
from statistics import mean

from app.evaluation.schemas import EvaluationError, digest
from app.evaluation.rank_replay import RULE_DIGEST

POLICY = dict(version="quota-decision-v1", recall20_min=0.80, all20_min=0.70,
    tie_order=["A", "C", "B"], quality_order=["recall20", "all20", "recall10", "recall5"],
    preserve_lexical=True, recover_korean=True, diagnostic_only=["D"])


def summarize(cases):
    positive = [c for c in cases if c["expected_outcome"] == "supported"]
    if not positive or any(c["status"] != "measured" for c in positive):
        raise EvaluationError("DECISION_EVIDENCE_INVALID")
    scores = [c["methods"]["hybrid"]["scores"] for c in positive]
    if any(s["group_recall_at_20"] is None for s in scores):
        raise EvaluationError("DECISION_EVIDENCE_INVALID")
    lost = [c["case_id"] for c in positive
        if c["methods"]["lexical"]["scores"]["all_groups_hit_at_20"] == 1
        and c["methods"]["hybrid"]["scores"]["all_groups_hit_at_20"] != 1]
    recovered = [c["case_id"] for c in positive if c["language"] == "ko"
        and c["methods"]["lexical"]["scores"]["all_groups_hit_at_20"] == 0
        and c["methods"]["hybrid"]["scores"]["all_groups_hit_at_20"] == 1]
    result = dict(positive_cases=len(positive), negative_cases=len(cases)-len(positive),
        all20=mean(s["all_groups_hit_at_20"] for s in scores),
        lost_lexical=lost, recovered_korean=recovered,
        mean_distinct_families=mean(c["methods"]["hybrid"]["distinct_families"] for c in positive),
        max_family_results=max(c["methods"]["hybrid"]["max_family_results"] for c in positive))
    result.update({f"recall{k}":mean(s[f"group_recall_at_{k}"] for s in scores) for k in (5,10,20)})
    result["eligible"] = (result["recall20"] >= POLICY["recall20_min"]
        and result["all20"] >= POLICY["all20_min"] and not lost and bool(recovered))
    return result


def select_tuning(report, *, tuning_digest, validation_digest):
    if (report["rule_digest"] != RULE_DIGEST or report["status"] != "measured"
            or report["dataset_digest"] != tuning_digest):
        raise EvaluationError("DECISION_CONFIGURATION_CHANGED")
    summaries = {name:summarize(value["cases"]) for name,value in report["variants"].items()}
    candidates = [name for name in POLICY["tie_order"] if summaries[name]["eligible"]]
    selected = max(candidates, key=lambda n:tuple(summaries[n][key] for key in POLICY["quality_order"]),default=None)
    result = dict(schema="lifhop-quota-freeze-v1", policy=POLICY, rule_digest=RULE_DIGEST,
        tuning_digest=tuning_digest, validation_digest=validation_digest,
        tuning_capture_digest=report["capture_digest"], summaries=summaries, selected=selected,
        status="frozen" if selected else "no_candidate", b2_gate="independent_validation_required")
    result["digest"] = digest(result)
    return result


def validate_frozen(frozen, report, *, validation_digest):
    if (frozen.get("digest") != digest({k:v for k,v in frozen.items() if k != "digest"})
            or frozen["policy"] != POLICY or frozen["rule_digest"] != RULE_DIGEST
            or report["rule_digest"] != RULE_DIGEST or report["status"] != "measured"
            or report["dataset_digest"] != validation_digest
            or frozen["validation_digest"] != validation_digest):
        raise EvaluationError("FROZEN_CONFIGURATION_CHANGED")
    if frozen["status"] != "frozen" or frozen["selected"] not in POLICY["tie_order"]:
        raise EvaluationError("NO_FROZEN_CANDIDATE")
    cases = report["variants"][frozen["selected"]]["cases"]
    result = dict(schema="lifhop-quota-validation-v1", freeze_digest=frozen["digest"],
        capture_digest=report["capture_digest"], validation_digest=validation_digest,
        selected=frozen["selected"], summary=summarize(cases),
        negative_case_ids=[c["case_id"] for c in cases if c["expected_outcome"] != "supported"])
    result["b2_gate"] = "owner_review_required" if result["summary"]["eligible"] else "criteria_not_met"
    return result
