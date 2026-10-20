"""Freeze a synthetic real-model proposal offline. Does not read DB or call providers."""
import argparse
import hashlib
import json
from pathlib import Path
from app.services import answer_transport as answer, followup_transport as planner, embedding_transport as embedding
from app.config import settings

ROOT=Path(__file__).resolve().parents[1]


def prepare():
    fixture_path=ROOT/'tests/fixtures/followup_validation.json'
    raw=fixture_path.read_bytes()
    fixture=json.loads(raw)
    texts=[r['content'] for r in fixture['corpus']]
    assert all(len(s)<=600 for s in texts)
    document_upper=embedding.input_bound(texts)
    document_cost=embedding.cost_micro(document_upper)
    bounds=dict(planner=planner.cost_micro(25600,1024),answer=answer.cost_micro(66560,4096),query=embedding.cost_micro(2048))
    calls=dict(document=1,planner=0,query=0,answer=0)
    rows=[]
    for t in fixture['turns']:
        cost=0
        if t['planner']:calls['planner']+=1;cost+=bounds['planner']
        if t['branch']=='search':calls['query']+=1;cost+=bounds['query']
        if t['branch']!='clarify':calls['answer']+=1;cost+=bounds['answer']
        rows.append(dict(id=t['id'],max_micro_usd=cost))
    files=sorted([*ROOT.glob('app/services/*.py'),*ROOT.glob('app/models/*.py'),
        *ROOT.glob('app/api/*.py'),ROOT/'app/schemas/answer_conversation.py',
        ROOT/'app/auth.py',ROOT/'app/security.py',ROOT/'app/db.py',ROOT/'app/config.py',
        ROOT/'app/evaluation/followup_run.py',ROOT/'scripts/run_followup_validation.py',
        fixture_path,Path(__file__)])
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    plan=dict(version=fixture['version'],status='prepared-not-authorized',fixture_sha256=hashlib.sha256(raw).hexdigest(),
        corpus=fixture['corpus'],turns=fixture['turns'],code_hashes=hashes,
        configs=dict(answer=answer.DIALOGUE_CONFIG_HASH,planner=planner.CONFIG_HASH,embedding=embedding.CONFIG),
        models=dict(generation=answer.MODEL,embedding=embedding.MODEL),
        limits=dict(history_bytes=16384,planner_wire_bytes=24576,answer_wire_bytes=65536,planner_output=1024,answer_output=4096),
        document_input_upper=document_upper,document_max_micro_usd=document_cost,turn_maxima=rows,
        max_calls=calls,max_total_calls=sum(calls.values()),
        max_micro_usd=document_cost+sum(r['max_micro_usd'] for r in rows),
        retries=0,personal_records=0,personal_policy_changes=0,
        billing=dict(corpus='isolated-loopback-test-schema',live_ledger='existing-app-ai-usage',
            scope=settings.embedding_billing_scope,
            monthly_limit_micro_usd=settings.embedding_monthly_limit_micro_usd,
            owner_domain='negative-protocol-digest',existing_rows='unchanged',max_new_rows=18),
        stop_on=['scope/code/config/permission/version change','unexpected branch before next dispatch',
            'provider or transport/usage error','uncertain accounting','output contract failure','deadline/budget exhaustion'])
    plan['digest']=hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'.local/verification/followup-validation/proposal.json')
    args=parser.parse_args()
    plan=prepare()
    args.out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with args.out.open('x',encoding='utf-8') as f:
        import os
        os.chmod(args.out,0o600)
        json.dump(plan,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:plan[k] for k in ['status','digest','max_calls','max_total_calls','max_micro_usd']},ensure_ascii=False))


if __name__=='__main__':main()
