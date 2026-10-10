"""Bounded B1 experiment. Vectors and source text never enter persisted reports."""
from collections import Counter
from dataclasses import dataclass
import math
import resource
import sys
import time
from uuid import uuid4
from sqlalchemy import case, func, select, String, cast, literal
from app.evaluation.evidence import validate_case
from app.evaluation.passage_metrics import passage_metrics, coverage_rank
from app.evaluation.retrieval import check_binding, corpus_manifest
from app.evaluation.schemas import digest, canonical_bytes
from app.evaluation.storage import MAX_DATASET_BYTES
from app.models.entry import Entry, EntrySource, EntryType
from app.models.history import EntryVersion, SourcePolicy
from app.models.passage import EntryPassage as P, PassageIndexState
from app.models.user import User
from app.services.embedding_transport import CONFIG, MODEL, DIMENSIONS, EmbeddingError, cost_micro
from app.services.passage_search import eligible_conditions, candidate_query, score_order
from app.evaluation.semantic_chunks import CHUNKING, split_rows, lexical_order

MAX_PASSAGES = 5000


@dataclass
class Experiment:
    manifest: dict
    rows: list[dict]
    cases: list
    gold: dict
    lexical: dict


def bounded_memory():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if rss * (1 if sys.platform == "darwin" else 1024) > 256 * 1024 * 1024:
        raise EmbeddingError("EXPERIMENT_MEMORY_LIMIT")


def group_rank(rows, ordered_ids, limit=100, *, per_entry_limit=2):
    by_id = {r["id"]: r for r in rows}
    groups, order = {}, []
    for pid in ordered_ids:
        row = by_id[pid]
        gid = row["group_id"]
        if gid not in groups:
            groups[gid] = []
            order.append(gid)
        groups[gid].append(row)
    counts, result = Counter(), []
    for gid in order:
        aliases = sorted(groups[gid], key=lambda r: (r["event_at"] or "", r["entry_id"]), reverse=True)
        rep = aliases[0]
        if per_entry_limit is not None and counts[rep["entry_id"]] >= per_entry_limit:
            continue
        counts[rep["entry_id"]] += 1
        result.append(dict(rep, gold_locations=[{k:r[k] for k in
            ("entry_id", "version_id", "field", "start", "end")} for r in aliases]))
        if len(result) == limit:
            break
    return result


def ranking_diagnostics(rows, ordered_ids, groups, *, per_entry_limit=2):
    """Score frozen evidence after ranking; never use it to choose candidates."""
    by_id = {r["id"]: r for r in rows}
    raw = [dict(by_id[pid], gold_locations=[{k:by_id[pid][k] for k in
        ("entry_id", "version_id", "field", "start", "end")}]) for pid in ordered_ids]
    grouped = group_rank(rows, ordered_ids, limit=MAX_PASSAGES, per_entry_limit=None)
    quota = group_rank(rows, ordered_ids, limit=MAX_PASSAGES, per_entry_limit=per_entry_limit)
    stages = dict(raw=raw, grouped=grouped, entry_quota=quota,
                  candidates=quota[:100], top20=quota[:20])
    result = {}
    for name, hits in stages.items():
        locations = [dict(location, rank=rank) for rank, hit in enumerate(hits, 1)
            for location in hit["gold_locations"]]
        result[name] = dict(result_count=len(hits), group_ranks={
            gid:min((rank for anchor in anchors
                if anchor["status"] == "valid" and anchor["selection"] == "current"
                and (rank := coverage_rank(locations, anchor)) is not None), default=None)
            for gid, anchors in groups.items()})
    return result


def fuse(lexical, semantic, *, per_entry_limit=2, limit=20):
    scores, representatives = {}, {}
    for lane in (lexical, semantic):
        for rank, hit in enumerate(lane, 1):
            gid = hit["group_id"]
            scores[gid] = scores.get(gid, 0) + 1 / (60 + rank)
            representatives[gid] = hit
    counts, result = Counter(), []
    for gid in sorted(scores, key=lambda g: (-scores[g], g)):
        hit = representatives[gid]
        if per_entry_limit is None or counts[hit["entry_id"]] < per_entry_limit:
            counts[hit["entry_id"]] += 1
            result.append(hit)
    return result[:limit]


def prepare(snapshot, dataset, *, provider, scope, entry_ids=None, chunking="indexed"):
    if chunking not in {"indexed", CHUNKING}:
        raise EmbeddingError("CHUNKING_UNSUPPORTED")
    check_binding(snapshot, dataset)
    filters = dict(source=EntrySource(provider), source_state=None, entry_type=None, date_field="created_at",
        date_from=None, date_to=None, include_work_commentary=False)
    allow = (SourcePolicy.external_ai_allowed.is_(True) & Entry.external_ai_allowed.is_(True))
    fields = [P.id, P.version_id, Entry.id.label("entry_id"), P.field, P.start, P.end,
        P.passage_hash, func.coalesce(P.group_key, literal("p:") + cast(P.id, String)).label("group_id"),
        Entry.provider, Entry.source_scope, Entry.type, Entry.event_at, Entry.created_at, Entry.source_state,
        allow.label("allowed"), func.octet_length(P.text).label("bytes"),
        case((allow, P.text), else_=None).label("text")]
    if chunking != "indexed":
        fields.append(case((P.group_key.is_not(None), EntryVersion.payload["path"].astext), else_=None).label("document_path"))
    query = select(*fields).select_from(P).join(EntryVersion, EntryVersion.id == P.version_id).join(
        Entry, Entry.id == EntryVersion.entry_id).join(PassageIndexState, PassageIndexState.entry_id == Entry.id).outerjoin(
        SourcePolicy, (SourcePolicy.user_id == Entry.user_id) & (SourcePolicy.provider == Entry.provider) &
        (SourcePolicy.scope == Entry.source_scope)).where(*eligible_conditions(snapshot.owner_id, filters),
        Entry.source_scope == scope, P.field == "content",
        Entry.type.in_([EntryType.NOTE, EntryType.DOCUMENT, EntryType.CONVERSATION])).order_by(P.id).limit(MAX_PASSAGES + 1)
    if entry_ids is not None:
        query = query.where(Entry.id.in_(entry_ids))
    rows = [dict(r) for r in snapshot.db.execute(query).mappings()]
    if len(rows) > MAX_PASSAGES:
        raise EmbeddingError("EXPERIMENT_CORPUS_LIMIT")
    for row in rows:
        for key in ("created_at", "event_at"):
            row[key] = row[key].isoformat() if row[key] else None
        row["type"] = row["type"].value
    metadata = [{k:v for k,v in r.items() if k != "text"} for r in rows]
    allowed = [r for r in rows if r["allowed"] and 0 < r["bytes"] <= 8000 and r["text"].strip()]
    if chunking != "indexed":
        allowed = split_rows(allowed, MAX_PASSAGES)
    allowed_ids = {r["id"] for r in allowed}
    cases = [c for c in dataset.cases if c.status == "reviewed"]
    if not cases:
        raise EmbeddingError("NO_REVIEWED_CASES")
    gold, lexical = {}, {}
    for c in cases:
        checked = validate_case(snapshot.db, snapshot.owner_id, c)
        required = {g.id for g in c.required_groups()}
        gold[c.id] = {name:anchors for name, anchors in checked["groups"].items() if name in required}
        if chunking == "indexed":
            base = candidate_query(snapshot.owner_id, c.question, c.filters.model_dump()).where(P.id.in_(allowed_ids)).cte()
            ids = list(snapshot.db.scalars(select(base.c.id).order_by(*score_order(base.c))))
        else:
            ids = lexical_order(snapshot.db, filtered_rows(allowed, c.filters), c.question)
        lexical[c.id] = ids
    document_bound = sum(r["bytes"] for r in allowed)
    # Conservative rounding assumes every document/query occupies its own request.
    upper_cost = sum(cost_micro(r["bytes"]) for r in allowed) + sum(cost_micro(len(c.question.encode())) for c in cases)
    manifest = dict(schema="lifhop-semantic-b1-v1", dataset_digest=dataset.digest, material_kind=dataset.material_kind, owner_id=snapshot.owner_id,
        database_fingerprint=snapshot.database_fingerprint, provider=provider, scope=scope,
        entry_ids=sorted(entry_ids) if entry_ids is not None else None,
        policy_revision=snapshot.db.scalar(select(User.policy_revision).where(User.id == snapshot.owner_id)),
        corpus=corpus_manifest(snapshot.db, snapshot.owner_id), model=MODEL, dimensions=DIMENSIONS,
        configuration_hash=digest(CONFIG), rows=metadata, allowed_passages=len(allowed),
        blocked_passages=sum(not r["allowed"] for r in rows), oversized_passages=sum(r["bytes"] > 8000 for r in rows),
        candidate_entries=len({r["entry_id"] for r in rows}),
        proposed_max_micro_usd=sum(cost_micro(r["bytes"]) for r in rows if 0 < r["bytes"] <= 8000) +
            sum(cost_micro(len(c.question.encode())) for c in cases),
        input_upper_bound=document_bound, query_count=len(cases), query_digests=[digest(c.question) for c in cases],
        estimated_max_micro_usd=upper_cost, external_query_transmission=True)
    if chunking != "indexed":
        manifest.update(chunking=chunking, configuration_hash=digest([CONFIG, chunking]),
            chunks=[{k:v for k,v in r.items() if k != "text"} for r in allowed],
            proposed_max_micro_usd=upper_cost)
    manifest["digest"] = digest(manifest)
    if len(canonical_bytes(manifest)) > MAX_DATASET_BYTES:
        raise EmbeddingError("EXPERIMENT_MANIFEST_LIMIT")
    bounded_memory()
    return Experiment(manifest, allowed, cases, gold, lexical)


def filtered_rows(rows, filters):
    from app.services.entry_search import date_boundary
    result = []
    for r in rows:
        if filters.source and r["provider"] != filters.source or filters.entry_type and r["type"] != filters.entry_type:
            continue
        # All experimental rows exclude source-deleted content.
        if filters.source_state and r["source_state"] != filters.source_state:
            continue
        stamp = r["event_at"] if filters.date_field == "event_at" else r["created_at"]
        if filters.date_from or filters.date_to:
            from datetime import datetime, timedelta
            if not stamp:
                continue
            value = datetime.fromisoformat(stamp)
            if filters.date_from and value < date_boundary(filters.date_from):
                continue
            if filters.date_to and value >= date_boundary(filters.date_to + timedelta(days=1)):
                continue
        result.append(r)
    return result


def compare(experiment, embed_documents, embed_query, *, rank_sink=None):
    run_id, started = uuid4().hex, time.monotonic()
    vectors = {}
    batch, size = [], 0
    def flush():
        if batch:
            if time.monotonic() - started > 300:
                raise EmbeddingError("EXPERIMENT_TIME_LIMIT")
            result = embed_documents(batch, run_id)
            for row, vector in zip(batch, result, strict=True):
                vectors[row["id"]] = vector
            bounded_memory()
    for row in experiment.rows:
        if len(batch) == 16 or size + row["bytes"] > 16000:
            flush()
            batch, size = [], 0
        batch.append(row)
        size += row["bytes"]
    flush()
    results = []
    if vectors:
        for c in experiment.cases:
            if time.monotonic() - started > 300:
                raise EmbeddingError("EXPERIMENT_TIME_LIMIT")
            before = time.monotonic()
            q = embed_query(c.question, run_id)
            rows = filtered_rows(experiment.rows, c.filters)
            norm = math.sqrt(sum(v*v for v in q))
            distances = {r["id"]: sum(a*b for a,b in zip(q, vectors[r["id"]])) /
                (norm * math.sqrt(sum(v*v for v in vectors[r["id"]]))) for r in rows}
            ids = sorted(distances, key=lambda pid: (-distances[pid], pid))
            semantic = group_rank(rows, ids)
            row_ids = {r["id"] for r in rows}
            lexical = group_rank(rows, [pid for pid in experiment.lexical[c.id] if pid in row_ids])
            groups = experiment.gold[c.id]
            methods = {"lexical":lexical[:20], "semantic":semantic[:20], "hybrid":fuse(lexical, semantic)}
            if rank_sink is not None:
                rank_sink(c.id, [pid for pid in experiment.lexical[c.id] if pid in row_ids], ids, methods)
            valid = all(a["status"] == "valid" for anchors in groups.values() for a in anchors)
            eligible = bool(groups) and all(any(a["external_ai_eligible"] and a["selection"] == "current"
                for a in anchors) for anchors in groups.values())
            negative = c.expected_outcome in {"insufficient_evidence", "coverage_gap"} and not groups
            results.append(dict(case_id=c.id, language=c.language,
                expected_outcome=c.expected_outcome,
                status="negative_review_required" if negative else "measured" if valid and eligible else "evidence_invalid" if not valid else "policy_excluded",
                elapsed_ms=round((time.monotonic()-before)*1000, 2),
                diagnostics={"lexical":ranking_diagnostics(rows,
                    [pid for pid in experiment.lexical[c.id] if pid in row_ids], groups),
                    "semantic":ranking_diagnostics(rows, ids, groups)},
                methods={name:dict(scores=passage_metrics(hits, groups), passage_ids=[h["id"] for h in hits])
                    for name,hits in methods.items()}))
    else:
        results = [dict(case_id=c.id, language=c.language, status="no_allowed_corpus", methods={}) for c in experiment.cases]
    gold_groups = {r["group_id"] for r in experiment.rows if any(a["entry_id"] == r["entry_id"] and
        a["version_id"] == r["version_id"] and a["field"] == r["field"] and
        a["start"] < r["end"] and a["end"] > r["start"] for groups in experiment.gold.values()
        for anchors in groups.values() for a in anchors if a["status"] == "valid")}
    distractors = len({r["group_id"] for r in experiment.rows} - gold_groups)
    measured = [r for r in results if r["status"] == "measured"]
    ko_recovered = any(r["language"] == "ko" and r["methods"]["lexical"]["scores"]["all_groups_hit_at_20"] == 0 and
        r["methods"]["hybrid"]["scores"]["all_groups_hit_at_20"] == 1 for r in measured)
    english = [r for r in measured if r["language"] == "en" and
        r["methods"]["lexical"]["scores"]["all_groups_hit_at_20"] == 1]
    preserved = bool(english) and all(r["methods"]["hybrid"]["scores"]["all_groups_hit_at_20"] == 1 for r in english)
    gate = "owner_review_required" if (experiment.manifest["material_kind"] == "private_real" and
        len(measured) == len(results) and len(measured) >= 3 and
        distractors >= 20 and ko_recovered and preserved) else "criteria_not_met"
    return dict(schema="lifhop-semantic-report-v1", run_id=run_id, manifest_digest=experiment.manifest["digest"],
        dataset_digest=experiment.manifest["dataset_digest"], model=MODEL,
        configuration_hash=experiment.manifest["configuration_hash"],
        chunking=experiment.manifest.get("chunking", "indexed"),
        status="measured" if vectors else "no_allowed_corpus", cases=results, non_gold_groups=distractors,
        elapsed_ms=round((time.monotonic()-started)*1000, 2),
        b2_gate=gate)
