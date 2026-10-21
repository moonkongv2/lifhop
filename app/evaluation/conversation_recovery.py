"""Bounded, externally reviewed recovery. Later success never rewrites the first result."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class Followup(BaseModel):
    model_config=ConfigDict(extra='forbid')
    question:str=Field(min_length=1,max_length=256)
    branch:Literal['search','reuse']


class RecoveryCase(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(min_length=1,max_length=80)
    initial_question:str=Field(min_length=1,max_length=256)
    followups:list[Followup]=Field(min_length=1,max_length=2)
    # These are local guard data, never answer hints sent to a provider.
    forbidden_hints:list[str]=Field(default_factory=list)

    @model_validator(mode='after')
    def natural_questions(self):
        questions=[self.initial_question,*[f.question for f in self.followups]]
        if any(not q.strip() or len(q.encode())>2048 for q in questions):
            raise ValueError('RECOVERY_QUESTION_LIMIT')
        if any(not h.strip() for h in self.forbidden_hints):
            raise ValueError('RECOVERY_HINT_INVALID')
        if any(h.casefold() in f.question.casefold() for h in self.forbidden_hints for f in self.followups):
            raise ValueError('RECOVERY_ANSWER_HINT')
        return self

    def envelope(self):
        # Conservative current profiles. Reused history/price changes are not authorized here.
        from app.services import answer_transport as at,followup_transport as ft,embedding_transport as et
        first=at.cost_micro(66560,4096)+et.cost_micro(2048)
        followups=[ft.cost_micro(25600,1024)+at.cost_micro(66560,4096)+
            (et.cost_micro(2048) if f.branch=='search' else 0) for f in self.followups]
        return dict(first_max_calls=2,followup_max_calls=sum(3 if f.branch=='search' else 2 for f in self.followups),
            first_max_micro_usd=first,followup_max_micro_usd=sum(followups),
            total_max_calls=2+sum(3 if f.branch=='search' else 2 for f in self.followups),
            total_max_micro_usd=first+sum(followups))


class Assessment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    verdict:Literal['passed','partial','failed']
    reviewer:Literal['source-review','synthetic-oracle']
    output_valid:bool=True
    safe:bool=True
    notes:str=Field(min_length=1,max_length=2000)

    @model_validator(mode='after')
    def valid_success(self):
        if self.verdict=='passed' and (not self.output_valid or not self.safe):
            raise ValueError('RECOVERY_UNSAFE_SUCCESS')
        return self


class RecoverySession:
    def __init__(self,case:RecoveryCase,*,synthetic=False):
        self.case=case.model_copy(deep=True);self.synthetic=synthetic
        self.questions=[];self.reviews=[]

    def start(self):
        if self.questions:raise ValueError('RECOVERY_ALREADY_STARTED')
        self.questions.append(self.case.initial_question)
        return self.questions[-1]

    def record(self,review:Assessment):
        if len(self.reviews)!=len(self.questions)-1:
            raise ValueError('RECOVERY_REVIEW_ORDER')
        if not self.synthetic and review.reviewer!='source-review':
            raise ValueError('RECOVERY_SOURCE_REVIEW_REQUIRED')
        self.reviews.append(review.model_copy(deep=True))

    def next_followup(self):
        if not self.questions or len(self.reviews)!=len(self.questions):
            raise ValueError('RECOVERY_REVIEW_REQUIRED')
        previous=self.reviews[-1]
        if not previous.output_valid or not previous.safe or previous.verdict=='passed':return None
        used=len(self.questions)-1
        if used==len(self.case.followups):return None
        followup=self.case.followups[used].model_copy(deep=True)
        self.questions.append(followup.question)
        return followup

    def report(self):
        pending=len(self.reviews)!=len(self.questions) or not self.reviews
        blocked=any(not r.safe or not r.output_valid for r in self.reviews)
        if pending:conversation='not-reviewed'
        elif blocked:conversation='blocked'
        elif self.reviews[-1].verdict=='passed':conversation='passed'
        elif len(self.questions)-1==len(self.case.followups):conversation='failed'
        else:conversation='in-progress'
        return dict(case_id=self.case.id,mode='synthetic' if self.synthetic else 'source-reviewed',
            first_response=self.reviews[0].model_dump() if self.reviews else None,
            followups_used=max(0,len(self.questions)-1),followup_limit=len(self.case.followups),
            followup_reviews=[r.model_dump() for r in self.reviews[1:]],
            conversation_verdict=conversation,
            recovery_verdict=('not-needed' if conversation=='passed' and len(self.questions)==1 else
                conversation),semantic_quality='not-evaluated' if self.synthetic else 'externally-reviewed',
            envelope=self.case.envelope())
