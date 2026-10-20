"""Offline proposal arithmetic/immutability, not semantic-quality assertions."""
from importlib.util import module_from_spec, spec_from_file_location

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
