# Phase 3.3 selected-passage answers

After a Semantic or local Passages search, select up to five displayed passages.
The screen shows exact text and source/version links before a separate answer
consent. The answer request sends the question and those passages to OpenAI, then
shows a draft with links back to the retained text. It may say evidence is
insufficient. Passages mode searches locally and does not need a stored vector or
a paid question embedding; Semantic mode still needs one paid question embedding.
This is a first answer flow, not a complete date-range retrospective or general
automatic RAG answerer. The owner must check whether each cited passage supports
every claim.

## Boundaries

- `ANSWER_MODE=off` is the default. The existing `.env` OpenAI key and Semantic
  indexing approval do not enable real answer generation. The separate checkbox
  and button are required for each paid answer.
- `POST /answers` accepts a question of at most 256 characters, one to five
  distinct current Semantic slice IDs **or** local passage IDs, a fresh request
  ID and explicit consent. Only the selected exact text is sent. Work-only text,
  title matches, source-deleted records, old versions and AI-excluded records
  fail the current policy check. A local passage can be up to 2,000 characters;
  the combined request is capped at 14 KiB, so a long selection may need fewer
  passages.
- The server holds the owner policy lock through the provider call and rechecks
  citations afterward. A stale or revoked citation suppresses the answer even
  when the provider call has already been charged.
- The pinned model is `gpt-4.1-mini-2025-04-14`; each Responses request uses
  structured output, no API-side storage, at most 512 output tokens, and the
  existing monthly AI budget. Its durable request cap is one call and USD 0.01.
  Uncertain charges and invalid responses are not retried automatically.
- Answer text and question vectors are not stored by lifhop. The response remains
  in browser memory while the search result is present. Citations are validated
  references, not a guarantee that the generated claim is true.

The Responses request and structured output shape follow the
[OpenAI text generation guide](https://developers.openai.com/api/docs/guides/text)
and [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).
The pinned model and published input/output rates are listed in the
[GPT-4.1 mini model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

## Verify without external transmission

```bash
docker compose -f compose.test.yaml up -d --wait test-db
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@localhost:55433/lifhop_test .venv/bin/pytest tests/test_answers.py -q
```

Expected: ten backend tests pass, including policy refusal, one-call
replay, revocation before/after dispatch, insufficient evidence and invalid
model citations, plus an answer from a local passage without a Semantic vector.
Frontend checks: `cd frontend`, then `npm test`, `npm run lint`
and `npm run build`.

For browser verification, start `.venv/bin/python scripts/preview_semantic.py --port 8003`
in one terminal. In another terminal, run `cd frontend` and
`LIFHOP_API_PROXY_TARGET=http://127.0.0.1:8003 npm run dev -- --host 127.0.0.1 --port 5175 --strictPort`.
These ports avoid older 8002/5174 previews; stop an older process or choose
another matching API/proxy pair if either port is occupied. Open
`http://127.0.0.1:5175/search` and log in with
`demo@example.test` / `demo-password`. Choose Semantic and ask where the worker
runs. Review index, consent to the synthetic search and submit. Select the worker
passage, then consent to the answer and press Generate cited answer. Expected:
one synthetic draft answer and a citation opening the same exact passage. Switch
to Passages and search for `worker`, then select the worker passage and generate
an answer after the separate consent. This route makes no question-embedding
request; its synthetic answer cites the local passage reader. The
demo uses an isolated test schema and mocked providers; normal shutdown drops
the schema. `http://localhost:5173/search` is the real development account,
where answer generation remains disabled by default.

## Next

Review the real indexed Semantic screen first. Then decide whether to enable
a separately scoped real answer check, stating which questions and selected
passages may be sent and the call/cost cap. Answer quality, insufficient-evidence
behavior, historical source treatment and date-range retrospectives remain
unverified. The previous 43-document embedding/ten-question authorization does
not cover answer requests.
