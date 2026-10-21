# Questions from observed historical versions

Implemented 2026-10-18. Search → **Search & ask** → enter a question →
**Advanced options** → **Record version: Observed by a date** → choose the
**Observed through** date → **Search**. The preview is local. Review its
exact original excerpts and coverage, then explicitly approve one answer call.
Existing answer modes still use current eligible versions.

## What the date means

The cutoff includes the full selected date in Asia/Seoul. For each currently
retained, owned record, choose the version with the greatest `observed_at` before
the next day's boundary; version ID breaks ties. Choose this version **before**
matching the question. If it does not match, do not search an older version of
the same record as a fallback. Restoring a version changes current selection,
not this ordering of retained observations.

`observed_at` means when lifhop observed that stored version. It does not prove
when the event, decision or external document change happened. `event_at` is
shown separately; `source_updated_at` is not used as a universal historical truth
because source providers do not supply equally reliable change histories.
An archive first imported in October cannot establish lifhop's observed state
in January, even if its events occurred in January. No version by the cutoff
means no evidence in this mode; never silently substitute today's version.
Reobservations of identical content and past selection/restoration events are
not reconstructed as a full timeline.

## Bounded local selection

- Apply current ownership, source/type scope, current record and source AI
  permissions and source-deletion exclusion. Both current record type and the
  historical version type must qualify under the shared AI source gate; an
  explicit type filter must match both. NOTE, DOCUMENT and CONVERSATION remain
  eligible; validated Codex/GitHub primary events now qualify as described in
  [AI_SOURCE_COVERAGE.md](../design/AI_SOURCE_COVERAGE.md). Logs and arbitrary project events remain excluded.
- Match up to sixteen existing query tokens (or a literal nonempty fallback)
  against the chosen versions' bodies. English stopwords follow the existing
  Passage tokenizer. This is local keyword matching, with no translation,
  vector lookup, question embedding or historical index.
- Consider at most twenty newest matching versions. Examine only bounded
  source material (1 MiB content, 2 MiB payload per version) and at most 512
  primary-text ranges. Reuse canonical Codex mapping to omit work/commentary
  when a record otherwise qualifies. Invalid mappings are skipped.
- Select the first matching full range per record, at most 2,000 characters,
  and at most five records within the actual serialized 14 KiB answer request.
  Skip an entire range that does not fit; never truncate it to gain inclusion.
- Show scoped/observed/allowed/matching/examined counts, materialization and
  request-size skips, exact observation/event dates and source incompleteness.
  Always label the result a partial view. Additional sections, older matching
  versions and versions beyond the candidate cap are not examined.

This is deliberately a bounded observed-history path. It does not claim semantic
recall, the best historical passages, an exhaustive summary or reconstruction
of the external world. Sparse observations, late imports, duplicate documents,
keyword mismatch and unsupported record types can yield incomplete/no results.

## Consent, dispatch and citations

`GET /historical/preview` sends nothing externally and reserves no usage.
`POST /historical` requires a reviewed owner-bound digest and explicit consent.
It recomputes the preview under the shared owner lock/search deadline. The digest
binds the normalized question, source/type/cutoff, revision, counts, exact excerpts
with date/current-version metadata and answer configuration.

The common answer caller rechecks every selected owned version, exact range/hash,
latest-observed eligibility, current type/source/AI permission, source state and
primary-text mapping before reservation and again under the dispatch owner lock.
Metadata and serialized request must still match. Return-time checks discard an
answer whose sources changed after dispatch. Deleted records and denied sources
cannot be revived by an old preview. Failures before sending release reservations;
already sent/uncertain calls keep the existing conservative accounting.

Reuse the existing answer ledger domain, one call, USD 0.01 maximum, monthly
budget, concurrency slot, 512-token output and no automatic retries. An action ID
cannot be reused by changing answer mode. Existing off-by-default activation,
model, pricing and uncertain reservations are unchanged. The historical request
adds `observed_through` and excerpt `version_id`, `observed_at`, `event_at` and
`completeness`; the consent describes these fields. Configuration hashing
includes the historical instructions. Closed experiments are not reopened.

The answer must use only the supplied excerpts and distinguish recorded plans
from evidence of adoption/completion. It must return insufficient when historical
facts are not supported. This instruction and output-shape validation do not
prove factual quality. No real-model quality claim follows from the mock demo.

Version/range/hash citation links use the retained citation reader and survive
current index replacement. **Open current record** remains a separate action.
Source-deleted records remain locally readable under existing history rules but
are excluded from new historical answer selection. Local deletion removes access.

Browser drafts, source/cutoff/question/account/revision changes, Stop and a
60-second deadline cancel or discard stale work. Results are ephemeral; returning
from citations or reloading does not resume/replay paid stages. A temporary
availability recheck hides a result while preserving it if the same reviewed
context remains valid. Changed context resets the run and consent.

## Verification and optional visual check

The agent verified the synthetic browser flow: January selects server Alpha's
proposal; February selects server Beta's recorded decision. The January citation
retains Alpha while the current-record link shows Beta. Before the first
observation there is no evidence and no answer call. Reload and citation return
do not replay a paid stage. Two mock calls, zero actual OpenAI calls.

Backend 641 tests and frontend 181 tests passed. Backend checks include Seoul
boundaries, deterministic ties, version selection before keyword matching,
restores, source/type/ownership exclusion, bounded full text, exact metadata,
preview changes, one-call accounting, dispatch-time revocation and post-dispatch
output suppression. An initial whole-suite failure came from a new test's
unremoved secondary owner; cleanup was corrected and the entire suite passed.
A real-browser result-loss bug during asynchronous rechecks was fixed with a
regression test before the successful flow. Lint/build and OpenAPI type alignment
are also checked at completion.

No mandatory user repetition is needed for functional verification. For optional
visual review, use the synthetic preview (provider is mocked):

```sh
.venv/bin/python scripts/preview_semantic.py --database-url postgresql+psycopg://lifhop:lifhop@localhost:5433/lifhop_test --port 8002
```

In another terminal, from `frontend/`:

```sh
LIFHOP_API_PROXY_TARGET=http://127.0.0.1:8002 npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

If these ports already serve this latest synthetic preview, reuse them. Open
`http://127.0.0.1:5174`, log in as `demo@example.test` / `demo-password`, enter
`Deployment history` in Search. Under Advanced options choose Record version →
Observed by a date, set Observed through to `2026-01-31` and Search. Expect Alpha; `2026-02-28` selects Beta;
`2026-01-01` selects nothing. Explicit consent plus **Answer from historical
excerpts** produces a synthetic cited answer. No import/embedding worker is
needed. Screenshot: `.local/verification/historical-january.png` (ignored).
