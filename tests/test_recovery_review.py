"""Capture binding and complete independent review precede any recovery protocol."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.evaluation.recovery_review import FirstResponseReview,capture_digest,review_capture
from app.services import answer_transport as at


def inputs():
    case=json.loads(Path('tests/fixtures/conversation_recovery.json').read_text())['case']
    text='Deleting a note keeps attachments.'
    request=dict(payload=dict(input=json.dumps(dict(question=case['initial_question'],
        excerpts=[dict(id=1,text=text)]))))
    result=dict(parts=[dict(request='Policy and implementation',kind='unresolved',
        known=[dict(text=text,evidence=[dict(id=1,quote=text)])],
        gap='The implementation commit is not established in these excerpts.')])
    response=dict(raw=dict(model=at.MODEL,status='completed',output=[dict(type='message',
        content=[dict(type='output_text',text=json.dumps(dict(result=result)))])]))
    review=dict(case=case,request_digest=capture_digest(request),response_digest=capture_digest(response),
        assessment=dict(verdict='partial',reviewer='source-review',notes='Policy supported; implementation missing.'),
        claims=[dict(path='parts/0/unresolved/0',text=text,verdict='supported',notes='Exact supporting quote.')])
    return request,response,review


def run(request,response,review):
    return review_capture(request,response,FirstResponseReview.model_validate(review))


def test_safe_partial_is_eligible_but_never_authorized():
    req,res,review=inputs();before=deepcopy((req,res,review))
    report=run(req,res,review)
    assert report['eligible_for_protocol'] and report['authorization']=='none'
    assert report['first_response']['verdict']=='partial' and report['followups_used']==0
    assert (req,res,review)==before


@pytest.mark.parametrize('capture',['request','response'])
def test_changed_captures_cannot_reuse_a_review(capture):
    req,res,review=inputs()
    (req if capture=='request' else res)['changed']=True
    with pytest.raises(ValueError,match='CAPTURE_CHANGED'):run(req,res,review)


@pytest.mark.parametrize('change',['missing','duplicate','different_text'])
def test_each_claim_requires_a_matching_review(change):
    req,res,review=inputs()
    if change=='missing':review['claims']=[]
    elif change=='duplicate':review['claims']*=2
    else:review['claims'][0]['text']='A different assertion.'
    with pytest.raises(ValueError,match='CLAIM_REVIEW_INCOMPLETE'):run(req,res,review)


def test_unsupported_clause_overrides_an_optimistic_overall_review():
    req,res,review=inputs();review['claims'][0]['verdict']='unsupported'
    review['assessment']['verdict']='passed'
    report=run(req,res,review)
    assert not report['eligible_for_protocol'] and report['conversation_verdict']=='blocked'
    assert report['first_response']['safe'] is False


def test_nonexact_quote_blocks_even_with_positive_source_review():
    req,res,review=inputs()
    result=json.loads(res['raw']['output'][0]['content'][0]['text'])
    result['result']['parts'][0]['known'][0]['evidence'][0]['quote']='Invented quote.'
    res['raw']['output'][0]['content'][0]['text']=json.dumps(result)
    review['response_digest']=capture_digest(res)
    report=run(req,res,review)
    assert report['validation_error']=='claim_evidence'
    assert report['conversation_verdict']=='blocked' and not report['first_response']['output_valid']


def test_first_success_needs_no_recovery():
    req,res,review=inputs();review['assessment']['verdict']='passed'
    report=run(req,res,review)
    assert not report['eligible_for_protocol'] and report['recovery_verdict']=='not-needed'


def test_synthetic_oracle_cannot_review_personal_captures():
    req,res,review=inputs();review['assessment']['reviewer']='synthetic-oracle'
    with pytest.raises(ValueError,match='SOURCE_REVIEW_REQUIRED'):run(req,res,review)
