"""Fixed candidate union and body-free manifests/captures for one rerank rule."""
from dataclasses import dataclass
from statistics import mean
from collections import Counter
from datetime import datetime
from app.evaluation.schemas import digest, EvaluationError, now
from app.evaluation.semantic import filtered_rows, group_rank
from app.evaluation.fusion_replay import replay_fusion, LOCATION_KEYS
from app.evaluation.rank_replay import selection, metadata
from app.evaluation.passage_metrics import passage_metrics
from app.evaluation.rank_decision import summarize
from app.services.rerank_transport import payload, cost_micro, CONFIG_HASH, OUTPUT_LIMIT

RULE = dict(version="direct-support-v1",per_lane=50,results=20,rrf_k=60,
    order="grade-desc-rrf-desc-group-asc",input_order="group-asc",transport=CONFIG_HASH,
    representatives="legacy-semantic-preferred",aliases="sorted-location-union",
    criteria=dict(recall20_min=.80,all20_min=.70,max_early_losses=1,preserve_lexical=True,recover_korean=True))
RULE_DIGEST=digest(RULE)


def candidates(lexical,semantic):
    lexical,semantic=lexical[:100],semantic[:100]
    ranks={}
    representatives={}
    aliases={}
    chosen={h['group_id'] for lane in (lexical,semantic) for h in lane[:50]}
    for name,lane in (("lexical",lexical),("semantic",semantic)):
        for rank,h in enumerate(lane,1):
            gid=h['group_id']
            if name in ranks.setdefault(gid,{}):
                raise EvaluationError("RERANK_DUPLICATE_GROUP")
            ranks[gid][name]=rank
            representatives[gid]=h
            aliases.setdefault(gid,set()).update(tuple(a[k] for k in LOCATION_KEYS) for a in h['gold_locations'])
    return [dict(representatives[g],gold_locations=[dict(zip(LOCATION_KEYS,a)) for a in sorted(aliases[g])],
        rrf_score=sum(1/(60+r) for r in ranks[g].values()),wire_id=i)
        for i,g in enumerate(sorted(chosen))]


def ranked(items,grades):
    if len(grades)!=len(items) or any(type(g) is not int or g not in range(4) for g in grades):
        raise EvaluationError("RERANK_GRADES_INVALID")
    return sorted([dict(h,grade=g) for h,g in zip(items,grades)],
        key=lambda h:(-h['grade'],-h['rrf_score'],h['group_id']))[:20]


@dataclass
class PreparedRerank:
    experiment: object
    baseline: dict
    requests: dict
    manifest: dict


def prepare_rerank(experiment,header,captures):
    baseline=replay_fusion(experiment,header,captures)
    requests={}
    cases=[]
    for case in experiment.cases:
        rows=filtered_rows(experiment.rows,case.filters)
        stored=captures[case.id]
        items=candidates(group_rank(rows,stored['lexical_ids'],per_entry_limit=None),
            group_rank(rows,stored['semantic_ids'],per_entry_limit=None))
        value,upper=payload(case.question,[h['text'] for h in items]) if items else (None,0)
        scores=passage_metrics(items,experiment.gold[case.id])
        # Report oracle coverage at up to 100 candidates, not only the first twenty.
        full=scores['group_ranks']
        requests[case.id]=dict(items=items,payload=value,input_upper=upper)
        cases.append(dict(case_id=case.id,request_digest=digest(value),candidate_count=len(items),
            input_upper=upper,max_micro_usd=cost_micro(upper,OUTPUT_LIMIT) if items else 0,
            candidates=selection(items),group_ranks=full,
            candidate_recall=mean(int(r is not None) for r in full.values()) if full else None,
            all_candidate_evidence=int(all(r is not None for r in full.values())) if full else None))
    manifest=dict(schema="lifhop-rerank-manifest-v1",rule_digest=RULE_DIGEST,
        source_capture_digest=header['digest'],source_manifest_digest=experiment.manifest['digest'],
        source_config={k:experiment.manifest[k] for k in ('provider','scope','entry_ids','chunking')},
        source_config_digest=digest({k:experiment.manifest[k] for k in ('provider','scope','entry_ids','chunking')}),
        dataset_digest=experiment.manifest['dataset_digest'],owner_id=experiment.manifest['owner_id'],
        database_fingerprint=experiment.manifest['database_fingerprint'],policy_revision=experiment.manifest['policy_revision'],
        corpus_digest=digest(experiment.manifest['corpus']),cases=cases,
        estimated_max_micro_usd=sum(c['max_micro_usd'] for c in cases),max_calls=sum(bool(c['candidate_count']) for c in cases))
    manifest['digest']=digest(manifest)
    return PreparedRerank(experiment,baseline,requests,manifest)


def evaluate(prepared, grade_lists, *, provider_calls=0):
    if set(grade_lists)!=set(prepared.requests):
        raise EvaluationError("RERANK_CAPTURE_INCOMPLETE")
    cases=[]
    for case in prepared.experiment.cases:
        items=prepared.requests[case.id]['items']
        hits=ranked(items,grade_lists[case.id])
        families=Counter(metadata(h)['family_id'] for h in hits)
        base=next(c for c in prepared.baseline['variants']['B0']['cases'] if c['case_id']==case.id)
        cases.append(dict(case_id=case.id,language=case.language,expected_outcome=case.expected_outcome,
            status=base['status'],methods=dict(lexical=base['methods']['lexical'],
                hybrid=dict(hits=selection(hits),scores=passage_metrics(hits,prepared.experiment.gold[case.id]),
                    distinct_families=len(families),max_family_results=max(families.values(),default=0))),
            grades=[dict(group_id=h['group_id'],grade=g,rrf_score=h['rrf_score']) for h,g in zip(items,grade_lists[case.id])]))
    result=dict(schema="lifhop-rerank-result-v1",manifest_digest=prepared.manifest['digest'],
        rule_digest=RULE_DIGEST,status="measured",measured_at=now().isoformat(),provider_calls=provider_calls,cases=cases)
    summary=decision_summary(cases,prepared.baseline['variants']['B0']['cases'])
    result['summary']=summary
    result['b2_gate']='independent_validation_required'
    return result


def decision_summary(cases,baseline):
    summary=summarize(cases)
    for k in (5,10):
        base={c['case_id']:c for c in baseline}
        lost=[c['case_id'] for c in cases if c['expected_outcome']=='supported'
            and base[c['case_id']]['methods']['hybrid']['scores'][f'group_recall_at_{k}']==1
            and c['methods']['hybrid']['scores'][f'group_recall_at_{k}']!=1]
        summary[f'lost_at_{k}']=lost
        summary['eligible'] &= len(lost)<=1
    return summary


def freeze(results,prepared_sets,validation_dataset):
    manifests=[p.manifest for p in prepared_sets]
    binding=('owner_id','database_fingerprint','policy_revision','corpus_digest','rule_digest','source_config_digest')
    if (not results or len(results)!=len(manifests)
            or any(r['status']!='measured' or r['manifest_digest']!=m['digest']
                for r,m in zip(results,manifests))
            or any(tuple(m[k] for k in binding)!=tuple(manifests[0][k] for k in binding) for m in manifests)):
        raise EvaluationError('RERANK_FREEZE_INVALID')
    if (not validation_dataset.cases or any(c.status!='reviewed' for c in validation_dataset.cases)
            or validation_dataset.owner_id!=manifests[0]['owner_id']
            or validation_dataset.database_fingerprint!=manifests[0]['database_fingerprint']
            or validation_dataset.digest in {m['dataset_digest'] for m in manifests}):
        raise EvaluationError('VALIDATION_REVIEW_REQUIRED')
    cases=[c for r in results for c in r['cases']]
    if any(c.reviewed_at>min(datetime.fromisoformat(r['measured_at']) for r in results)
            for c in validation_dataset.cases):
        raise EvaluationError('VALIDATION_REVIEW_TOO_LATE')
    if len({c['case_id'] for c in cases})!=len(cases):
        raise EvaluationError('RERANK_DUPLICATE_CASE')
    baselines=[c for p in prepared_sets for c in p.baseline['variants']['B0']['cases']]
    summary=decision_summary(cases,baselines)
    result=dict(schema='lifhop-rerank-freeze-v1',rule_digest=RULE_DIGEST,
        binding={k:manifests[0][k] for k in binding},validation_digest=validation_dataset.digest,
        input_manifests=[m['digest'] for m in manifests],result_digests=[digest(r) for r in results],
        frozen_at=now().isoformat(),summary=summary,selected='T' if summary['eligible'] else None,
        status='frozen' if summary['eligible'] else 'no_candidate')
    result['digest']=digest(result)
    return result


def validate_frozen(frozen,result,prepared):
    if (frozen.get('digest')!=digest({k:v for k,v in frozen.items() if k!='digest'})
            or frozen['rule_digest']!=RULE_DIGEST or frozen['status']!='frozen'
            or frozen['selected']!='T' or result['status']!='measured'
            or result['manifest_digest']!=prepared.manifest['digest']
            or frozen['validation_digest']!=prepared.manifest['dataset_digest']
            or frozen['binding']!={k:prepared.manifest[k] for k in frozen['binding']}):
        raise EvaluationError('RERANK_FREEZE_CHANGED')
    return dict(freeze_digest=frozen['digest'],result_digest=digest(result),selected='T',
        summary=result['summary'],b2_gate='owner_review_required' if result['summary']['eligible'] else 'criteria_not_met')
