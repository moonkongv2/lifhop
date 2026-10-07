from statistics import mean


def query_metrics(hits: list[dict], groups: dict[str, list[dict]]) -> dict:
    # Each group is one requirement; alternate records never increase its weight.
    usable = {name:[anchor for anchor in anchors if anchor["status"] == "valid" and
              anchor["selection"] == "current"] for name, anchors in groups.items()}
    rank = {(hit["entry_id"], hit["version_id"]):i for i, hit in reversed(list(enumerate(hits, 1)))}
    group_ranks = {name:min((rank[(a["entry_id"], a["version_id"])] for a in anchors
        if (a["entry_id"], a["version_id"]) in rank), default=None) for name, anchors in usable.items()}
    count = len(groups)
    result = {f"group_recall_at_{k}":sum(r is not None and r <= k for r in group_ranks.values()) / count if count else None
              for k in (5, 10, 20)}
    found = [r for r in group_ranks.values() if r is not None and r <= 20]
    result.update(all_groups_hit_at_20=float(bool(count) and len(found) == count) if count else None,
        mrr_at_20=1 / min(found) if found else (0.0 if count else None),
        current_version_hit=float(bool(found)) if count else None,
        historical_entry_hit=float(any(a["status"] == "valid" and a["selection"] == "historical" and
            any(hit["entry_id"] == a["entry_id"] for hit in hits) for anchors in groups.values() for a in anchors)),
        group_ranks=group_ranks)
    return result


SCORE_KEYS = ("group_recall_at_5", "group_recall_at_10", "group_recall_at_20",
              "all_groups_hit_at_20", "mrr_at_20", "current_version_hit", "historical_entry_hit")


def average_scores(scores: list[dict]) -> dict:
    return {key:mean(values) if (values := [score[key] for score in scores if score.get(key) is not None]) else None
            for key in SCORE_KEYS}


def summarize(cases: list[dict]) -> dict:
    scored = [case for case in cases if case["scored"]]
    clean = [case for case in scored if not case["validation_errors"] and case["status"] == "evaluated"]
    common = [case for case in scored if case["has_keywords"]]
    historical = [c for c in cases if c["has_historical"] and c["queries"]]
    return dict(total_cases=len(cases), scored_cases=len(scored), clean_cases=len(clean),
        invalid_scored_cases=len(scored)-len(clean),
        failed_scored_cases=sum(c["status"] in {"run_budget", "database_timeout_or_error"} for c in scored),
        state_counts={state:sum(case["status"] == state for case in cases) for state in sorted({c["status"] for c in cases})},
        scores=average_scores([case["scores"] for case in scored]),
        clean_scores=average_scores([case["scores"] for case in clean]),
        common_keyword_cases=len(common), common_keyword_scores=average_scores([case["scores"] for case in common]),
        historical_cases=len(historical), historical_scores=average_scores([c["scores"] for c in historical]),
        by_language={language:dict(count=len(rows), scores=average_scores([r["scores"] for r in rows]))
            for language in sorted({c["language"] for c in scored})
            if (rows := [c for c in scored if c["language"] == language])},
        by_tag={tag:dict(count=len(rows), scores=average_scores([r["scores"] for r in rows]))
            for tag in sorted({tag for c in scored for tag in c["tags"]})
            if (rows := [c for c in scored if tag in c["tags"]])})
