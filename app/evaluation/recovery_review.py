"""Offline eligibility review of immutable captured first responses; no dispatch authority."""
import hashlib
import json
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from app.evaluation.conversation_recovery import Assessment,RecoveryCase,RecoverySession
from app.services import answer_transport as at


def capture_digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode()).hexdigest()


class ClaimReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    path:str
    text:str=Field(min_length=1)
    verdict:Literal['supported','unsupported']
    notes:str=Field(min_length=1,max_length=2000)


class FirstResponseReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    case:RecoveryCase
    request_digest:str=Field(pattern=r'^[a-f0-9]{64}$')
    response_digest:str=Field(pattern=r'^[a-f0-9]{64}$')
    assessment:Assessment
    claims:list[ClaimReview]


def review_capture(request,response,review:FirstResponseReview):
    # A changed input needs a new review, never a recycled verdict.
    if capture_digest(request)!=review.request_digest or capture_digest(response)!=review.response_digest:
        raise ValueError('RECOVERY_CAPTURE_CHANGED')
    if review.assessment.reviewer!='source-review':raise ValueError('RECOVERY_SOURCE_REVIEW_REQUIRED')
    body=json.loads(request['payload']['input'])
    if body['question']!=review.case.initial_question:raise ValueError('RECOVERY_QUESTION_SCOPE')
    excerpts={e['id']:e['text'] for e in body['excerpts']}
    if len(excerpts)!=len(body['excerpts']):raise ValueError('RECOVERY_DUPLICATE_EXCERPT')
    validation_error=None
    try:
        at.parse(response['raw'],set(excerpts),excerpts=excerpts,question=body['question'])
    except at.AnswerOutputError as error:
        validation_error=error.reason
    assessment=review.assessment.model_copy(deep=True)
    if validation_error:
        assessment=Assessment(verdict='failed',reviewer='source-review',output_valid=False,
            safe=assessment.safe,notes=assessment.notes)
    else:
        message=next(x for x in response['raw']['output'] if x.get('type')=='message')
        data=json.loads(message['content'][0]['text'])['result']
        expected={f'parts/{i}/{part["kind"]}/{j}':fact['text']
            for i,part in enumerate(data['parts'])
            for j,fact in enumerate(part.get('facts',part.get('known',[])))}
        actual={r.path:r.text for r in review.claims}
        if len(actual)!=len(review.claims) or actual!=expected:
            raise ValueError('RECOVERY_CLAIM_REVIEW_INCOMPLETE')
        if any(r.verdict=='unsupported' for r in review.claims):
            assessment=Assessment(verdict='failed',reviewer='source-review',safe=False,
                output_valid=True,notes=assessment.notes)
    session=RecoverySession(review.case);session.start();session.record(assessment)
    report=session.report()
    report.update(request_digest=review.request_digest,response_digest=review.response_digest,
        review_digest=capture_digest(review.model_dump(mode='json')),validation_error=validation_error,
        original_assessment=review.assessment.model_dump(mode='json'),
        eligible_for_protocol=(report['conversation_verdict']=='in-progress'),
        authorization='none',provider_calls=0,personal_db_reads=0,personal_db_writes=0)
    return report
