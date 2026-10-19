"""Pure offline capacity checks: no DB fixture, provider or personal records."""
from copy import deepcopy
import json
from app.evaluation.answer_contract_capacity import (
    byte_size, candidate_request, output_assessment, synthetic_outputs)


def test_candidate_preserves_complete_input_and_all_other_request_controls():
    old = dict(model='gpt-6-luna', max_output_tokens=512, instructions='Old instructions',
        input=json.dumps(dict(question='Synthetic?', excerpts=[dict(id=5, text='🙂'*2000,
            title='Synthetic source', source='manual')]), ensure_ascii=False),
        text=dict(format=dict(type='json_schema', strict=True, name='old', schema={})))
    original = deepcopy(old)
    new = candidate_request(old)
    assert old == original and new['input'] == old['input']
    assert {k:v for k,v in new.items() if k not in ['instructions','text']} == {
        k:v for k,v in old.items() if k not in ['instructions','text']}
    assert new['text']['format']['strict'] is True
    assert byte_size(new) == len(json.dumps(new, ensure_ascii=False, separators=(',', ':')).encode())


def test_unmapped_diagnostic_token_count_cannot_pass_output_gate():
    report = output_assessment(synthetic_outputs(), diagnostic_counter=lambda raw: 1,
        diagnostic_encoding='synthetic-non-target')
    assert not report['passed'] and report['target_tokenizer_mapping'] is None


def test_maximum_example_exercises_joint_bounds_and_render_length():
    value = synthetic_outputs()['maximum_fields']['result']
    assert len(value['parts']) == 3 and all(len(x['text'])==80 for x in value['parts'])
    assert len(value['claims'])==6 and sum(len(x['evidence']) for x in value['claims'])==8
    assert all(len(x['text'])==150 for x in value['claims'])
    assert all(len(e['quote'])==120 for x in value['claims'] for e in x['evidence'])
    assert len(value['unknowns'])==3 and all(len(x['text'])==140 for x in value['unknowns'])
    rendered='\n'.join([x['text'] for x in value['claims']]+[x['text'] for x in value['unknowns']])
    assert len(rendered)==1328
