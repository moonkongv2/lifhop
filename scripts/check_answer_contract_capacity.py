"""Offline capacity report from an already-reviewed, closed comparison bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from html import escape

from app.evaluation.answer_contract_capacity import (
    VERSION, REQUEST_LIMIT, OUTPUT_LIMIT, candidate_request, byte_size,
    synthetic_outputs, output_assessment)
from app.evaluation.schemas import digest
from app.evaluation.storage import PRIVATE_ROOT, read_private, write_private
from app.services.answer_transport import CONFIG_HASH


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--closed-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tokenizer-package', type=Path)
    parser.add_argument('--tokenizer-cache', type=Path)
    args = parser.parse_args()
    frozen = read_private(args.review/'proposal.json', PRIVATE_ROOT)
    assert digest({k:v for k,v in frozen.items() if k!='digest'}) == frozen['digest']
    assert frozen['configuration_hash'] == CONFIG_HASH
    closed = read_private(args.closed_run/'report.json', PRIVATE_ROOT)
    assert closed['state']=='closed_all_planned_requests_reviewed'
    assert closed['proposal_digest']==frozen['digest']
    source = read_private(args.review/'requests.json', PRIVATE_ROOT)
    contexts = read_private(args.review/'prepared-contexts.json', PRIVATE_ROOT)
    assert len(source)==14 and len(contexts)==7
    inputs, candidates = [], []
    for old in source:
        assert digest(old['request']) == old['request_digest']
        if old['model']!='gpt-6-luna' or old['case_id'] in ['period-review','historical-cutoff']:
            continue
        new = candidate_request(old['request'])
        assert new['input'] == old['request']['input'] and new['max_output_tokens']==OUTPUT_LIMIT
        inputs.append(dict(case_id=old['case_id'],old_bytes=byte_size(old['request']),
            candidate_bytes=byte_size(new),limit=REQUEST_LIMIT,passed=byte_size(new)<=REQUEST_LIMIT,
            exact_input_digest=digest(new['input'])))
        candidates.append(dict(case_id=old['case_id'],request=new))
    assert len(inputs)==5
    mapping, tokenizer_version, counter, diagnostic_encoding = None, None, None, None
    def no_network(*a, **kw):
        raise RuntimeError('NETWORK_DISABLED_IN_CAPACITY_CHECK')
    connect = socket.socket.connect
    socket.socket.connect = no_network
    try:
        if args.tokenizer_package:
            sys.path.insert(0,str(args.tokenizer_package))
            if args.tokenizer_cache:
                os.environ['TIKTOKEN_CACHE_DIR']=str(args.tokenizer_cache)
            import tiktoken
            tokenizer_version=tiktoken.__version__
            try:
                mapping=tiktoken.encoding_name_for_model('gpt-6-luna')
            except KeyError:
                pass
            diagnostic_encoding=mapping or 'o200k_base'
            encoding=tiktoken.get_encoding(diagnostic_encoding)
            counter=lambda value:len(encoding.encode(value,disallowed_special=()))
        output=output_assessment(synthetic_outputs(),diagnostic_counter=counter,
            diagnostic_encoding=diagnostic_encoding)
    finally:
        socket.socket.connect=connect
    output.update(installed_model_mapping=mapping,tokenizer_version=tokenizer_version,
        tokenizer_network_disabled=True)
    # Even a future local mapping would require a fresh target-capacity review;
    # this tool never promotes a reference count to a provider guarantee.
    preserved=read_private(args.closed_run/'preserved-artifacts.json',PRIVATE_ROOT)
    for folder in [args.review,args.closed_run]:
        for file in folder.iterdir():
            if file.is_file():preserved[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
    for file,sha in preserved.items():
        assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==sha
    report=dict(version=VERSION,state='capacity_gate_not_passed',input_passed=all(x['passed'] for x in inputs),
        output_passed=False,inputs=inputs,output=output,provider_calls=0,new_charge_micro_usd=0,
        production_configuration_hash=CONFIG_HASH,production_configuration_changed=False,
        preserved_files=len(preserved),review_digest=frozen['digest'],
        limits=dict(request_bytes=REQUEST_LIMIT,output_tokens=OUTPUT_LIMIT),
        limitations=['No Luna tokenizer mapping; reference encoding counts are not target-model counts.',
            'No provider schema acceptance or generated-answer quality tested.',
            'Do not proceed to production wiring or paid preparation until both gates pass.'])
    checklist=[dict(case_id=x['case']['id'],question=x['case']['question'],
        required_v1=x['case']['required'],unknowns_v1=x['case']['unknowns'],
        rubric_alignment_note='Existing v1 remains unchanged; framework/progress details remain separately flagged.')
        for x in contexts]
    for name,value in [('report.json',report),('candidate-requests.json',candidates),
            ('synthetic-outputs.json',synthetic_outputs()),('v1-checklist.json',checklist),
            ('preserved-artifacts.json',preserved)]:
        write_private(args.output/name,value,root=PRIVATE_ROOT)
    rows=''.join('<tr><td>'+escape(x['case_id'])+'</td><td>'+str(x['old_bytes'])+'</td><td>'+
        str(x['candidate_bytes'])+'</td><td>'+('통과' if x['passed'] else '초과')+'</td></tr>' for x in inputs)
    page='<!doctype html><html lang="ko"><meta charset="utf-8"><title>근거 계약 크기 게이트</title><style>body{max-width:1000px;margin:30px auto;font:16px/1.6 sans-serif}table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px}pre{white-space:pre-wrap}</style><h1>근거 계약 크기 게이트: 미통과</h1><p>기존 일반 5문맥의 질문·원문·메타데이터를 그대로 보존하고 지침/schema만 교체했습니다. 실제 전송은 없습니다.</p><table><tr><th>사례</th><th>기존 bytes</th><th>후보 bytes</th><th>14 KiB</th></tr>'+rows+'</table><h2>합성 출력 검사</h2><pre>'+escape(json.dumps(output,ensure_ascii=False,indent=2))+'</pre><p>Luna의 토크나이저 매핑은 확인되지 않았습니다. o200k_base 수치는 참고용이며 Luna의 실제 토큰 수로 해석하면 안 됩니다. 512토큰 수용을 검증하지 못했으므로 계획대로 제품 연결/유료 제안은 중단합니다. 원문 절단·출력 상한 자동 상향·기준 완화는 없습니다.</p><p>검토 가능한 다음 대안: 계약 중복/구절 길이를 줄이는 별도 설계 또는 정확한 대상 출력 용량 확인과 더 큰 출력 상한/비용 제안. 새 상한은 아직 적용하거나 승인받지 않았습니다.</p><p>보존 파일 '+str(len(preserved))+'개. 새 AI 호출/과금 0. <a href="report.json">수치 보고서</a> · <a href="candidate-requests.json">미전송 후보</a> · <a href="v1-checklist.json">동결 v1 체크리스트</a></p></html>'
    write_private(args.output/'report.html',page.encode(),root=PRIVATE_ROOT)
    print(json.dumps(dict(folder=str(args.output),state=report['state'],input_passed=report['input_passed'],
        output=output,inputs=inputs,preserved_files=len(preserved),provider_calls=0),ensure_ascii=False))


if __name__=='__main__':
    main()
