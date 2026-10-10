"""New fusion rules over verified legacy captures; never dispatch a provider."""
from collections import Counter
import time

from app.evaluation.schemas import EvaluationError, digest, canonical_bytes, now
from app.evaluation.storage import write_private, read_private, MAX_DATASET_BYTES
from app.evaluation.semantic import group_rank, filtered_rows
from app.evaluation.rank_replay import replay, selection, metadata, RULE_DIGEST as CAPTURE_RULE_DIGEST
from app.evaluation.passage_metrics import passage_metrics

CONFIG = dict(version="fusion-v1", candidates=100, results=20, rrf_k=60,
    weights=[1,1], protected_per_lane=5, variants=["B0","R","P","S"],
    representatives="legacy-semantic-preferred", aliases="sorted-location-union")
RULE_DIGEST = digest(CONFIG)
LOCATION_KEYS = ("entry_id","version_id","field","start","end")


def rank_candidates(lexical, semantic, variant):
    if variant not in CONFIG["variants"]:
        raise EvaluationError("FUSION_VARIANT_INVALID")
    lexical, semantic = lexical[:100], semantic[:100]
    scores, representatives, locations, ranks = {}, {}, {}, {}
    for name,lane in (("lexical",lexical),("semantic",semantic)):
        for rank,hit in enumerate(lane,1):
            gid=hit["group_id"]
            if name in ranks.setdefault(gid,{}):
                raise EvaluationError("FUSION_DUPLICATE_GROUP")
            ranks[gid][name]=rank
            scores[gid]=scores.get(gid,0)+1/(60+rank)
            # Retain the original fusion's representative choice.
            representatives[gid]=hit
            locations.setdefault(gid,set()).update(tuple(a[k] for k in LOCATION_KEYS)
                for a in hit["gold_locations"])
    protected={h["group_id"] for lane in (lexical,semantic) for h in lane[:5]}
    order=sorted(scores,key=lambda gid:(-scores[gid],gid))
    if variant=="P":
        order=[g for g in order if g in protected]+[g for g in order if g not in protected]
    elif variant=="S":
        order=[h["group_id"] for h in semantic]
    counts,selected,trace=Counter(),[],[]
    for position,gid in enumerate(order,1):
        hit=representatives[gid]
        reason=None
        if variant=="B0" and counts[hit["entry_id"]]>=2:
            reason="entry_quota"
        else:
            counts[hit["entry_id"]]+=1
            if len(selected)>=20:
                reason="top20"
        if reason is None:
            selected.append(dict(hit,gold_locations=[dict(zip(LOCATION_KEYS,a)) for a in sorted(locations[gid])]))
        trace.append(dict(group_id=gid,entry_id=hit["entry_id"],candidate_position=position,
            lexical_rank=ranks[gid].get("lexical"),semantic_rank=ranks[gid].get("semantic"),
            lexical_contribution=1/(60+ranks[gid]["lexical"]) if "lexical" in ranks[gid] else 0,
            semantic_contribution=1/(60+ranks[gid]["semantic"]) if "semantic" in ranks[gid] else 0,
            rrf_score=scores[gid],protected=variant=="P" and gid in protected,
            final_rank=len(selected) if reason is None else None,exclusion=reason))
    if variant=="S":
        trace.extend(dict(group_id=g,entry_id=representatives[g]["entry_id"],
            lexical_rank=ranks[g]["lexical"],semantic_rank=None,lexical_contribution=1/(60+ranks[g]["lexical"]),
            semantic_contribution=0,rrf_score=scores[g],protected=False,final_rank=None,
            candidate_position=None,exclusion="semantic_only") for g in scores if "semantic" not in ranks[g])
    return selected,trace


def replay_fusion(experiment, header, captures, *, family_map=None):
    legacy=replay(experiment,header,captures)
    family_map=family_map or {}
    result=dict(schema="lifhop-fusion-replay-v1",status="measured",rule_digest=RULE_DIGEST,
        capture_rule_digest=CAPTURE_RULE_DIGEST,capture_digest=header["digest"],
        dataset_digest=experiment.manifest["dataset_digest"],manifest_digest=experiment.manifest["digest"],
        owner_id=experiment.manifest["owner_id"],database_fingerprint=experiment.manifest["database_fingerprint"],
        policy_revision=experiment.manifest["policy_revision"],corpus_digest=digest(experiment.manifest["corpus"]),
        source_config_digest=experiment.manifest["configuration_hash"],replayed_at=now().isoformat(),
        source_run_id=header["run_id"],family_map_digest=digest(family_map),provider_calls=0,
        b2_gate="independent_validation_required",variants={})
    checks={name:{c["case_id"]:c for c in v["cases"]} for name,v in legacy["variants"].items()}
    for variant in CONFIG["variants"]:
        cases=[]
        for case in experiment.cases:
            start=time.monotonic()
            rows=filtered_rows(experiment.rows,case.filters)
            captured=captures[case.id]
            lex=group_rank(rows,captured["lexical_ids"],per_entry_limit=None)
            sem=group_rank(rows,captured["semantic_ids"],per_entry_limit=None)
            hits,trace=rank_candidates(lex,sem,variant)
            scores=passage_metrics(hits,experiment.gold[case.id])
            previous=checks["B" if variant!="R" else "D"][case.id]
            method="semantic" if variant=="S" else "hybrid"
            if variant in {"B0","R","S"}:
                expected=previous["methods"][method]
                if selection(hits)!=expected["hits"] or scores!=expected["scores"]:
                    raise EvaluationError("FUSION_BASELINE_MISMATCH")
            family_by_id={r["id"]:family_map.get(metadata(r)["family_id"],metadata(r)["family_id"]) for r in rows}
            counts=Counter(family_by_id[h["id"]] for h in hits)
            cases.append(dict(case_id=case.id,language=case.language,expected_outcome=case.expected_outcome,
                status=previous["status"],methods=dict(lexical=previous["methods"]["lexical"],
                    hybrid=dict(scores=scores,hits=selection(hits),distinct_families=len(counts),
                        max_family_results=max(counts.values(),default=0))),
                trace=trace,replay_ms=round((time.monotonic()-start)*1000,2)))
        result["variants"][variant]=dict(cases=cases,mode="semantic" if variant=="S" else "hybrid")
    return result


def write_fusion_report(directory, report, *, root):
    """Keep case traces bounded and publish their body-free index last."""
    index={k:v for k,v in report.items() if k!="variants"}
    index["variants"]={}
    documents=[]
    for variant,value in report["variants"].items():
        cases=[]
        for number,case in enumerate(value["cases"]):
            name=f"{variant}-{number:02d}.json"
            documents.append((directory/name,case))
            cases.append(dict(case_id=case["case_id"],file=name,digest=digest(case)))
        index["variants"][variant]=dict(mode=value["mode"],cases=cases)
    index["digest"]=digest(index)
    documents.append((directory/"report.json",index))
    sizes=[len(canonical_bytes(v)) for _,v in documents]
    if any(n>MAX_DATASET_BYTES for n in sizes) or sum(sizes)>16*1024*1024:
        raise EvaluationError("FUSION_REPORT_SIZE_LIMIT")
    for path,value in documents:
        write_private(path,value,root=root)
    return directory/"report.json"


def load_fusion_report(path, *, root):
    index=read_private(path,root)
    if (index.get("schema")!="lifhop-fusion-replay-v1" or index.get("rule_digest")!=RULE_DIGEST
            or index.get("digest")!=digest({k:v for k,v in index.items() if k!="digest"})
            or set(index["variants"])!=set(CONFIG["variants"])):
        raise EvaluationError("FUSION_REPORT_INVALID")
    total=len(canonical_bytes(index))
    result={k:v for k,v in index.items() if k not in {"digest","variants"}}
    result["variants"]={}
    for variant,value in index["variants"].items():
        if len(value["cases"])>100:
            raise EvaluationError("FUSION_REPORT_INVALID")
        cases=[]
        for number,item in enumerate(value["cases"]):
            if item["file"]!=f"{variant}-{number:02d}.json":
                raise EvaluationError("FUSION_REPORT_INVALID")
            case=read_private(path.parent/item["file"],root)
            total+=len(canonical_bytes(case))
            if digest(case)!=item["digest"] or case["case_id"]!=item["case_id"] or total>16*1024*1024:
                raise EvaluationError("FUSION_REPORT_INVALID")
            cases.append(case)
        result["variants"][variant]=dict(mode=value["mode"],cases=cases)
    return result
