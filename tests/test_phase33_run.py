"""Selected-context execution uses product APIs once, with mocks and real ledger."""
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.evaluation.phase33_preflight import AcceptanceSpec, prepare_acceptance
from app.evaluation.phase33_run import request_plan, run_pass
from app.evaluation.schemas import EvaluationError, digest
from app.evaluation.storage import read_private
from app.models.ai_usage import AiUsageAttempt
from app.models.entry import Entry
from test_answers import answer_client, response
from test_embedding_jobs import actor
from test_phase33_preflight import inputs, seed


def prepared(bind, owner, config):
    with Session(bind) as db:
        user = SimpleNamespace(id=owner)
        seed(db, user)
        db.commit()
        snapshot, spec, _ = inputs(db, user)
        raw = spec.model_dump(mode='json')
        raw['cases'][0]['deferred_reason'] = 'Missing cross-source proof.'
        raw['cases'][1]['deferred_reason'] = 'Missing change reason.'
        raw['cases'][2].update(expected_outcome='insufficient', query='worker', filters=dict(source='codex'))
        raw['cases'][5]['question'] = 'missing-proof: is deployment established?'
        spec = AcceptanceSpec.model_validate(raw)
        protocol, _ = prepare_acceptance(snapshot, spec, config)
    return protocol, spec


def test_four_routes_are_bounded_settled_and_never_replayed(answer_client, actor, tmp_path):
    client, headers, sender, _, bind, owner, _ = answer_client
    protocol, spec = prepared(bind, owner, actor[1])
    plan = request_plan(protocol, spec, approval_digest=protocol['digest'])
    assert [c['endpoint'] for c in plan] == ['/answers', '/retrospectives', '/historical', '/answers']
    def provider(value):
        inputs = json.loads(value['input'])
        if 'rental' in inputs['question'].lower() or 'missing-proof' in inputs['question']:
            return response(value, status='insufficient')
        raw = response(value)
        if 'newline-separated items' in value['instructions']:
            excerpts = inputs['excerpts']
            raw['output'][0]['content'][0]['text'] = json.dumps(dict(result=dict(status='supported',
                answer='\n'.join(f'[{x["id"]}] Recorded activity: Synthetic recorded statement.' for x in excerpts),
                citation_ids=[x['id'] for x in excerpts])))
        return raw
    sender.side_effect = provider
    client.headers.update(headers)
    report = run_pass(protocol, spec, approval_digest=protocol['digest'], client=client, output=tmp_path, root=tmp_path)
    assert report['state'] == 'completed' and report['unsent_cases'] == report['uncertain_cases'] == []
    assert report['phase_exit'] is False and report['grounding_review_complete'] is False
    assert sender.call_count == 4
    with Session(bind) as db:
        rows = list(db.scalars(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner, AiUsageAttempt.purpose == 'answer')))
        assert len(rows) == 4 and all(r.status == 'spent' for r in rows)
        assert sum(r.spent_micro_usd for r in rows) <= protocol['answer_max_micro_usd']
    with pytest.raises(EvaluationError, match='OUTPUT_EXISTS'):
        run_pass(protocol, spec, approval_digest=protocol['digest'], client=client, output=tmp_path, root=tmp_path)
    assert sender.call_count == 4


@pytest.mark.parametrize('change', ['approval', 'spec', 'config', 'budget', 'count', 'order'])
def test_invalid_plan_never_posts(actor, tmp_path, change):
    bind, config, owner, _ = actor
    protocol, spec = prepared(bind, owner, config)
    approval = protocol['digest']
    if change == 'approval': approval = 'wrong'
    elif change == 'spec': spec.cases[2].question = 'Changed question'
    else:
        if change == 'config': protocol['configuration_hash'] = 'old'
        elif change == 'budget': protocol['budget']['remaining_micro_usd'] = 0
        elif change == 'count': protocol['answer_call_limit'] = 6
        else: protocol['cases'].reverse()
        protocol.pop('digest'); protocol['digest'] = digest(protocol); approval = protocol['digest']
    client = Mock()
    with pytest.raises(EvaluationError, match='PHASE33_APPROVAL_INVALID'):
        run_pass(protocol, spec, approval_digest=approval, client=client, output=tmp_path, root=tmp_path)
    client.post.assert_not_called()
    assert not (tmp_path / 'run-start.json').exists()


def test_http_failure_stops_and_crash_is_uncertain_without_retry(actor, tmp_path):
    bind, config, owner, _ = actor
    protocol, spec = prepared(bind, owner, config)
    client = Mock()
    client.post.return_value = SimpleNamespace(status_code=503, json=lambda:dict(detail='ANSWER_OUTPUT_INVALID'))
    report = run_pass(protocol, spec, approval_digest=protocol['digest'], client=client, output=tmp_path/'failed', root=tmp_path)
    assert report['state'] == 'stopped_after_failure' and len(report['unsent_cases']) == 3
    assert client.post.call_count == 1
    client.reset_mock()
    client.post.side_effect = RuntimeError('synthetic interrupted request')
    with pytest.raises(RuntimeError):
        run_pass(protocol, spec, approval_digest=protocol['digest'], client=client, output=tmp_path/'crashed', root=tmp_path)
    saved = read_private(tmp_path/'crashed'/'report.json', tmp_path)
    assert saved['uncertain_cases'] == ['ordinary-life'] and len(saved['unsent_cases']) == 3
    with pytest.raises(EvaluationError, match='OUTPUT_EXISTS'):
        run_pass(protocol, spec, approval_digest=protocol['digest'], client=client, output=tmp_path/'crashed', root=tmp_path)
    assert client.post.call_count == 1


def test_partial_selected_pass_runs_once_without_sending_expectations(answer_client, actor, tmp_path):
    client, headers, sender, _, bind, owner, _ = answer_client
    _, spec = prepared(bind, owner, actor[1])
    raw = spec.model_dump(mode='json')
    raw['cases'][2].update(expected_outcome='partial', unconfirmed_aspects=['PRIVATE-EXPECTED-UNKNOWN'])
    for c in raw['cases'][3:]:
        c['deferred_reason'] = 'Other cases are outside this synthetic test.'
    spec = AcceptanceSpec.model_validate(raw)
    with Session(bind) as db:
        snapshot, _, _ = inputs(db, SimpleNamespace(id=owner))
        protocol, _ = prepare_acceptance(snapshot, spec, actor[1])
    plan = request_plan(protocol, spec, approval_digest=protocol['digest'])
    assert len(plan) == 1 and plan[0]['expected_outcome'] == 'partial'
    assert 'PRIVATE-EXPECTED-UNKNOWN' not in json.dumps(plan[0]['data'])
    sender.side_effect = lambda value: response(value, status='partial')
    client.headers.update(headers)
    report = run_pass(protocol, spec, approval_digest=protocol['digest'], client=client, output=tmp_path, root=tmp_path)
    assert report['state'] == 'completed' and report['cases'][0]['status'] == 'partial'
    assert report['phase_exit'] is False and report['grounding_review_complete'] is False
    assert 'PRIVATE-EXPECTED-UNKNOWN' not in json.dumps(sender.call_args.args[0])
    assert sender.call_count == 1
    with pytest.raises(EvaluationError, match='OUTPUT_EXISTS'):
        run_pass(protocol, spec, approval_digest=protocol['digest'], client=client, output=tmp_path, root=tmp_path)
    assert sender.call_count == 1


@pytest.mark.parametrize('change', ['old_preparation', 'unknowns'])
def test_partial_scope_or_preparation_change_rejects_old_approval(actor, change):
    bind, config, owner, _ = actor
    protocol, spec = prepared(bind, owner, config)
    if change == 'old_preparation':
        protocol['preparation_version'] = 'evidence-drafts-v2'
    else:
        protocol['cases'][2]['unconfirmed_aspects_digest'] = digest(['Unreviewed unknown'])
    protocol.pop('digest'); protocol['digest'] = digest(protocol)
    with pytest.raises(EvaluationError, match='PHASE33_APPROVAL_INVALID|PHASE33_INPUT_CHANGED'):
        request_plan(protocol, spec, approval_digest=protocol['digest'])
