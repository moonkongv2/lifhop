"""Synthetic contract delivery and saved rendering, not real-model semantic compliance."""
import json
from pathlib import Path
from copy import deepcopy
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entry import Entry
from app.models.ai_usage import AiUsageAttempt
from app.security import create_access_token
from app.services.answer_transport import payload, parse, MODEL, DIALOGUE_CONFIG_HASH
from app.services.source_history import record_version, select_version
from test_answer_conversations import chat, create, claim, step
from test_embedding_jobs import actor
from test_embedding_store import save


FIXTURE = json.loads(Path('tests/fixtures/followup_validation.json').read_text())
BODY = '\n'.join(r['content'] for r in FIXTURE['corpus'])


def fact(text, quote):
    return dict(text=text, evidence=[dict(id=1, quote=quote)])


def response(parts):
    return dict(model=MODEL, status='completed', usage=dict(input_tokens=10, output_tokens=10, total_tokens=20),
        output=[dict(type='message', content=[dict(type='output_text', text=json.dumps(dict(result=dict(parts=parts))))])])


CASES = [
    ('progress', FIXTURE['turns'][0]['q'], dict(request='두 업체의 견적과 예약 진행', kind='unresolved', known=[
        fact('알파 견적은 30만원이다.', '알파 견적은 30만원'),
        fact('베타 견적은 35만원이다.', '베타 견적은 35만원'),
        fact('사용자는 알파에 예약 요청을 보냈다고 말했다.', '사용자는 알파에 예약 요청을 보냈다고 말했다.'),
        fact('사용자는 아직 업체를 최종 선택했다고 말하지 않았다.', '사용자는 아직 업체를 최종 선택했다고 말하지 않았다.'),
        fact('이 예약 기록에는 확정·결제·실제 이용을 확인하는 내용이 없다.', '이 기록에는 예약 확정, 결제, 실제 차량 이용을 확인하는 내용이 없다.')],
        gap='제공된 기록에서 베타의 예약 진행은 확인할 수 없다.')),
    ('cancellation', '알파의 취소 요청과 취소·환불 완료 여부를 알려줘.', dict(request='알파 취소 진행과 완료 여부', kind='unresolved', known=[
        fact('사용자는 알파에 취소 요청을 보냈다고 말했다.', '사용자는 알파에 취소 요청을 보냈다고 말했다.')],
        gap='이 기록에는 취소·환불 완료를 확인하는 내용이 없다.')),
    ('calculation', '기록된 알파와 베타의 가격 차이를 비교해줘.', dict(request='두 업체의 가격 차이', kind='answered', facts=[
        fact('기록된 가격으로 계산하면 베타가 5만원 더 비싸다(35만원 - 30만원 = 5만원).',
            '알파 견적은 30만원, 베타 견적은 35만원이었다.')])),
    ('missing_beta', FIXTURE['turns'][7]['q'], dict(request='베타 예약 확정 여부', kind='unresolved', known=[],
        gap='제공된 기록에는 베타 예약 확정을 확인하는 내용이 없다.')),
]


@pytest.mark.parametrize('dialogue', [None, [], [dict(question='업체 견적?', answer='이전 답변은 근거가 아니다.')]])
def test_ordinary_and_dialogue_requests_deliver_quality_contract_without_rewriting_sources(dialogue):
    excerpts=[dict(id=1, text=BODY)]
    original=deepcopy(excerpts)
    value, upper=payload('견적과 예약 진행을 알려줘.', excerpts, dialogue=dialogue)
    instructions=value['instructions']
    assert 'preserve explicit source qualifications' in instructions
    assert 'do not invent an unrequested outcome checklist' in instructions
    assert 'one independently supported assertion' in instructions
    assert 'put that scoped unknown in the unresolved gap' in instructions
    assert 'label it as calculated from recorded values' in instructions
    assert 'cite all operands' in instructions
    assert json.loads(value['input'])['excerpts']==original==excerpts
    assert value['store'] is False and value['max_output_tokens']==4096
    assert upper==len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())+1024


@pytest.mark.parametrize('name,q,part', CASES, ids=[c[0] for c in CASES])
def test_cited_limits_calculation_and_scoped_unknown_survive_saved_answer_and_restoration(chat, name, q, part):
    client, headers, bind, owner, eid, answer, planner, query=chat
    with Session(bind) as db:
        entry=db.get(Entry,eid)
        entry.content=BODY
        select_version(db,entry,record_version(db,entry))
        save(db,entry)
        db.commit()
    output=response([part])
    original=deepcopy(output)
    def send(value):
        assert 'preserve explicit source qualifications' in value['instructions']
        assert 'label it as calculated from recorded values' in value['instructions']
        assert json.loads(value['input'])['excerpts'][0]['text']==BODY
        return output
    answer.side_effect=send
    c,_=claim(chat,create(chat),q)
    for stage in ['plan','search','answer']:
        c=step(chat,c,stage)
    turn=c['turns'][-1]
    facts=part.get('facts',part.get('known',[]))
    expected='\n'.join([f['text'] for f in facts]+([part['gap']] if 'gap' in part else []))
    assert turn['answer']==expected
    assert turn['answer_status']==('insufficient' if not facts else 'partial' if 'gap' in part else 'supported')
    assert bool(turn['citations'])==bool(facts)
    if facts:assert turn['citations'][0]['entry_id']==eid
    # Replaying a stage/reading with a new owner token never repairs or resends the response.
    c=step(chat,c,'answer')
    restored=client.get(f"/answer-conversations/{c['id']}",headers=dict(
        Authorization='Bearer '+create_access_token(owner))).json()
    assert restored['turns'][-1]['answer']==expected
    assert answer.call_count==query.call_count==1 and planner.call_count==0
    assert output==original
    with Session(bind) as db:
        row=db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id==owner,AiUsageAttempt.purpose=='answer'))
        assert row.status=='spent' and row.configuration_hash==DIALOGUE_CONFIG_HASH


def test_narrative_modes_keep_their_existing_output_contract():
    for options in [dict(retrospective=True),dict(historical_as_of='2026-04-30')]:
        value,_=payload('기록을 정리해줘.',[dict(id=1,text=BODY)],**options)
        assert 'label it as calculated from recorded values' not in value['instructions']
        assert value['text']['format']['name']=='cited_answer'
        assert value['max_output_tokens']==512


def test_explicit_base_followup_preserves_limits_and_calculation_without_new_search(chat):
    client,headers,bind,owner,eid,answer,planner,query=chat
    with Session(bind) as db:
        entry=db.get(Entry,eid)
        entry.content=BODY
        select_version(db,entry,record_version(db,entry))
        save(db,entry)
        db.commit()
    answer.side_effect=lambda value:response([CASES[0][2]])
    c,_=claim(chat,create(chat),CASES[0][1])
    for stage in ['plan','search','answer']:c=step(chat,c,stage)
    base=c['turns'][0]
    def calculate(value):
        content=json.loads(value['input'])
        assert content['dialogue']==[dict(turn_id=base['id'],question=base['q'],answer=base['answer'],outcome='answer')]
        assert 'label it as calculated from recorded values' in value['instructions']
        return response([CASES[2][2]])
    answer.side_effect=calculate
    c,_=claim(chat,c,FIXTURE['turns'][4]['q'],base_turn_id=base['id'])
    for stage in ['plan','evidence','answer']:c=step(chat,c,stage)
    restored=client.get(f"/answer-conversations/{c['id']}",headers=headers).json()
    assert restored['turns'][0]['answer']==base['answer']
    assert restored['turns'][1]['answer']==CASES[2][2]['facts'][0]['text']
    assert restored['turns'][1]['base_turn_id']==base['id']
    assert answer.call_count==2 and planner.call_count==query.call_count==1


@pytest.mark.parametrize('dialogue',[None,[]])
def test_fact_gap_boundaries_are_delivered_at_schema_fields_without_new_output_fields(dialogue):
    value,_=payload('가격과 활성화 상태?', [dict(id=1,text='Service A costs 10 units.')],dialogue=dialogue)
    schema=value['text']['format']['schema']
    answered,unresolved=schema['properties']['result']['properties']['parts']['items']['anyOf']
    assert answered['required']==['request','kind','facts']
    assert unresolved['required']==['request','kind','known','gap']
    assert schema['$defs']['fact']['required']==['text','evidence']
    assert 'explicit source qualifications' in schema['$defs']['fact']['properties']['text']['description']
    assert 'cannot prove absence' in schema['$defs']['fact']['properties']['evidence']['description']
    assert 'Split subjects' in answered['properties']['request']['description']
    assert 'gap has no evidence quote' in unresolved['properties']['gap']['description']
    assert 'split the price into answered/facts' in value['instructions']
    assert 'activation into unresolved/known=[]' in value['instructions']


def test_separate_subjects_preserve_explicit_limits_and_scoped_gap_without_repair():
    parts=[
        dict(request='알파·베타 가격',kind='answered',facts=[
            fact('알파는30만원, 베타는35만원이다.','알파 견적은 30만원, 베타 견적은 35만원이었다.')]),
        dict(request='알파 예약 진행',kind='answered',facts=[
            fact('알파에 예약 요청을 보냈다고 말했다.','사용자는 알파에 예약 요청을 보냈다고 말했다.'),
            fact('이 기록에는 예약 확정·결제·실제 이용 확인이 없다.','이 기록에는 예약 확정, 결제, 실제 차량 이용을 확인하는 내용이 없다.'),
            fact('사용자는 최종 선택을 보고하지 않았다.','사용자는 아직 업체를 최종 선택했다고 말하지 않았다.')]),
        dict(request='베타 예약 진행',kind='unresolved',known=[],gap='베타 예약 진행은 제공 기록에서 확인되지 않는다.')]
    original=deepcopy(parts)
    result=parse(response(parts),{1},excerpts={1:BODY},question=FIXTURE['turns'][0]['q'])
    assert result['status']=='partial' and result['citation_ids']==[1]
    assert result['answer'].splitlines()==[f['text'] for p in parts for f in p.get('facts',[])]+[parts[-1]['gap']]
    assert result['unconfirmed_aspects']==[parts[-1]['gap']]
    assert parts==original


def test_schema_guidance_does_not_create_a_semantic_validator():
    # Reproduces the known T1 boundary without copying or repairing paid artifacts.
    # Even the strengthened schema cannot detect a wrongly declared answered fact.
    quote='알파 견적은 30만원, 베타 견적은 35만원이었다.'
    parts=[dict(request='베타 예약 진행',kind='answered',facts=[
        fact('베타 예약 진행은 기록되어 있지 않다.',quote)])]
    result=parse(response(parts),{1},excerpts={1:BODY},question='베타 예약 진행?')
    assert result['status']=='supported'  # Structural status, not semantic acceptance.
    assert result['answer']==parts[0]['facts'][0]['text']
