"""One approved selected-context pass; deferred cases never dispatch."""
from time import perf_counter
from app.evaluation.schemas import EvaluationError, digest, now
from app.evaluation.storage import write_private
from app.services.answer_transport import CONFIG_HASH
from app.services.embedding_store import STORAGE_CONFIG


def request_id(protocol, case_id):
    return digest(['phase33-answer-pass-v1', protocol['digest'], case_id])[:32]


def request_plan(protocol, spec, *, approval_digest):
    prepared = [c for c in protocol.get('cases', []) if c.get('selected') and not c.get('gaps')]
    if (protocol.get('schema') != 'lifhop-phase33-preflight-v1' or
            protocol.get('preparation_version') != 'evidence-drafts-v2' or
            digest({k:v for k,v in protocol.items() if k != 'digest'}) != protocol.get('digest') or
            approval_digest != protocol['digest'] or protocol.get('configuration_hash') != CONFIG_HASH or
            protocol.get('storage_configuration') != STORAGE_CONFIG or
            digest(spec.model_dump(mode='json')) != protocol.get('spec_digest') or
            [c['id'] for c in protocol.get('cases', [])] != [c.id for c in spec.cases] or
            [c['id'] for c in prepared] != protocol.get('prepared_answer_cases') or
            not 1 <= len(prepared) <= 6 or protocol.get('answer_call_limit') != len(prepared) or
            protocol.get('answer_max_micro_usd') != len(prepared)*10000 or
            protocol.get('budget', {}).get('remaining_micro_usd', 0) < len(prepared)*10000):
        raise EvaluationError('PHASE33_APPROVAL_INVALID')
    by_id = {c.id: c for c in spec.cases}
    plan = []
    for case in prepared:
        source = by_id[case['id']]
        if (case.get('deferred') or source.deferred_reason or
                digest(source.question) != case['question_digest'] or
                digest(source.checklist) != case['checklist_digest'] or
                source.expected_outcome != case['expected_outcome']):
            raise EvaluationError('PHASE33_INPUT_CHANGED')
        data = dict(request_id=request_id(protocol, case['id']), confirm_external_ai=True)
        if source.period or source.historical:
            scope = (source.period or source.historical).model_dump(mode='json')
            endpoint = '/retrospectives' if source.period else '/historical'
            if case.get('endpoint') != endpoint or scope != case.get('scope'):
                raise EvaluationError('PHASE33_INPUT_CHANGED')
            data.update(scope, preview_digest=case['coverage']['preview_digest'])
        else:
            endpoint = '/answers'
            ids = [p['passage_id'] for p in case['selected']]
            if case.get('endpoint') != endpoint or any(type(i) is not int or i <= 0 for i in ids) or len(ids) != len(set(ids)):
                raise EvaluationError('PHASE33_INPUT_CHANGED')
            data.update(q=source.question, passage_ids=ids, policy_revision=protocol['policy_revision'])
        plan.append(dict(id=case['id'], endpoint=endpoint, data=data, expected_outcome=source.expected_outcome))
    return plan


def run_pass(protocol, spec, *, approval_digest, client, output, root):
    plan = request_plan(protocol, spec, approval_digest=approval_digest)
    write_private(output / 'run-start.json', dict(protocol_digest=protocol['digest'],
        approved_at=now().isoformat(), request_ids={c['id']:c['data']['request_id'] for c in plan}), root=root)
    report = dict(protocol_digest=protocol['digest'], state='completed', cases=[],
        unsent_cases=[c['id'] for c in plan], uncertain_cases=[], grounding_review_complete=False,
        automatic_retrieval_evaluated=False, phase_exit=False)
    try:
        for case in plan:
            start = perf_counter()
            report['unsent_cases'].remove(case['id'])
            response = client.post(case['endpoint'], json=case['data'])
            seconds = perf_counter()-start
            body = response.json()
            write_private(output / (case['id'] + '.json'), dict(case_id=case['id'],
                http_status=response.status_code, seconds=seconds, response=body), root=root)
            result = body.get('answer', {}) if case['endpoint'] == '/retrospectives' else body
            status = result.get('status') if isinstance(result, dict) else None
            report['cases'].append(dict(id=case['id'], http_status=response.status_code,
                seconds=seconds, status=status, expected_outcome=case['expected_outcome'], error=body.get('detail')))
            if response.status_code != 200 or status != case['expected_outcome']:
                report['state'] = 'stopped_after_failure'
                break
    except BaseException:
        report['state'] = 'interrupted_requires_review'
        report['uncertain_cases'].append(case['id'])
        raise
    finally:
        write_private(output / 'report.json', report, root=root)
    return report
