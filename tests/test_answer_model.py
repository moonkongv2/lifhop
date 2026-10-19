"""Synthetic Sol/Luna ledger isolation, no provider or personal corpus access."""
import json
from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.evaluation.answer_model import frozen_model_request, PROFILES
from app.models.ai_usage import AiUsageAttempt
from app.models.passage_embedding import PassageEmbedding
from app.services import answer_transport as transport
from app.services.answer_context import current_excerpt
from app.services.passage_search import read_passage
from test_answers import answer_client, response
from test_embedding_jobs import actor


@pytest.mark.parametrize('model', list(PROFILES))
def test_frozen_model_prices_reservation_and_settlement_and_restores_defaults(answer_client, model):
    client, headers, sender, vector_id, bind, owner, _ = answer_client
    original = (transport.MODEL, transport.CONFIG_HASH, transport.INPUT_PRICE, transport.OUTPUT_PRICE)
    with Session(bind) as db:
        p = read_passage(db, owner, db.get(PassageEmbedding, vector_id).passage_id)
    value, _ = transport.payload('Synthetic question?', [current_excerpt(p)])
    value['model'] = model
    upper = len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()) + 1024
    a, b = PROFILES[model]
    maximum = (upper*a + value["max_output_tokens"]*b + 999999)//1000000
    def synthetic(sent):
        assert sent == value
        raw = response(sent)
        raw['model'] = model
        return raw
    sender.side_effect = synthetic
    with frozen_model_request(value, maximum):
        configured = transport.CONFIG_HASH
        result = client.post('/answers', headers=headers, json=dict(q='Synthetic question?',
            passage_ids=[p.id], request_id=uuid4().hex, confirm_external_ai=True))
        assert result.status_code == 200, result.text
    with Session(bind) as db:
        row = db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner))
        assert row.model == model and row.status == 'spent'
        assert row.configuration_hash == configured and row.reserved_micro_usd == maximum
        assert row.output_upper_bound == 4096
        assert (row.input_price_micro, row.output_price_micro) == (a, b)
        assert row.spent_micro_usd == (10*a+10*b+999999)//1000000
    assert (transport.MODEL, transport.CONFIG_HASH, transport.INPUT_PRICE, transport.OUTPUT_PRICE) == original


def test_unreviewed_context_never_reserves_or_dispatches(answer_client):
    client, headers, sender, vector_id, bind, owner, _ = answer_client
    value, _ = transport.payload('A different frozen question?', [dict(id=1, text='Synthetic context')])
    with frozen_model_request(value, 999):
        result = client.post('/answers', headers=headers, json=dict(q='Synthetic question?',
            embedding_ids=[vector_id], request_id=uuid4().hex, confirm_external_ai=True))
        assert result.status_code == 409
    sender.assert_not_called()
    with Session(bind) as db:
        assert db.scalar(select(AiUsageAttempt).where(AiUsageAttempt.owner_id == owner)) is None
