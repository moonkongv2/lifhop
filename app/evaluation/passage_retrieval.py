from sqlalchemy import select
from app.services.passage_search import ranked_passages
from app.services.passage_budget import search_budget


def retrieve_passages(db, *, owner_id, q, filters, groups):
    with search_budget(db):
        return _retrieve_passages(db, owner_id=owner_id, q=q, filters=filters, groups=groups)


def _retrieve_passages(db, *, owner_id, q, filters, groups):
    base, rows, total = ranked_passages(db, owner_id, q, filters.model_dump())
    hits = [dict(passage_id=r["id"], entry_id=r["entry_id"], version_id=r["version_id"],
        field=r["field"], start=r["start"], end=r["end"], passage_hash=r["passage_hash"],
        alias_total=r["alias_total"], gold_locations=[]) for r in rows]
    group_to_hit = {r["group_id"]:hit for r, hit in zip(rows, hits)}
    anchors = {(a["entry_id"], a["version_id"]) for anchors in groups.values() for a in anchors if a["status"] == "valid"}
    for entry_id, version_id in anchors:
        for row in db.execute(select(base.c.id, base.c.entry_id, base.c.version_id, base.c.field,
            base.c.start, base.c.end, base.c.group_id).where(base.c.entry_id == entry_id,
                base.c.version_id == version_id, base.c.group_id.in_(group_to_hit)).limit(512)).mappings():
            value = dict(row)
            group_to_hit[value.pop("group_id")]["gold_locations"].append(value)
    return dict(total=total, hits=hits)
