"""Three fixed-context answer generations. No search, dialogue mutation or implicit approval."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import json
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User
from app.evaluation.c3_validation import code_hashes,check_source,corpus_metadata,ledger_rows,normalized
from app.evaluation.retrieval import database_identity
from app.evaluation.schemas import digest
from app.evaluation.storage import PRIVATE_ROOT,read_private
from app.services import answer_transport as at,conversation_context as context


class RecheckError(ValueError):
    pass


def hashes():
    result=code_hashes()
    path=Path(__file__).resolve().parents[2]/'tests/test_quote_recheck.py'
    import hashlib
    result['tests/test_quote_recheck.py']=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def seal(value):
    value['digest']=digest({k:v for k,v in value.items() if k!='digest'})
    return value


def validate(protocol,approval=None,*,dry_run=False):
    if seal(dict(protocol))!=protocol:raise RecheckError('QUOTE_PROTOCOL_CHANGED')
    if not dry_run and approval!=protocol['digest']:raise RecheckError('QUOTE_APPROVAL_REQUIRED')
    if protocol['version']!='quote-recheck-v1' or protocol['code_hashes']!=hashes():
        raise RecheckError('QUOTE_CODE_CHANGED')
    if protocol['configs']!=dict(answer=at.CONFIG_HASH,dialogue=at.DIALOGUE_CONFIG_HASH,price=at.PRICE_HASH):
        raise RecheckError('QUOTE_CONFIG_CHANGED')
    cases=protocol['cases']
    if [c['id'] for c in cases]!=['S1','R1','R2']:raise RecheckError('QUOTE_CASE_SCOPE')
    for case in cases:
        body=json.loads(case['request']['input'])
        expected,upper=at.payload(body['question'],body['excerpts'],dialogue=[])
        if (body.get('dialogue')!=[] or case['request']!=expected or upper!=case['input_upper'] or
                case['max_micro_usd']!=at.cost_micro(upper,4096) or
                bool(case['anchors'])!=(case['id']!='S1')):
            raise RecheckError('QUOTE_PAYLOAD_SCOPE')
    if protocol['call_limit']!=3 or protocol['max_micro_usd']!=sum(c['max_micro_usd'] for c in cases):
        raise RecheckError('QUOTE_ENVELOPE_CHANGED')
    if (protocol['billing']!=dict(scope=settings.embedding_billing_scope,
            monthly_limit=settings.embedding_monthly_limit_micro_usd) or settings.answer_mode!='off'):
        raise RecheckError('QUOTE_RUNTIME_CHANGED')
    for item in protocol['origins']:
        if digest(read_private(Path(item['path']),PRIVATE_ROOT))!=item['digest']:
            raise RecheckError('QUOTE_ORIGINAL_CHANGED')


@contextmanager
def source_guard(engine,protocol,case):
    # Hold the existing shared owner policy lock through I/O, release before billing settlement.
    # The first snapshot must follow lock acquisition: an in-flight policy update may hold the lock.
    with engine.connect().execution_options(isolation_level='READ COMMITTED',postgresql_readonly=True) as connection:
        with connection.begin(),Session(connection) as db:
            owner=protocol['scope']['owner_id']
            context.shared_lock(db,owner)
            if db.scalar(select(User.policy_revision).where(User.id==owner))!=protocol['scope']['policy_revision']:
                raise RecheckError('QUOTE_POLICY_CHANGED')
            if case['anchors']:
                context.validate(db,owner,case['anchors'])
                sources=[SimpleNamespace(**a,selection_order=i) for i,a in enumerate(case['anchors'])]
                if context.excerpts(db,owner,sources)!=json.loads(case['request']['input'])['excerpts']:
                    raise RecheckError('QUOTE_SOURCE_CHANGED')
            yield


def prepare(source,prior_path,capture_dir):
    prior=read_private(prior_path,PRIVATE_ROOT)
    if seal(dict(prior))!=prior:raise RecheckError('QUOTE_PRIOR_CHANGED')
    owner=prior['scope']['owner_id'];cases=[];origins=[]
    def origin(path):
        value=read_private(path,PRIVATE_ROOT)
        origins.append(dict(path=str(path.absolute()),digest=digest(value)))
        return value
    origin(prior_path)
    closed=origin(capture_dir/'closed.json')
    if closed.get('digest')!=prior['digest'] or closed.get('approval_closed') is not True or closed.get('resume_authorized') is not False:
        raise RecheckError('QUOTE_PRIOR_NOT_CLOSED')
    for name,number in [('S1','01'),('R1','03'),('R2','05')]:
        old=origin(capture_dir/f'{number}-answer-request.json')
        origin(capture_dir/f'{number}-answer-response.json')
        body=json.loads(old['payload']['input'])
        if body.get('dialogue',[]):raise RecheckError('QUOTE_UNSAFE_HISTORY')
        value,upper=at.payload(body['question'],body['excerpts'],dialogue=[])
        if json.loads(value['input'])!=body:raise RecheckError('QUOTE_CAPTURE_SHAPE')
        anchors=origin(capture_dir/f'{name}-evidence.json')['selected'] if name!='S1' else []
        cases.append(dict(id=name,request=value,input_upper=upper,max_micro_usd=at.cost_micro(upper,4096),anchors=anchors))
    with source.connect().execution_options(isolation_level='REPEATABLE READ',postgresql_readonly=True) as c:
        with c.begin(),Session(c) as db:
            revision=db.scalar(select(User.policy_revision).where(User.id==owner))
            if revision!=prior['scope']['policy_revision']:raise RecheckError('QUOTE_POLICY_CHANGED')
            old=ledger_rows(db)
            protocol=dict(version='quote-recheck-v1',state='prepared-not-authorized',
                scope=dict(owner_id=owner,policy_revision=revision,database=database_identity(db)),
                metadata=dict(rows=corpus_metadata(db,owner)),old_usage_ids=[r['id'] for r in old],
                old_usage_digest=digest(old),cases=cases,origins=origins,code_hashes=hashes(),
                configs=dict(answer=at.CONFIG_HASH,dialogue=at.DIALOGUE_CONFIG_HASH,price=at.PRICE_HASH),
                billing=dict(scope=settings.embedding_billing_scope,monthly_limit=settings.embedding_monthly_limit_micro_usd),
                call_limit=3,max_micro_usd=sum(c['max_micro_usd'] for c in cases))
    seal(protocol);validate(protocol,dry_run=True);check_source(source,protocol)
    for case in cases:
        with source_guard(source,protocol,case):pass
    return normalized(protocol)
