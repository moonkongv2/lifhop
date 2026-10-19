"""Synthetic behavior of ordinary claim rendering, independent of model quality."""
from copy import deepcopy
import json
import pytest
from app.services.answer_transport import MODEL, AnswerOutputError, parse, payload, usage
from app.services.embedding_transport import EmbeddingError

BODIES = {11: 'The blue switch was selected. Testing is planned.',
          22: 'A related interface review was recorded.',
          33: 'The second requested fact was confirmed.'}


def result(kind='answer', complete=True):
    return dict(parts=[dict(id=1, text='The requested switch.', complete=complete)],
        claims=[dict(part=1, kind=kind, text='The blue switch was selected.',
            evidence=[dict(id=11, quote='The blue switch was selected.')])],
        unknowns=[] if complete else [dict(part=1, text='The final test result is unconfirmed in these records.')])


def raw(data):
    return dict(model=MODEL, status='completed', output=[dict(type='message',
        content=[dict(type='output_text', text=json.dumps(dict(result=data)))])])


def parsed(data):
    return parse(raw(data), set(BODIES), excerpts=BODIES, question='Which switch was selected?')


def test_answer_is_assembled_only_from_rendered_claims_and_unknowns():
    data=result(complete=False)
    data['claims'].append(dict(part=1,kind='background',text='The interface review was recorded.',
        evidence=[dict(id=22,quote='A related interface review was recorded.')]))
    answer=parsed(data)
    assert answer==dict(status='partial',answer='The blue switch was selected.\nThe final test result is unconfirmed in these records.',
        citation_ids=[11],unconfirmed_aspects=['The final test result is unconfirmed in these records.'])
    assert 'review' not in answer['answer'] and 'quote' not in answer


@pytest.mark.parametrize('kind',['answer','progress','limitation'])
def test_known_facts_or_progress_and_unknown_outcome_are_partial(kind):
    assert parsed(result(kind,False))['status']=='partial'


@pytest.mark.parametrize('background',[False,True])
def test_no_direct_evidence_is_insufficient_with_no_citations(background):
    data=result('background',False)
    if not background:data['claims']=[]
    answer=parsed(data)
    assert answer['status']=='insufficient' and answer['citation_ids']==[]
    assert answer['unconfirmed_aspects']==[] and 'selected' not in answer['answer']
    korean=parse(raw(data),set(BODIES),excerpts=BODIES,question='어떤 선택을 했어?')
    assert korean['answer']=='제공된 기록에서 질문에 답하는 사실·관련 진행·명시된 검증 한계를 확인하지 못했습니다.'


def test_distinct_citations_follow_rendered_claim_order_and_repeat_source_quotes_are_valid():
    data=result()
    data['claims'][0]['evidence'].append(dict(id=11,quote='Testing is planned.'))
    data['parts'].append(dict(id=2,text='A second fact.',complete=True))
    data['claims'].insert(0,dict(part=2,kind='answer',text='The second fact was confirmed.',
        evidence=[dict(id=33,quote='The second requested fact was confirmed.')]))
    answer=parsed(data)
    assert answer['status']=='supported' and answer['citation_ids']==[33,11]
    assert answer['answer']=='The second fact was confirmed.\nThe blue switch was selected.'


@pytest.mark.parametrize('change',[
    lambda d:d.update(extra=True),
    lambda d:d['parts'][0].update(id=True),
    lambda d:d['parts'][0].update(complete=1),
    lambda d:d['parts'][0].update(text=' '),
    lambda d:d['parts'].append(deepcopy(d['parts'][0])),
    lambda d:d['parts'].extend([dict(id=i,text='Extra.',complete=False) for i in [2,3,4]]),
    lambda d:d['claims'][0].update(part=True),
    lambda d:d['claims'][0].update(part=3),
    lambda d:d['claims'][0].update(kind='adoption'),
    lambda d:d['claims'][0].update(text='x'*151),
    lambda d:d['claims'][0].update(evidence=[]),
    lambda d:d['claims'][0]['evidence'][0].update(id=True),
    lambda d:d['claims'][0]['evidence'][0].update(id=99),
    lambda d:d['claims'][0]['evidence'][0].update(quote='the blue switch was selected.'),
    lambda d:d['claims'][0]['evidence'][0].update(quote='The blue  switch was selected.'),
    lambda d:d['claims'][0]['evidence'][0].update(quote=' '),
    lambda d:d['claims'][0]['evidence'][0].update(quote='x'*121),
    lambda d:d['claims'][0]['evidence'].append(deepcopy(d['claims'][0]['evidence'][0])),
    lambda d:d['claims'][0].update(kind='progress'),
    lambda d:d['claims'][0].update(kind='limitation'),
    lambda d:d['claims'][0].update(kind='background'),
    lambda d:d.update(claims=[]),
    lambda d:d['parts'][0].update(complete=False),
    lambda d:d['unknowns'].append(dict(part=1,text='An unknown outcome.')),
])
def test_invalid_claims_are_rejected_without_truncating_or_repairing(change):
    data=result()
    change(data)
    original=deepcopy(data)
    with pytest.raises(AnswerOutputError,match='ANSWER_OUTPUT_INVALID'):parsed(data)
    assert data==original


@pytest.mark.parametrize('change',[
    lambda d:d['unknowns'].append(deepcopy(d['unknowns'][0])),
    lambda d:d['unknowns'][0].update(part=True),
    lambda d:d['unknowns'][0].update(part=3),
    lambda d:d['unknowns'][0].update(text='x'*141),
    lambda d:d['unknowns'][0].update(text=' '),
])
def test_unknowns_are_bounded_and_unique_per_declared_part(change):
    data=result(complete=False)
    change(data)
    with pytest.raises(AnswerOutputError):parsed(data)


def test_reference_budget_applies_to_background_too():
    data=result(complete=False)
    data['claims']=[deepcopy(data['claims'][0]) for _ in range(5)]
    for item in data['claims']:
        item['evidence'].append(dict(id=22,quote='A related interface review was recorded.'))
    data['claims'][-1]['kind']='background'
    with pytest.raises(AnswerOutputError) as error:parsed(data)
    assert error.value.reason=='claim_evidence'


def test_maximum_fields_render_within_1328_characters():
    data=dict(parts=[dict(id=i,text='p'*80,complete=False) for i in range(1,4)],
        claims=[dict(part=i%3+1,kind='progress',text='x'*150,
            evidence=[dict(id=11,quote='The blue switch was selected.')]) for i in range(6)],
        unknowns=[dict(part=i,text='u'*140) for i in range(1,4)])
    assert len(parsed(data)['answer'])==1328


def test_narrative_is_not_accepted_by_current_mode_or_autodetected():
    legacy=dict(status='supported',answer='A legacy answer.',citation_ids=[11],unconfirmed_aspects=[])
    with pytest.raises(AnswerOutputError):parsed(legacy)
    assert parse(raw(legacy),set(BODIES),historical=True)==legacy
    with pytest.raises(AnswerOutputError):parse(raw(result()),set(BODIES),historical=True)
    with pytest.raises(AnswerOutputError):parse(raw(result()),set(BODIES))


def test_mode_limits_are_explicit_and_usage_uses_actual_request_bound():
    for options,limit in [({},4096),({'retrospective':True},512),({'historical_as_of':'2026-01-31'},512)]:
        value,_=payload('Synthetic question?',[dict(id=11,text=BODIES[11])],**options)
        assert value['max_output_tokens']==limit
        response=dict(model=MODEL,usage=dict(input_tokens=10,output_tokens=limit,total_tokens=limit+10))
        assert usage(response,100,output_limit=value['max_output_tokens'])==(10,limit)
        response['usage'].update(output_tokens=limit+1,total_tokens=limit+11)
        with pytest.raises(EmbeddingError,match='ANSWER_USAGE_INVALID'):usage(response,100,output_limit=limit)


def test_duplicate_source_identity_is_rejected_before_dispatch():
    with pytest.raises(EmbeddingError,match='ANSWER_INPUT_LIMIT'):
        payload('Synthetic question?',[dict(id=11,text='First body.'),dict(id=11,text='Different body.')])


def test_invalid_background_is_not_ignored_when_it_would_render_no_facts():
    data=result('background',False)
    data['claims'][0]['evidence'][0]['quote']='An invented quote.'
    with pytest.raises(AnswerOutputError):parsed(data)


def test_explicit_review_limitation_is_retained_with_scope_and_unknown_outcome():
    body='This review read the documents but did not run execution tests.'
    data=dict(parts=[dict(id=1,text='Whether deployment and verification succeeded.',complete=False)],
        claims=[dict(part=1,kind='limitation',
            text='The reviewer reported that this review did not run execution tests.',
            evidence=[dict(id=11,quote='did not run execution tests')])],
        unknowns=[dict(part=1,text='Deployment and post-deployment verification success are unconfirmed in these excerpts.')])
    answer=parse(raw(data),{11},excerpts={11:body},question='Did deployment succeed?')
    assert answer['status']=='partial' and answer['citation_ids']==[11]
    assert answer['answer']==data['claims'][0]['text']+'\n'+data['unknowns'][0]['text']
    assert 'deployment failed' not in answer['answer'].lower()


def test_explicit_nonexecution_can_answer_a_question_about_that_review():
    body='This review did not run execution tests.'
    data=dict(parts=[dict(id=1,text='Did this review run execution tests?',complete=True)],
        claims=[dict(part=1,kind='answer',text='This review did not run execution tests.',
            evidence=[dict(id=11,quote=body)])],unknowns=[])
    assert parse(raw(data),{11},excerpts={11:body},question='Did this review run tests?')['status']=='supported'


def test_exact_quote_does_not_prove_semantic_scope_or_claim_relevance():
    # The local validator cannot detect this model mistake. The frozen semantic
    # rubric must reject treating a scoped nonexecution as operational failure.
    data=result('limitation',False)
    data['claims'][0]['text']='The deployment failed everywhere.'
    assert parsed(data)['status']=='partial'


def test_new_limitation_kind_is_sent_only_in_ordinary_contract():
    for options,expected in [({},True),({'retrospective':True},False),({'historical_as_of':'2026-01-31'},False)]:
        request,_=payload('Synthetic question?',[dict(id=11,text=BODIES[11])],**options)
        schema=json.dumps(request['text']['format']['schema'])
        assert ('limitation' in schema)==expected
        if expected:
            assert 'Silence is not evidence of non-execution' in request['instructions']
            assert 'not operational failure or non-execution elsewhere' in request['instructions']
