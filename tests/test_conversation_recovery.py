"""First response vs bounded recovery are independent; invalid output cannot be bypassed."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.evaluation.conversation_recovery import Assessment,RecoveryCase,RecoverySession


FIXTURE=json.loads(Path('tests/fixtures/conversation_recovery.json').read_text())


def session(*,synthetic=False):
    return RecoverySession(RecoveryCase.model_validate(FIXTURE['case']),synthetic=synthetic)


def review(verdict,**kw):
    return Assessment(verdict=verdict,reviewer='source-review',notes='Independent citation and scope review.',**kw)


def test_recovery_success_does_not_promote_the_first_response():
    s=session();s.start();s.record(review('partial'))
    f=s.next_followup();assert f.branch=='search'
    s.record(review('passed'));assert s.next_followup() is None
    r=s.report()
    assert r['first_response']['verdict']=='partial' and r['conversation_verdict']=='passed'
    assert r['followups_used']==1 and r['recovery_verdict']=='passed'


def test_good_first_response_spends_no_followup():
    s=session();s.start();s.record(review('passed'))
    assert s.next_followup() is None
    assert s.report()['followups_used']==0 and s.report()['recovery_verdict']=='not-needed'


def test_two_unsuccessful_followups_end_as_failure():
    s=session();s.start();s.record(review('partial'))
    for _ in range(2):
        assert s.next_followup() is not None
        s.record(review('partial'))
    assert s.next_followup() is None
    assert s.report()['conversation_verdict']=='failed' and s.report()['followups_used']==2


@pytest.mark.parametrize('field',['output_valid','safe'])
def test_invalid_output_or_unsafe_claims_block_recovery(field):
    s=session();s.start();s.record(review('failed',**{field:False}))
    assert s.next_followup() is None and s.report()['conversation_verdict']=='blocked'


def test_pending_review_never_authorizes_the_next_question():
    s=session()
    with pytest.raises(ValueError,match='REVIEW_REQUIRED'):s.next_followup()
    s.start()
    with pytest.raises(ValueError,match='REVIEW_REQUIRED'):s.next_followup()
    assert s.report()['conversation_verdict']=='not-reviewed'


def test_self_reported_model_status_is_not_an_assessment():
    with pytest.raises(ValueError):Assessment(verdict='passed',reviewer='model',notes='supported')
    s=session();s.start()
    with pytest.raises(ValueError,match='SOURCE_REVIEW_REQUIRED'):
        s.record(Assessment(verdict='passed',reviewer='synthetic-oracle',notes='Fixture only'))


@pytest.mark.parametrize('change',['answer_hint','third_question','blank'])
def test_unbounded_or_hint_bearing_plans_are_rejected(change):
    data=deepcopy(FIXTURE['case'])
    if change=='answer_hint':data['followups'][0]['question']='dry-commit-7e2c에 대해 알려줘.'
    if change=='third_question':data['followups'].append(data['followups'][0])
    if change=='blank':data['followups'][0]['question']=' '
    with pytest.raises(ValueError):RecoveryCase.model_validate(data)


def test_review_is_copied_and_cannot_be_replaced_by_later_success():
    s=session();s.start();r=review('failed');s.record(r);r.verdict='passed'
    assert s.report()['first_response']['verdict']=='failed'
    with pytest.raises(ValueError,match='REVIEW_ORDER'):s.record(review('passed'))


def test_envelope_includes_new_search_after_each_followup():
    e=session().case.envelope()
    assert e==dict(first_max_calls=2,followup_max_calls=6,first_max_micro_usd=8745,
        followup_max_micro_usd=23634,total_max_calls=8,total_max_micro_usd=32379)
