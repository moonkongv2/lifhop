# Phase 3.3 remaining acceptance

Status: 2026-10-18. The selected-context, 46-record indexing and three-question
integrated smoke passes are closed. Phase 3.3 remains incomplete; this plan does
not authorize another provider request.

## 후속 준비 상태와 근거 수집 기준 (2026-10-18)

인용 지침은 `6a7beda`, 미해결 항목 표시 수정은 `9d9eb69`로 분리 커밋했다.
이번 후속 검토에서 관련 백엔드 테스트 110개와 전체 701개가 통과했다.
현재 설정은 `ANSWER_MODE=off`다. 외부 AI 요청이나 새 임베딩은 실행하지 않았다.
마무리 비교에서 기존 검증 파일 138개의 SHA-256, 과금 원장 전체, source 정책,
Entry별 AI 허용/선택 버전 메타데이터가 그대로임을 확인했다. 미확정 예약은
3건/USD 0.006801로 유지된다. 비공개 결과는
`.local/evaluation/phase33/handoff-preservation-20261018.json`에 남겼다.
아래는 자료 준비 기준이며, 새로운 과금 실행 승인 요청이나 완료 선언이 아니다.
기존 문서의 축소/유예 선택지는 현재 채택하지 않는다. 모든 미충족 조건을 유지하고
Phase 4는 시작하지 않는다. 과거 감사 결과를 이번 새 검색 결과로 해석하지 않는다.

### 지금 필요한 실제 원본

기존 허용 풀의 감사에는 Codex 3개/7개 부모 구간, GitHub 문서 43개/267개 부모
구간이 있다. 검토된 Codex는 lifhop 계획·우선순위, GitHub는 다른 앱 문서다.
같은 키워드나 서로 다른 프로젝트의 계획·구현을 연결해 통과시킬 수 없다.
기존 비공개 `scope-audit-222116b7ad9c4fbf92b37e354a0061e5/`의
`scope-assessment.json`, `audit.json`, `review.html`을 보존한다.

| 미충족 조건 | 준비할 실제 근거 | 통과 판정에 필요한 사실 |
| --- | --- | --- |
| 동일 결정과 구현의 Codex·GitHub 연결 | Codex의 명시적 선택/요구 문장과, 같은 프로젝트·대상을 구현했다고 기록한 GitHub 커밋 메시지 또는 문서의 정확한 구간 | 결정 내용, 구현 내용, 양쪽의 연결을 각각 설명할 수 있어야 한다. 동일 SHA/PR/경로의 명시적 참조 또는 동일 대상·행동을 직접 확인할 연결 근거가 필요하다. 두 출처를 실제 인용해야 한다. |
| 실제 채택한 변경과 이유 | 초기안, 이후 채택/변경을 명시한 문장, 그 선택에 붙어 있는 이유. 원본 날짜·순서도 함께 확보 | 무엇에서 무엇으로 바뀌었는지, 실제 채택되었는지, 기록된 이유가 무엇인지 각각 직접 뒷받침해야 한다. 조언·검토 목록·추정 이유는 통과 근거가 아니다. |
| 실제 일상 사실과 선택 이유 | 실제 이용/예약/구매/선택을 명시한 대화·메모와 그 이유. 여행이라면 시기·업체·실제 이용 여부와 이유를 구분 | 후보 업체나 희망 질문이 아닌 실제 사실과 명시된 이유를 답해야 한다. 기존 오키나와 질문의 근거는 아직 없다. 다른 일상 사례를 고르면 이 질문의 미확인 상태를 별도로 남기고 평가 사례 변경을 사용자와 합의한다. |

첫 두 조건은 동일한 실제 변경 사례가 양쪽 조건을 모두 충족하면 근거를 공유할 수
있지만, 두 판정은 따로 기록한다. 구현 기록만으로 테스트·운영 배포 성공까지 추론하지
않는다. GitHub diff나 Codex 명령 결과가 존재하더라도 현재 AI 입력 허용 범위를
대신하지 않는다. 제외된 본문은 열지 않으며, 기존 primary-text 규칙을 넓히지 않는다.

사용자가 지금 제공할 것은 **위치 단서**다: 프로젝트/저장소, Codex 세션 제목·날짜,
GitHub 커밋 SHA/문서 경로·링크, 일상 기록의 제목·날짜 중 아는 정보만 있으면 된다.
이것은 제외 기록 열람, 권한 변경 또는 외부 전송 승인이 아니다. 기존 허용 범위 밖이면
후보의 식별 정보와 필요한 열람 범위를 먼저 제시하고, 본문 검토는 해당 허가 후 진행한다.
새 기록 작성으로 과거 사실이나 당시 선택 이유를 소급해 만들어내지 않는다.

각 후보는 비공개 자료표에 아래 정보를 채워야 준비 완료로 본다. 개인정보·원문·정답은
Git에 넣지 않는다.

- 원본 식별: 소유자, provider/source scope, Entry/version, 원본 링크·세션/커밋 식별자.
- 재현 가능한 구간: field, start/end, SHA-256, 현재 버전/삭제 상태, source/record AI 정책.
- 의미 검토: 정확한 주장과 이를 뒷받침하는 문장, 양쪽 기록의 연결, 채택 여부와 명시된 이유.
- 날짜 구분: 사건 시각, 수집/관찰 시각, Asia/Seoul 날짜. 모르는 시각은 미상으로 유지.
- 독립 채점표: 필수 사실, 허용되는 불확실성, 금지할 추론. 질문과 실제 전송 본문에서 분리.

### 자료 준비 후 한 번에 제시할 검증 패키지

현재 세 긍정 범주의 원본/정답표가 없으므로 **최종 질문 수·전송 구간·비용 승인안은
아직 준비되지 않았다**. 인용 지침만 또는 날짜 수정만 따로 유료 재실행하지 않는다.
자료가 준비되면 다음 항목을 한 패키지로 확정해 별도 승인을 요청한다.

| 검증 항목 | 확정할 실행·판정 범위 |
| --- | --- |
| 세 긍정 범주 | 위 원본에서 자연어 질문과 필수 사실을 고정하고 실제 Semantic → 추천 → 답변 → 원본 인용을 검증한다. 교차 출처 사례는 한 provider로 제한하지 않는다. 정답 구간을 검색/추천에 주입하거나 출처 다양성을 강제하지 않는다. |
| 인용 완전성 회귀 | 기존 부분 통과 질문을 알려진 회귀 사례로 명시한다. 답변의 모든 사실을 **실제 반환 인용**에 대조한다. 여러 구간의 보완 사실이 필요하면 해당 인용이 모두 있어야 한다. 필요한 정답 누락과 미인용 사실을 따로 판정한다. 새 독립 품질 평가로 계산하지 않는다. |
| 한국 시간 회고 회귀 | 기존 2026-09-28~30 회고 범위와 원본을 기준으로 UTC 2026-09-28 / 서울 2026-09-29 경계의 날짜를 확인한다. +09:00 메타데이터, 사건/수집 날짜, 제안/채택/완료 분류와 항목별 인용을 함께 검사한다. 날짜를 전혀 말하지 않아 경계를 검사할 수 없으면 날짜 수정 통과로 처리하지 않는다. |
| 기존 통과·보호 조건 | 역사적 cutoff/근거 부족 거절의 기존 결과와 현재 로컬 회귀 결과를 함께 제시한다. 변경된 공통 지침에 대한 실제 재검증 포함 여부와 이유를 사전에 명시한다. 권한·삭제·소유권·재전송·예산 보호는 계속 필수다. |

승인안에는 정확한 질문/필터/날짜, 기대 주장과 원본 앵커, owner/DB/policy/config
digest, 허용 풀과 현재 벡터, 자동 선택 가능한 본문 범위, 호출 수·전송 바이트·최대 비용,
일회 실행 및 중단 조건을 적는다. 자동 선택 문장은 검색 후 정해지므로 허용 풀 전체를
미리 고정하고 실제 선택을 전송 전에 재확인한다. 새 자료의 임베딩이 필요하면 그 대상·
구간·호출/비용을 별도 항목으로 산정한다. 기존 벡터 재생성을 기본으로 삼지 않는다.
기존 한 동작 한도(질문+답변 USD 0.011, 답변 5개 구간/14 KiB)를 유지하며 전체
월 한도·미확정 예약을 포함해 가용액을 확인한다. 가격은 실행안 작성 때 재확인한다.

사용자 승인 후에만 해당 프로세스에서 답변을 일시 활성화하며 영구 설정은 off로 둔다.
원본 응답/실패/예약과 닫힌 실행 표식을 보존하고, 자동 재시도 없이 단계별 검색 누락,
선택 누락, 답변·인용 오류, 날짜 오류, 시간과 비용을 구분해 기록한다. 필수 조건 하나가
실패하거나 검증되지 않으면 Phase 3.3을 완료로 표시하지 않는다.

## Remaining scope audit implemented (2026-10-18)

The local preflight now includes every structurally blocked case in its unresolved
category list, not just explicit deferrals and negative substitutes for positive
categories. Previously an empty evidence set or a missing required source could
be absent from that list despite coverage gaps elsewhere in the report. The HTML
now shows the complete unresolved list. Tests cover empty/denied/deleted/foreign
corpora and a selected Codex excerpt with the required GitHub source unavailable.
This summary does not prove that the contents support the proposed answer;
candidate relevance and adopted reasons still require direct review.

A fresh, read-only discovery used only the existing permitted 46-record pool.
It found the same 1,060 valid vectors and 274 primary parents; usage/run/job/Entry
counts were unchanged. Denied record bodies were not materialized. No API call,
indexing activation, permission change or paid replay occurred. Detailed source
anchors and relevance findings are private outside Git.

| Remaining item | Local finding | Required resolution |
| --- | --- | --- |
| Linked cross-source implementation | Reviewed Codex planning and GitHub app documents do not establish the same decision/implementation; the worker query returned Codex only | Review an actual linked pair from owner-selected permitted records, or explicitly defer this gate |
| Adopted change with reason | Inspected hits contain proposals, priorities or review checklists, not an adopted change and its stated reason | Review an explicit adoption/reason, or explicitly defer this gate |
| Positive ordinary-life recall | Two rental matches are desired example questions, not a used company and selection reason | Review a real note/conversation containing the fact, or explicitly defer this gate |
| Citation completeness and Seoul period dates | Local instruction/metadata fixes are implemented; original live failures remain preserved | Include both in one later reviewed acceptance pass; no automatic retest |

These are findings from bounded permitted discovery, not proof that the owner's
entire original history lacks evidence. Do not broaden permissions, invent facts,
pair unrelated projects or treat keyword hits as acceptance. The next owner
decision is either to identify the missing real evidence and its allowed scope,
or agree a concrete narrower gate that leaves those categories deferred. This
audit does not itself change the roadmap order or authorize Phase 4.

Focused preflight/executor tests: **29 passed**; full backend **701 passed** and
diff whitespace passed. The citation instruction correction is committed
separately as `6a7beda`; this checkpoint covers the unresolved-report correction
and scope audit. No frontend or schema change.

## Latest local change: citation instructions strengthened

The shared answer instructions now require cited excerpts collectively to support
every factual claim and include all necessary IDs. Optional details unsupported
by those citations must be omitted; if a complete answer is no longer possible,
the response must be insufficient with empty citations. The same rule is sent
for current, period and historical answers. This is a prompt correction, not a
new semantic verifier or a guarantee of factual correctness.

Four synthetic checks were added: an API case with complementary facts in two
of three selected sources, and instruction delivery for three answer modes. The
API preserves exactly the provider's two citations, omits the unused source and
settles once without replay. Focused answer/run/period/history tests: **81 passed**.
Final full backend suite: **700 passed**; diff whitespace check passed.
No model, embedding, schema, dependencies, API format or usage limits changed.
No real-provider call, permission expansion or persistent answer enablement.
The configuration hash changed; preserve prior protocols and raw answers, and
prepare a fresh scope before any future paid action. Existing vectors remain
compatible and do not need reindexing for this instruction change.

### Remaining acceptance, reviewed together

| Item | Current evidence | Next step before a final acceptance decision |
| --- | --- | --- |
| Citation coverage | Real partial result; instruction correction tested synthetically | Include complementary-source claims in the next agreed real check; inspect each claim against returned citations |
| Period dates | Real UTC/Seoul mismatch; metadata/instruction correction tested synthetically | Retain failure and include a Seoul date boundary in the next agreed check |
| Automatic retrieval | Three source-filtered known cases executed; one partial answer | Keep these as smoke results; do not infer broad unfiltered recall |
| Cross-source implementation | Validated source types exist; no reviewed linked case | Identify an actual recorded decision and its matching implementation in permitted primary text |
| Adopted change and reason | Proposals exist; adopted reason not established | Find the explicit adoption/reason, or report absent/excluded evidence |
| Positive ordinary-life memory | Desired rental question only; negative case passed | Supply a real fact/reason in permitted records, or explicitly agree a narrower gate |

Do not make a separate paid loop for each instruction adjustment. Inspect the
remaining permitted evidence locally, then present one complete acceptance scope
or an explicitly narrower release proposal for owner agreement. No category is
waived by this local fix; Phase 3.3 remains incomplete and Phase 4 has not started.

## Latest result: integrated smoke pass closed

The owner approved three questions, up to fifteen automatic excerpt occurrences,
one pass/six calls/USD 0.033 and temporary answer enablement. The exact protocol
matched live owner/database/policy/configuration and the full frozen index.
Existing product handlers processed actual question embeddings, their ranked
hits, unchanged automatic parent recommendations and answers. No scoring answer
or reference anchor entered retrieval, selection or model requests.

| Case | Retrieved / selected / cited | Direct review |
| --- | --- | --- |
| Codex priority order | 20 / 5 / 1 | Pass: exact user priority order and citation match |
| GitHub README purpose/flow | 20 / 5 / 1 | Partial: core explanation supported, citation coverage incomplete; reference vehicle-selection detail omitted |
| Codex production proof | 20 / 4 / 0 | Pass: insufficient with no invented deployment success |

All three expected statuses matched, but this is not three full acceptance
passes. The GitHub answer describes the child audience, which appears in selected
README context but not the only excerpt it actually cites. A source elsewhere in
the request is not a complete returned citation. The missing reference checklist
detail is recorded separately from the factual citation gap; do not rewrite the
answer or automatically insert a reference to make the result appear passed.

Actual **six calls** (three query/three answer), **fourteen excerpt occurrences**,
**USD 0.000997 settled**, **zero new uncertain usage**, **4.5–5.3 seconds/action**.
Two original citation reads and the refusal explanation were independently
checked with zero provider calls/new usage rows. The same-action domain-separated
ledger and exclusive marker prevent replay. All prior attempts, source policy
and versions were preserved. Temporary process settings were restored; answer
mode remains off. Private raw stage responses, ledger, grounding review and
readable results are retained alongside the immutable protocol. Approval is
consumed; do not repeat it.

Existing recommendation/Semantic/answer tests rerun after execution: **61 passed**;
diff whitespace passed. No app code changed, and no new browser run was made.

The subsequent local correction above requires citations supporting
all returned factual details and omit a detail that cannot be tied to selected
evidence. Preserve the observed failure; do not silently add guessed citations
or use evaluation answers to repair output. Synthetic checks can verify request
contracts and no-retry behavior, not prove semantic grounding. Consolidate this
with the remaining acceptance gaps before seeking any fresh real-model pass;
do not start another paid tuning loop against these three known cases.

## Latest result: approved indexing completed

The owner explicitly approved the 43 GitHub documents and three Codex records,
one pass, at most 72 calls/USD 0.01. Exact frozen manifests matched live policy,
versions, selectors and configuration. Both runs completed with follow-changes
disabled: **46 records / 1,060 eligible vectors**, **67 actual calls**, **USD
0.000996 settled**, **zero new outstanding usage**, about **56 seconds**.

Independent readback matched all stored anchors to the manifests, checked
1,536-dimensional nonzero vectors and verified the local status API overall and
by provider. It made no provider calls or new usage reservations. Prior attempts,
old runs/jobs, source versions and permissions were preserved. Question/answer
calls remain zero in this pass; no answer-mode or model setting changed.

An optional run selector now bounds worker claim, expired-lease recovery and batch
processing to the two approved run IDs; an empty selector processes nothing.
Unscoped processing retains its normal behavior. Two scope-isolation regressions
were added. Full backend **696 passed**, focused indexing tests **31 passed** and
diff whitespace passed. No frontend change or browser check was required.

Step 2's private protocol has now been executed and closed (details below).
Index availability establishes readiness, not broad answer
or automatic retrieval quality. The approval is consumed; do not rerun it or send
new questions under the indexing permission. The readiness counts below describe
the pre-execution snapshot and are retained as the audit trail.

## What the completed pass establishes

- Two missing-evidence questions correctly declined to invent facts.
- A historical priority answer matched its original evidence.
- The period review separated activity and proposals, but used one UTC day
  instead of the Seoul day. Payload offsets and instructions are fixed;
  two synthetic regressions pass. Actual model compliance after the fix is
  unverified. Preserve the original response and record the failure.
- Four citation reads matched the selected original ranges. This checks the
  selected context, not automatic retrieval or broad answer quality.

## Read-only account readiness audit

The audit used a repeatable-read, read-only transaction. Source-policy and lexical
counts select metadata only. Indexing previews process currently allowed primary
text locally to calculate exact slice anchors and byte bounds; they store no
source bodies. No API call, indexing activation, permission change or new ledger
reservation occurred. Entry/run/job/attempt row counts were unchanged.

| Observation | Result | Meaning |
| --- | --- | --- |
| Current local projections | 480 ready records | Local passage search is ready |
| Currently AI-permitted records | 46 | 43 GitHub documents and three selected Codex records |
| Usable current embeddings | 0 records / 0 slices | Integrated Semantic retrieval cannot yet be evaluated |
| Older indexing jobs | 1,031 stale | Old jobs are not fresh indexing authorization |
| Answer mode | off | No persistent answer-mode setting was changed |

The prior primary-text projection/configuration change invalidated old vectors.
The recent date correction changes the answer configuration, not the embedding
space; it is not itself a reason to re-embed. Keep the existing embedding model.

Keyword matches are discovery counts, not proof of a decision or its reason.
In particular, the existing rental examples contain a desired question, not an
actual vendor/selection reason. Do not turn this negative test into positive
life-memory acceptance or enable additional records to make the set pass.

## Next sequence

### 1. Restore a bounded current index — completed

Prepare fresh manifests for the existing allowed records only. Fix the Entry
selectors, current versions, scope, policy/configuration and exact slice hashes;
follow-changes is false. The reviewed previews contain:

| Source | Records | Pending slices | Call ceiling | Conservative cost ceiling |
| --- | ---: | ---: | ---: | ---: |
| Codex | 3 | 29 | 3 | USD 0.000310 |
| GitHub documents | 43 | 1,031 | 69 | USD 0.008113 |
| Total | 46 | 1,060 | 72 | USD 0.008423 |

Slice occurrences can repeat identical document text. Valid derivative reuse and
batching can reduce actual sends. The call ceilings conservatively use current
slice byte bounds and the worker's 16-input/16,000-byte packing; slices are not
individual API calls. Approval can use a combined USD 0.01 ceiling while keeping
the two stricter manifest budgets. No question or answer call is included.

Keep exact manifests in the private audit directory outside Git. Recheck them
before activation; drift requires refreshed review. Activate and process only the
approved run IDs; stop on failed/uncertain work rather than retrying automatically.
Do not resume older runs or release earlier uncertain reservations. Report actual
spent/uncertain cost and current eligible vector counts after publication. A
successful indexing pass alone does not establish retrieval quality.

### 2. Integrated-flow check — executed; grounding partially passed

**Preparation snapshot, subsequently approved and executed as recorded above.** Three proposed
questions cover Codex priority-order recall, GitHub README purpose/usage recall,
and missing production-deployment proof restricted to the permitted Codex source.
The two positive examples have directly inspected reference evidence; the
negative example preserves the requirement to decline unsupported claims. These
are known-evidence smoke cases, not a newly approved gold benchmark.

The private proposal binds owner/database/policy, answer/storage configuration,
all 1,060 vector anchors, 274 eligible parent anchors, exact questions/source
filters, reference evidence and scoring checklists. Its HTML includes the full
eligible parent-text pool for review. Source filters are part of each question;
the test does not measure unfiltered cross-source recall. The question and all
retrieval inputs must match the frozen proposal before paid execution.

At most three question embeddings plus three answers: **six calls / USD 0.033**
(query USD 0.003, answer USD 0.03). Actual answer excerpts cannot be known until
the real query executes. Approval must explicitly allow up to five automatically
selected complete parents per answer, at most fifteen excerpt occurrences total,
from the existing 46-record pool only. Keep the existing 14 KiB answer request
limit; no reindexing or policy expansion is included. Recheck every selected
anchor against this pool before answer dispatch. Expected answers/checklists
must not enter paid requests or modify ranking/selection.

Execute the existing `/semantic/search` → `/answers/recommendations` → `/answers`
handlers with the same question, filters, revision and action ID. Save each
stage, originals, omission reasons, latency and separately settled query/answer
cost. Use an exclusive run marker and separate query/answer ledger domains;
stop on failure without replay. A retrieval/context miss remains in the report;
do not manually insert the expected evidence. Missing selected evidence should
prevent a positive answer and be classified separately from an answer error.
The configured answer mode remains off. Approval should include enabling answers
temporarily inside this bounded process only; restore settings afterward.

Local checks used a reference **source vector**, not a paid question vector, to
exercise real-corpus distance ranking/grouping and parent recommendation. All
three probes selected reference text within request limits. This verifies wiring
and stored-vector readability only; it does not establish question recall or
answer grounding. Preparation ran in a read-only transaction and left usage-row
counts unchanged. Additional actual provider calls: **zero**.

Existing backend recommendation/Semantic/answer tests rerun: **61 passed**.
Existing frontend integrated question/search tests rerun: **32 passed**. No app
code or frontend behavior changed in this preparation; no browser run was made.
The prior worker/indexing slice was committed as `e45e74e`.

After indexing, prepare exact questions, independent expected claims and source
anchors from permitted primary records. Reuse supported evidence deliberately
only as a smoke check, not as a fresh general-quality benchmark. Do not expose
expected answers to the retriever/model or force source diversity at ranking time.

Inspect query → Semantic hits → parent recommendation → answer → original citation
as distinct stages. Separate query/retrieval misses from context-selection and
answer-grounding failures. Prepare the data/call/cost manifest before obtaining
any new question/answer transmission approval. Each integrated action retains
its existing two-call/USD 0.011 cap. No broad tuning or model change is planned.

### 3. Resolve the remaining acceptance scope explicitly

| Gap | Evidence or decision needed |
| --- | --- |
| Cross-source decision and implementation | A genuine linked Codex decision and GitHub primary implementation record; source presence alone is insufficient |
| Reason and later change | An explicit adopted change with its recorded reason, rather than an assistant proposal |
| Positive ordinary-life recall | A real non-project fact and reason present in permitted records |
| Period calendar correctness | Retain the observed failure; include the Seoul boundary in any separately approved final check |
| Automatic retrieval | Integrated-flow results after current indexing |

First inspect permitted evidence locally for relevant cases. If records are absent
or excluded, report that boundary and present a concrete new source/record scope
for review, or ask the owner to accept an explicitly narrower release gate.
Do not silently waive a category, alter permissions or mark Phase 3.3 complete.
Phase 4 scheduled collection begins only after the remaining exit scope is agreed
and its checks are satisfied.

## Verification and handoff

The implementation committed before this audit passed all **694 backend tests**
and `git diff --check`. This follow-up changes documentation and private local
audit artifacts only; no frontend, schema, model or dependency changed. Read-only
database execution and unchanged row-count assertions verified the audit. The
existing indexing-job/Semantic tests were also rerun: **51 passed**. Diff whitespace
checks passed. No new tests or browser steps are required to inspect these findings.

The owner need not repeat a closed pass or local readback. Review the results and
the citation-coverage finding; no browser action is required to inspect the agent's
checks. Preserve frozen protocols and raw answers. The worker/indexing change was
committed as `e45e74e`; integrated results were committed as `693b919`. The
citation instructions and regressions are committed separately as `6a7beda`
(`fix: require cited support for every answer fact`).
