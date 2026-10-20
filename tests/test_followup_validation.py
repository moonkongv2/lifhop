"""Offline proposal arithmetic/immutability, not semantic-quality assertions."""
from importlib.util import module_from_spec, spec_from_file_location
import pytest

spec=spec_from_file_location('followup_validation_prepare','scripts/prepare_followup_validation.py')
module=module_from_spec(spec)
spec.loader.exec_module(module)
prepare=module.prepare


def test_proposal_scope_and_conservative_cost_are_explicit():
    proposal=prepare()
    assert proposal['status']=='prepared-not-authorized'
    assert proposal['max_calls']==dict(document=1,planner=6,query=4,answer=7)
    assert proposal['max_total_calls']==18
    assert proposal['max_micro_usd']==79537
    assert proposal['document_max_micro_usd']==13
    assert proposal['retries']==proposal['personal_records']==proposal['personal_policy_changes']==0
    assert len(proposal['corpus'])==3 and len(proposal['turns'])==8
    assert len(proposal['digest'])==64
    assert prepare()==proposal


def test_quality_recheck_preserves_originals_and_questions_with_tighter_scope():
    full=prepare()
    quality=prepare('quality')
    assert quality['version']=='followup-quality-recheck-v1'
    assert quality['status']=='prepared-not-authorized'
    assert quality['corpus']==full['corpus'] and quality['fixture_sha256']==full['fixture_sha256']
    assert [t['id'] for t in quality['turns']]==['T1','T5','T8']
    for t in quality['turns']:
        original=next(o for o in full['turns'] if o['id']==t['id'])
        assert {k:v for k,v in t.items() if k!='expected'}=={k:v for k,v in original.items() if k!='expected'}
    assert quality['max_calls']==dict(document=1,planner=1,query=2,answer=3)
    assert quality['max_total_calls']==quality['billing']['max_new_rows']==7
    assert quality['max_micro_usd']==29279
    assert quality['retries']==quality['personal_records']==quality['personal_policy_changes']==0
    assert quality['digest']!=full['digest'] and prepare('quality')==quality
    assert 'tests/fixtures/followup_quality_recheck.json' in quality['code_hashes']


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):prepare('custom')
