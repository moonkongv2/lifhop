"""Local synthetic reproductions; no real provider response is reconstructed."""
import json
import pytest
from app.services.answer_transport import MODEL, INSTRUCTIONS, AnswerOutputError, parse
from app.services.embedding_transport import EmbeddingError


def output(data):
    return dict(model=MODEL, status="completed", output=[dict(type="message",
        content=[dict(type="output_text", text=json.dumps(dict(result=data)))])])


@pytest.mark.parametrize("data", [
    dict(status="insufficient", answer="Evidence is missing.", citation_ids=[4]),
    dict(status="supported", answer="Synthetic answer.", citation_ids=[]),
    dict(status="supported", answer="Synthetic answer.", citation_ids=[99]),
    dict(status="supported", answer="Synthetic answer.", citation_ids=[4, 4]),
    dict(status="supported", answer="", citation_ids=[4]),
    dict(status="supported", answer="x"*1501, citation_ids=[4]),
])
def test_invalid_citation_and_length_contracts(data):
    with pytest.raises(EmbeddingError, match="ANSWER_OUTPUT_INVALID"):
        parse(output(data), {4})


@pytest.mark.parametrize("data", [
    dict(status="insufficient", answer="Evidence is missing.", citation_ids=[]),
    dict(status="supported", answer="Synthetic answer.", citation_ids=[4]),
])
def test_valid_supported_and_insufficient_contracts(data):
    assert parse(output(data), {4}) == data


@pytest.mark.parametrize("kind", ["incomplete", "refusal", "invalid_json"])
def test_other_output_failure_paths(kind):
    raw = output(dict(status="insufficient", answer="Evidence is missing.", citation_ids=[]))
    if kind == "incomplete":
        raw["status"] = "incomplete"
    elif kind == "refusal":
        raw["output"][0]["content"] = [dict(type="refusal", refusal="Synthetic refusal.")]
    else:
        raw["output"][0]["content"][0]["text"] = "{"
    with pytest.raises(EmbeddingError, match="ANSWER_OUTPUT_INVALID"):
        parse(raw, {4})


@pytest.mark.parametrize("raw,reason", [
    (None, "response_shape"),
    (dict(model=MODEL,status="incomplete"), "response_status"),
    (dict(model=MODEL,status="completed",output=[None]), "response_shape"),
    (output([1]), "json_shape"),
    (output(dict(status="supported",answer="ok",citation_ids=[True])), "citation_type"),
    (output(dict(status="supported",answer="ok",citation_ids=[4,4])), "duplicate_citation"),
    (output(dict(status="supported",answer="ok",citation_ids=[99])), "unknown_citation"),
    (output(dict(status="supported",answer="ok",citation_ids=[])), "status_citation_mismatch"),
    (output(dict(status="supported",answer="",citation_ids=[4])), "answer_length"),
])
def test_rejection_reason_is_bounded_and_public_code_stays_compatible(raw, reason):
    with pytest.raises(AnswerOutputError) as error:
        parse(raw, {4})
    assert str(error.value) == "ANSWER_OUTPUT_INVALID"
    assert error.value.reason == reason


def test_prompt_explicitly_explains_status_and_length_contract():
    assert "citation_ids to an empty list" in INSTRUCTIONS
    assert "distinct integer IDs" in INSTRUCTIONS and "1500 characters" in INSTRUCTIONS


def test_transmitted_schema_couples_status_to_citation_count():
    from app.services.answer_transport import payload
    value,_=payload('Synthetic question?', [dict(id=4,text='Synthetic evidence')])
    format=value['text']['format']
    assert format['strict'] is True
    schema=format['schema']
    assert schema['type']=='object' and 'anyOf' not in schema
    assert schema['required']==['result'] and schema['additionalProperties'] is False
    branches=schema['properties']['result']['anyOf']
    assert len(branches)==2
    by_status={b['properties']['status']['enum'][0]:b for b in branches}
    for branch in branches:
        assert branch['additionalProperties'] is False
        assert set(branch['required'])=={'status','answer','citation_ids'}
    supported=by_status['supported']['properties']['citation_ids']
    insufficient=by_status['insufficient']['properties']['citation_ids']
    assert supported['minItems']==1 and supported['maxItems']==5
    assert insufficient['maxItems']==0


@pytest.mark.parametrize('data', [
    dict(status='insufficient',answer='Synthetic missing evidence.',citation_ids=[]),
    dict(result=None),
    dict(result=dict(status='insufficient',answer='Missing.',citation_ids=[]),extra='unexpected'),
])
def test_legacy_or_malformed_result_wrappers_are_rejected(data):
    raw=output(None)
    raw['output'][0]['content'][0]['text']=json.dumps(data)
    with pytest.raises(AnswerOutputError) as error:
        parse(raw,{4})
    assert error.value.reason=='json_shape'


def test_luna_payload_preserves_bounded_nonreasoning_uncached_role():
    from app.services.answer_transport import payload, cost_micro, CONFIG_HASH
    from app.evaluation.schemas import digest
    value,_=payload('Synthetic question?', [dict(id=4,text='Synthetic evidence')])
    assert value['model']=='gpt-6-luna'
    assert value['reasoning']==dict(effort='none')
    assert value['prompt_cache_options']==dict(mode='explicit')
    assert value['temperature']==0 and value['store'] is False
    assert value['max_output_tokens']==512
    assert 'prompt_cache_breakpoint' not in json.dumps(value)
    assert cost_micro(1000,100)==150
    assert CONFIG_HASH != digest(dict(model='gpt-4.1-mini-2025-04-14'))


@pytest.mark.parametrize('details', [dict(cached_tokens=2), dict(cache_write_tokens=1), None])
def test_unexpected_cache_accounting_is_not_silently_undercharged(details):
    from app.services.answer_transport import usage
    raw=dict(model=MODEL,usage=dict(input_tokens=10,output_tokens=2,total_tokens=12,
        input_tokens_details=details))
    with pytest.raises(EmbeddingError,match='ANSWER_USAGE_INVALID'):
        usage(raw,100)
