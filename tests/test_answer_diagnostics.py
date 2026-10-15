"""Local synthetic reproductions; no real provider response is reconstructed."""
import json
import pytest
from app.services.answer_transport import MODEL, SCHEMA, parse
from app.services.embedding_transport import EmbeddingError


def output(data):
    return dict(model=MODEL, status="completed", output=[dict(type="message",
        content=[dict(type="output_text", text=json.dumps(data))])])


@pytest.mark.parametrize("data", [
    dict(status="insufficient", answer="Evidence is missing.", citation_ids=[4]),
    dict(status="supported", answer="Synthetic answer.", citation_ids=[]),
    dict(status="supported", answer="Synthetic answer.", citation_ids=[99]),
    dict(status="supported", answer="Synthetic answer.", citation_ids=[4, 4]),
    dict(status="supported", answer="", citation_ids=[4]),
    dict(status="supported", answer="x"*1501, citation_ids=[4]),
])
def test_schema_shaped_outputs_can_fail_application_contract(data):
    # These values satisfy every constraint in the current transmitted schema.
    assert SCHEMA["additionalProperties"] is False
    assert set(data) == set(SCHEMA["required"]) == set(SCHEMA["properties"])
    assert SCHEMA["properties"]["status"] == dict(type="string", enum=["supported", "insufficient"])
    assert data["status"] in SCHEMA["properties"]["status"]["enum"]
    assert SCHEMA["properties"]["answer"] == dict(type="string")
    assert isinstance(data["answer"], str)
    assert SCHEMA["properties"]["citation_ids"] == dict(type="array", items=dict(type="integer"))
    assert all(type(i) is int for i in data["citation_ids"])
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
