"""A record hit succeeds only when returned ranges cover its checked gold span."""
from app.evaluation.metrics import query_metrics


def coverage_rank(locations: list[dict], anchor: dict) -> int | None:
    matching = [p for p in locations if p["entry_id"] == anchor["entry_id"] and
        p["version_id"] == anchor["version_id"] and p["field"] == anchor["field"]]
    for k in sorted({p["rank"] for p in matching}):
        cursor = anchor["start"]
        for p in sorted((p for p in matching if p["rank"] <= k), key=lambda p: (p["start"], p["end"])):
            if p["start"] > cursor:
                break
            cursor = max(cursor, p["end"])
            if cursor >= anchor["end"]:
                return k
    return None


def passage_metrics(hits: list[dict], groups: dict[str, list[dict]]) -> dict:
    locations = [dict(location, rank=rank) for rank, hit in enumerate(hits, 1) for location in hit.get("gold_locations", [])]
    group_ranks = {name:min((r for a in anchors if a["status"] == "valid" and a["selection"] == "current"
        and (r := coverage_rank(locations, a)) is not None), default=None) for name, anchors in groups.items()}
    result = query_metrics([], groups)
    count = len(groups)
    result.update({f"group_recall_at_{k}":sum(r is not None and r <= k for r in group_ranks.values()) / count if count else None for k in (5, 10, 20)})
    found = [r for r in group_ranks.values() if r is not None and r <= 20]
    result.update(group_ranks=group_ranks,
        all_groups_hit_at_20=float(bool(count) and len(found) == count) if count else None,
        mrr_at_20=1/min(found) if found else (0.0 if count else None),
        current_version_hit=float(bool(found)) if count else None,
        historical_entry_hit=float(any(a["status"] == "valid" and a["selection"] == "historical" and
            any(h["entry_id"] == a["entry_id"] for h in hits) for anchors in groups.values() for a in anchors)))
    return result
