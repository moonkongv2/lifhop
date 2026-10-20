"""Synthetic part results; structural acceptance is not semantic proof."""
from copy import deepcopy
import json
import pytest
from app.services.answer_transport import MODEL, AnswerOutputError, parse, payload, usage
from app.services.embedding_transport import EmbeddingError

BODIES = {11: 'The blue switch was selected. Testing is planned.',
          22: 'This review did not run execution tests.',
          33: 'The second requested fact was confirmed.'}


def fact(source=11, quote='The blue switch was selected.', text='The blue switch was selected.'):
    return dict(text=text, evidence=[dict(id=source, quote=quote)])


def result(unresolved=False):
    part = dict(request='Which switch was selected?', kind='answered', facts=[fact()])
    if unresolved:
        part = dict(request='Which switch and what test outcome?', kind='unresolved',
            known=[fact()], gap='The final test result is unconfirmed in these records.')
    return dict(parts=[part])


def raw(data):
    return dict(model=MODEL, status='completed', output=[dict(type='message',
        content=[dict(type='output_text', text=json.dumps(dict(result=data)))])])


def parsed(data):
    return parse(raw(data), set(BODIES), excerpts=BODIES, question='Which switch was selected?')


def test_server_assembles_facts_gaps_status_and_citation_union_in_part_order():
    data=result()
    data['parts'].append(dict(request='Second fact and final outcome?', kind='unresolved',
        known=[fact(33, BODIES[33], 'The second fact was confirmed.'), fact()], gap='The final outcome is unknown.'))
    assert parsed(data)==dict(status='partial',
        answer='The blue switch was selected.\nThe second fact was confirmed.\nThe blue switch was selected.\nThe final outcome is unknown.',
        citation_ids=[11,33],unconfirmed_aspects=['The final outcome is unknown.'])
    assert parsed(result())['status']=='supported'


def test_empty_known_is_insufficient_and_retains_scoped_explanation():
    data=result(True)
    data['parts'][0]['known']=[]
    assert parsed(data)==dict(status='insufficient',answer=data['parts'][0]['gap'],citation_ids=[],unconfirmed_aspects=[])
    data['parts'].insert(0,result()['parts'][0])
    assert parsed(data)['status']=='partial'


@pytest.mark.parametrize('change',[
    lambda d:d.update(extra=True),
    lambda d:d.update(claims=[],unknowns=[]),
    lambda d:d.update(parts=[]),
    lambda d:d['parts'].extend([deepcopy(d['parts'][0]) for _ in range(3)]),
    lambda d:d['parts'][0].update(complete=True),
    lambda d:d['parts'][0].update(request=' '),
    lambda d:d['parts'][0].update(request='x'*81),
    lambda d:d['parts'][0].update(kind=True),
    lambda d:d['parts'][0].update(kind='background'),
    lambda d:d['parts'][0].update(gap='Unconfirmed.'),
    lambda d:d['parts'][0].update(known=[]),
    lambda d:d['parts'][0].update(facts=[]),
    lambda d:d['parts'][0]['facts'][0].update(kind='background'),
    lambda d:d['parts'][0]['facts'][0].update(part=1),
    lambda d:d['parts'][0]['facts'][0].update(text='x'*151),
    lambda d:d['parts'][0]['facts'][0].update(text=' '),
    lambda d:d['parts'][0]['facts'][0].update(evidence=[]),
    lambda d:d['parts'][0]['facts'][0]['evidence'][0].update(id=True),
    lambda d:d['parts'][0]['facts'][0]['evidence'][0].update(id=99),
    lambda d:d['parts'][0]['facts'][0]['evidence'][0].update(quote='the blue switch was selected.'),
    lambda d:d['parts'][0]['facts'][0]['evidence'][0].update(quote='The blue  switch was selected.'),
    lambda d:d['parts'][0]['facts'][0]['evidence'][0].update(quote=' '),
    lambda d:d['parts'][0]['facts'][0]['evidence'][0].update(quote='x'*121),
    lambda d:d['parts'][0]['facts'][0]['evidence'].append(deepcopy(d['parts'][0]['facts'][0]['evidence'][0])),
])
def test_invalid_branch_or_evidence_is_rejected_without_repair(change):
    data=result()
    change(data)
    original=deepcopy(data)
    with pytest.raises(AnswerOutputError,match='ANSWER_OUTPUT_INVALID'):parsed(data)
    assert data==original


@pytest.mark.parametrize('change',[
    lambda p:p.pop('gap'), lambda p:p.update(gap=' '), lambda p:p.update(gap='x'*141),
    lambda p:p.update(facts=[]), lambda p:p.pop('known'), lambda p:p.update(known=None),
])
def test_unresolved_requires_its_own_bounded_gap(change):
    data=result(True)
    change(data['parts'][0])
    with pytest.raises(AnswerOutputError):parsed(data)


def test_old_completed_response_is_rejected_instead_of_upgraded():
    old=dict(parts=[dict(id=1,text='Question',complete=False)],
        claims=[dict(part=1,kind='answer',**fact())],unknowns=[])
    with pytest.raises(AnswerOutputError):parsed(old)


def test_global_fact_and_reference_budgets_span_parts():
    data=result()
    data['parts'][0]['facts']=[fact() for _ in range(4)]
    data['parts'].append(deepcopy(data['parts'][0]))
    with pytest.raises(AnswerOutputError):parsed(data)
    data['parts'][0]['facts']=[fact() for _ in range(3)]
    data['parts'][1]['facts']=[fact() for _ in range(3)]
    for p in data['parts']:
        for f in p['facts']:
            f['evidence'].append(dict(id=11,quote='Testing is planned.'))
    with pytest.raises(AnswerOutputError) as error:parsed(data)
    assert error.value.reason=='claim_evidence'
    for p in data['parts']:
        for f in p['facts']:f['evidence'].pop()
    assert parsed(data)['status']=='supported'


def test_maximum_render_is_1328_characters_without_truncation():
    data=dict(parts=[dict(request='p'*80,kind='unresolved',known=[
        fact(text='x'*150),fact(text='y'*150)],gap='u'*140) for _ in range(3)])
    assert len(parsed(data)['answer'])==1328


def test_scoped_review_nonexecution_is_a_fact_but_not_automatic_outcome_completion():
    known=fact(22,BODIES[22],BODIES[22])
    data=dict(parts=[dict(request='Did deployment succeed?',kind='unresolved',known=[known],
        gap='Deployment success is unconfirmed in these records.')])
    assert parsed(data)['status']=='partial'
    data=dict(parts=[dict(request='Did this review run tests?',kind='answered',facts=[known])])
    assert parsed(data)['status']=='supported'
    # Exact quotes cannot detect a model's semantic misclassification.
    data['parts'][0]['facts'][0]['text']='The deployment failed everywhere.'
    assert parsed(data)['status']=='supported'


def test_narrative_is_not_autodetected_or_accepted_by_current_mode():
    legacy=dict(status='supported',answer='A legacy answer.',citation_ids=[11],unconfirmed_aspects=[])
    with pytest.raises(AnswerOutputError):parsed(legacy)
    assert parse(raw(legacy),set(BODIES),historical=True)==legacy
    with pytest.raises(AnswerOutputError):parse(raw(result()),set(BODIES),historical=True)
    with pytest.raises(AnswerOutputError):parse(raw(result()),set(BODIES))


def test_mode_schema_and_limits_are_explicit_and_usage_uses_request_bound():
    for options,limit in [({},4096),({'retrospective':True},512),({'historical_as_of':'2026-01-31'},512)]:
        value,_=payload('Synthetic question?',[dict(id=11,text=BODIES[11])],**options)
        assert value['max_output_tokens']==limit
        schema=json.dumps(value['text']['format']['schema'])
        assert ('answered' in schema)==(not options)
        if not options:
            assert not any(word in schema for word in ['complete','background','unknowns'])
            assert 'Silence is not evidence of non-execution' in value['instructions']
            assert 'not operational failure or non-execution elsewhere' in value['instructions']
        response=dict(model=MODEL,usage=dict(input_tokens=10,output_tokens=limit,total_tokens=limit+10))
        assert usage(response,100,output_limit=limit)==(10,limit)
        response['usage'].update(output_tokens=limit+1,total_tokens=limit+11)
        with pytest.raises(EmbeddingError,match='ANSWER_USAGE_INVALID'):usage(response,100,output_limit=limit)


def test_duplicate_source_identity_is_rejected_before_dispatch():
    with pytest.raises(EmbeddingError,match='ANSWER_INPUT_LIMIT'):
        payload('Synthetic question?',[dict(id=11,text='First.'),dict(id=11,text='Second.')])


def test_wire_schema_couples_each_branch_and_reuses_one_fact_definition():
    from app.services.answer_claims import SCHEMA
    branches=SCHEMA['properties']['result']['properties']['parts']['items']['anyOf']
    answered,unresolved=branches
    assert answered['required']==['request','kind','facts']
    assert unresolved['required']==['request','kind','known','gap']
    assert all(b['additionalProperties'] is False for b in branches)
    assert answered['properties']['kind']['enum']==['answered']
    assert unresolved['properties']['kind']['enum']==['unresolved']
    assert answered['properties']['facts']['minItems']==1
    assert unresolved['properties']['known']['minItems']==0
    assert unresolved['properties']['gap']['minLength']==1
    for branch,key in [(answered,'facts'),(unresolved,'known')]:
        assert branch['properties'][key]['items']=={'$ref':'#/$defs/fact'}
    assert SCHEMA['$defs']['fact']['required']==['text','evidence']


def test_full_input_is_preserved_and_oversize_is_rejected_without_truncation():
    excerpts=[dict(id=i,text='기록 '*200,title='Synthetic source',source='manual') for i in range(5)]
    original=deepcopy(excerpts)
    value,upper=payload('합성 질문?',excerpts)
    assert json.loads(value['input'])['excerpts']==original==excerpts
    assert upper==len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())+1024
    excerpts[0]['title']='x'*14000
    original=deepcopy(excerpts)
    with pytest.raises(EmbeddingError,match='ANSWER_INPUT_LIMIT'):payload('합성 질문?',excerpts)
    assert excerpts==original
