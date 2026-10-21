"""Synthetic quote-copy boundaries; these do not measure a model's compliance."""
from copy import deepcopy
import json
import pytest
from app.services import answer_transport as at


def response(facts):
    result=dict(parts=[dict(request='Recorded archive behavior',kind='answered',facts=facts)])
    return dict(model=at.MODEL,status='completed',output=[dict(type='message',content=[
        dict(type='output_text',text=json.dumps(dict(result=result)))])])


def fact(quote,text='The recorded setting is retained.'):
    return dict(text=text,evidence=[dict(id=1,quote=quote)])


@pytest.mark.parametrize('quote',[
    'The `draft` flag is **kept**.',
    'The setting  remains unchanged.',
    'First line.\nSecond line.',
    'The label is “archived”.',
    '설정 `임시`는 **유지**한다.',
])
def test_exact_formatting_survives_payload_json_and_quote_validation(quote):
    body='Synthetic preface.\n'+quote+'\nSynthetic suffix.'
    for dialogue in [None,[]]:
        value,_=at.payload('What setting was recorded?',[dict(id=1,text=body)],dialogue=dialogue)
        excerpts={e['id']:e['text'] for e in json.loads(value['input'])['excerpts']}
        assert excerpts[1]==body
        result=at.parse(response([fact(quote)]),{1},excerpts=excerpts)
        assert result['status']=='supported' and result['citation_ids']==[1]


@pytest.mark.parametrize('body,altered',[
    ('The `draft` flag is **kept**.','The draft flag is kept.'),
    ('The setting  remains unchanged.','The setting remains unchanged.'),
    ('First line.\nSecond line.','First line. Second line.'),
    ('The label is “archived”.','The label is "archived".'),
    ('설정은 유지한다.','The setting is retained.'),
    ('The flag is retained after review.','The flag ... after review.'),
])
def test_normalized_or_shortened_nonexact_quote_is_rejected_without_repair(body,altered):
    raw=response([fact(altered)]);before=deepcopy(raw)
    with pytest.raises(at.AnswerOutputError) as error:at.parse(raw,{1},excerpts={1:body})
    assert error.value.reason=='claim_evidence' and raw==before


def test_short_contiguous_quotes_from_long_source_support_separate_assertions():
    first='The `draft` flag is **kept**.'
    second='The archive count is reduced.'
    body='Synthetic context. '*20+first+' More context. '*10+second
    facts=[fact(first,'The draft flag is retained.'),fact(second,'The archive count is reduced.')]
    raw=response(facts);before=deepcopy(raw)
    result=at.parse(raw,{1},excerpts={1:body})
    assert result['answer']=='The draft flag is retained.\nThe archive count is reduced.'
    assert result['citation_ids']==[1] and raw==before


def test_quote_ceiling_remains_120_decoded_characters():
    quote='가'*119+'`'
    assert at.parse(response([fact(quote)]),{1},excerpts={1:quote})['status']=='supported'
    with pytest.raises(at.AnswerOutputError):
        at.parse(response([fact(quote+'나')]),{1},excerpts={1:quote+'나'})
