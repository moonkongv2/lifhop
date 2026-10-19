"""Temporary model pricing for a single-process, offline answer verifier only.

Never use this context inside a running product server: the transport module is
process-global. Each verifier process must execute exactly one frozen request.
"""
from contextlib import contextmanager
from app.evaluation.schemas import digest
from app.services import answer_transport as transport, answer_call as caller
from app.services.embedding_transport import EmbeddingError

PROFILES = {'gpt-6-luna': (100000, 500000), 'gpt-6-sol': (2000000, 10000000)}


@contextmanager
def frozen_model_request(request, maximum_micro_usd):
    model = request.get('model')
    if model not in PROFILES or type(maximum_micro_usd) is not int:
        raise EmbeddingError('ANSWER_COMPARISON_PROFILE_INVALID')
    original = {name: getattr(transport, name) for name in
        ['MODEL', 'INPUT_PRICE', 'OUTPUT_PRICE', 'PRICE_HASH', 'CONFIG_HASH']}
    prepare, reserve = caller.prepare_payload, caller.reserve
    expected = digest(request)
    try:
        transport.MODEL = model
        transport.INPUT_PRICE, transport.OUTPUT_PRICE = PROFILES[model]
        transport.PRICE_HASH = digest(dict(model=model, input=transport.INPUT_PRICE, output=transport.OUTPUT_PRICE))
        transport.CONFIG_HASH = digest(dict(base=original['CONFIG_HASH'], model=model,
            price=transport.PRICE_HASH, request=expected))
        def checked(*args, **kwargs):
            value, upper = prepare(*args, **kwargs)
            if digest(value) != expected or transport.cost_micro(upper, transport.OUTPUT_LIMIT) != maximum_micro_usd:
                raise EmbeddingError('ANSWER_CONTEXT_CHANGED')
            return value, upper
        def priced(db, **kwargs):
            # The product's USD .01 action limit stays unchanged outside this
            # isolated verifier. Only the exact reviewed request gets its bound.
            if kwargs['purpose'] != 'answer' or transport.cost_micro(
                    kwargs['upper'], transport.OUTPUT_LIMIT) != maximum_micro_usd:
                raise EmbeddingError('ANSWER_COMPARISON_PROFILE_INVALID')
            return reserve(db, **dict(kwargs, run_limit=maximum_micro_usd))
        caller.prepare_payload, caller.reserve = checked, priced
        yield
    finally:
        caller.prepare_payload, caller.reserve = prepare, reserve
        for name, value in original.items():
            setattr(transport, name, value)
