"""Immutable bounded grade captures; replay never contacts a provider."""
from app.evaluation.schemas import digest, canonical_bytes, EvaluationError, now
from app.evaluation.storage import write_private, read_private, MAX_DATASET_BYTES
from app.evaluation.rerank import RULE_DIGEST, evaluate


def publish(directory,prepared,grade_lists,*,status,usage,root,timings=None):
    documents=[]
    index=dict(schema='lifhop-rerank-capture-v1',rule_digest=RULE_DIGEST,
        manifest_digest=prepared.manifest['digest'],captured_at=now().isoformat(),
        status=status,usage=usage,cases=[],timings=timings or {})
    for i,(cid,values) in enumerate(grade_lists.items()):
        value=dict(case_id=cid,request_digest=digest(prepared.requests[cid]['payload']),grades=values)
        filename=f'case-{i:02d}.json'
        documents.append((directory/filename,value))
        index['cases'].append(dict(case_id=cid,file=filename,digest=digest(value)))
    index['digest']=digest(index)
    documents.append((directory/'capture.json',index))
    sizes=[len(canonical_bytes(v)) for _,v in documents]
    if any(s>MAX_DATASET_BYTES for s in sizes) or sum(sizes)>16*1024*1024:
        raise EvaluationError('RERANK_CAPTURE_LIMIT')
    for path,value in documents:
        write_private(path,value,root=root)
    return directory/'capture.json'


def replay(path,prepared,*,root):
    header=read_private(path,root)
    if (header.get('digest')!=digest({k:v for k,v in header.items() if k!='digest'})
            or header['schema']!='lifhop-rerank-capture-v1' or header['rule_digest']!=RULE_DIGEST
            or header['manifest_digest']!=prepared.manifest['digest'] or header['status']!='measured'
            or len(header['cases'])>100):
        raise EvaluationError('RERANK_CAPTURE_INVALID')
    values={}
    size=len(canonical_bytes(header))
    for i,item in enumerate(header['cases']):
        cid=item['case_id']
        if item['file']!=f'case-{i:02d}.json' or cid in values or cid not in prepared.requests:
            raise EvaluationError('RERANK_CAPTURE_INVALID')
        value=read_private(path.parent/item['file'],root)
        size+=len(canonical_bytes(value))
        if (digest(value)!=item['digest'] or value['case_id']!=cid
                or value['request_digest']!=digest(prepared.requests[cid]['payload'])
                or size>16*1024*1024 or len(value['grades'])>100):
            raise EvaluationError('RERANK_CAPTURE_INVALID')
        values[cid]=value['grades']
    result=evaluate(prepared,values,provider_calls=0)
    result['measured_at']=header['captured_at']
    return result
