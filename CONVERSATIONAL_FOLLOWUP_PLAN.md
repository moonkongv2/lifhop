# 저장된 대화에서 이어 묻기 구현 계획

2026-10-20. 개정2: 사용자별 PostgreSQL 저장 방식으로 변경. 구현 전 계획이며,
이번 `agy-plan-review-loop 2`는 이 개정안만 검토했으며2회 지적 반영을 완료했다. 제품 구현/새 유료 답변
실행/Phase3.3 완료를 승인한 문서는 아니다. 이전 탭 한정 계획을 대체한다.

## 1. 사용자 흐름과 완료 기준

같은 PostgreSQL의 대화/턴을 `user_id`로 소유자에게 연결한다. 사용자마다 DB를
별도로 만들지 않는다. 대화 종료·페이지 이탈·로그아웃·서버 재시작 후에도 대화는
남으며, 같은 계정으로 재로그인해 목록에서 열고 후속 질문을 할 수 있어야 한다.

완료할 한 흐름:
1. Search & ask에서 첫 질문 → 저장된 대화와 원문 인용 답변.
2. ‘첫 번째 업체의 예약 진행도 있어?’ → 앞선 대상 해석, 기존 근거 재사용 또는 검색.
3. 대화 종료/로그아웃 → 재로그인 → 대화 목록/기존 답변 확인.
4. ‘그 뒤 취소한 기록도 찾아줘’ → 현재 권한·원문을 검사하고 추가 검색/인용 답변.
5. 다른 계정에서는 대화/턴/원문 모두 접근 불가. 대화 삭제 후 다시 나타나지 않음.

한 입력창에서 자연스럽게 이어 묻는다. 내부 검색방식을 사용자가 고르지 않으며,
대상이 모호하면 짧게 되묻는다. 오래된 특정 답변은 ‘이 답변에 이어 묻기’로 지정한다.
답변 저장은 사실의 정확성 인증이 아니며 이전 AI 문장은 원문 근거를 대신하지 않는다.

첫 범위는 **현재 기록을 쓰는 일반 Search & ask + 저장 대화 목록/상세**다.
과거 cutoff/기간 회고·고급 수동 선택·장기 개인 메모리·메시지 편집/분기·공유·자동제목
생성은 변경하지 않는다. 기기 간에도 같은 계정의 DB 목록/복원은 가능하나 동시 편집은
서버에서 충돌 처리한다. Phase4 수집은 시작하지 않는다.

사용자는 현재 답변 수준을 허용 가능하다고 밝혔다. 과거 실측 v2 4/7/원본/실패는
그대로 보존하고 이 작업을 과거7건의 키워드 재튜닝이나 완료조건 축소로 사용하지 않는다.

## 2. 현재 코드와 바뀌는 경계

| 파일/현재 상태 | 변경 |
| --- | --- |
| `app/models/user.py`, `app/models/__init__.py`, `alembic/env.py` | 대화/턴/근거 모델 등록·migration |
| `app/api/answers.py`, `app/schemas/answer.py` | 기존 단일 질문은 호환 유지; 별도 conversations API/schema |
| `app/services/answer_call.py`, `answer_transport.py` | DB에서 검증한 대화와 해석 질문을 일반 모드에만 선택적으로 전달 |
| `app/services/answer_evidence.py`, `app/api/semantic.py` | history 포함 wire 크기·검색→선택 서버 내부 연결 |
| `app/services/ai_usage.py` | followup 생성 호출의 가격/예약/정산/reconcile·stage ID 연결 |
| `app/services/source_history.py`, `app/services/citation_read.py` | 삭제된 기록의 파생 답변 제거·안정적인 과거 인용 읽기 |
| `frontend/src/components/QuestionAnswer.tsx`, `frontend/src/api/questions.ts` | 첫 질문 저장/새 대화 경로 연결; legacy 경로 보존 |
| `frontend/src/main.tsx`, `App.tsx` | `/conversations`, `/conversations/:id`와 대화 목록 이동 |
| `frontend/src/utils/session.ts`, 기존 캐시/Abort 처리 | 로그아웃은 DB 삭제가 아닌 메모리/캐시 비우기, 늦은 응답 폐기 |

현재 모델/답변 계약은 part-results-v3, 일반 request14KiB/output4096 후보,
회고·과거512. ANSWER_MODE=off. 마지막 로컬 backend819/frontend198·lint/build와
실제 v3 13회(계약13/13, 기본7건 v2 4/7, USD0.005012)를 구분한다.
총485 usage행/기존미확정3건USD0.006801과 기존 미커밋 변경을 건드리지 않는다.

## 3. 저장 모델과 보관 정책

### 선택과 대안

앱 PostgreSQL을 대화의 원본 상태로 사용한다. 새 Redis/별도 DB/큐/공급자 대화저장/
previous_response_id는 추가하지 않고 provider store=false를 유지한다.
이전 계획의 continuation/plan/evidence 서명 JWT와 access-token digest binding,
30분 수명/총6턴 제한은 제거한다. 로그인 만료는 인증만 끝내며 대화 수명을 끝내지 않는다.
후속 요청은 새 로그인으로 인증한 owner와 DB 소유권을 다시 확인한다.

개인 질문/생성 답변을 새로 보관하는 변화이므로 구현 시 DECISIONS에 저장·삭제·보관
결정을 기록하고, 실제 구현 완료 후 CURRENT/UNIFIED_ANSWER를 갱신한다.
현재 요청에서는 이 계획만 수정한다.

### 최소3테이블

| 모델(신규 `app/models/answer_conversation.py`) | 필수 데이터/제약 |
| --- | --- |
| `AnswerConversation` | id(무작위32hex), user_id FK, 첫 질문 기반의 짧은 제목, 고정 검색필터, active/closed 상태, context_epoch, revision, created_at/updated_at |
| `AnswerTurn` | id, conversation_id+user_id의 composite FK, seq, owner당 unique request_id, base_revision, epoch, 원래 q, 선택적 base_turn_id, evidence_reference_turn_id/context_root_turn_id, 검증한 history turn IDs, resolved_q/분기, state/outcome, 표시 답변/status/미확인, 안전한 오류코드, config/format version, stage별 dispatch marker·lease·usage IDs, 시각 |
| `AnswerTurnSource` | turn FK(cascade), entry/version/field/start/end/hash/projection_version의 안정 anchor, direct_selected/inherited/dispatch_intent/cited의 독립 flags; 같은 turn+anchor unique; entry/version으로 역조회 index |

추가 제약/index:
- conversation은 `(id,user_id)` unique, 목록은 `(user_id,updated_at,id)` index.
- turn은 `(conversation_id,seq)` unique 및 `(user_id,request_id)` unique.
- conversation당 미완료 turn이 하나만 존재하도록 partial unique index.
- TurnSource는 Entry/EntryVersion 삭제로 cascade하지 않는다. 원문 삭제 때 의존성까지
  사라져 파생 답변이 안전하다고 오인하면 안 된다. 숫자/tombstone anchor만 보존한다.
- user_id는 로그인에서 결정하며 클라이언트가 소유자/답변/사용근거를 써넣지 못한다.

원문 본문은 복제 저장하지 않는다. 모든 전송 근거(최대5개, 비인용 포함)와 history의
전이적 의존성 anchor를 TurnSource에 펼쳐 저장한다. inherited도 삭제하지 않으므로
여러 턴 전 비인용 자료의 제외/삭제를 감지할 수 있다. 현재 문맥epoch의 의존성이
500개 anchor를 넘으면 무전송으로 새 문맥을 안내한다. 저장된 대화 전체를 삭제하거나
임의 턴 수로 만료시키는 제한과는 다르다. 물리 저장량/조회 비용을 로컬에서 측정한다.

기존의 disposable Passage ID는 영구 인용 키로 쓰지 않는다. 저장 인용은
`CitationAnchor`의 version/field/range/hash를 사용한다. 표시 링크는 기존
`/passages/citation` 기반으로 만들고 검색 인덱스 재생성 후에도 읽을 수 있게 한다.
저장 대화의 TurnResponse는 별도 stable citation schema로 반환하며, 복원 시 폐기된
Passage ID를 가짜로 만들거나 legacy AnswerResponse 형식을 바꾸지 않는다.
모델 재사용은 retained-version 로컬 reader를 그대로 전송에 쓰지 않고, 해당 버전이
현재 AI 허용 primary projection과 일치하는지 기존 AI gate로 별도 확인한다.

### 보관·삭제

대화는 기본적으로 **사용자가 삭제할 때까지 보관**한다. 로그아웃·대화 닫기·새 대화·
앱 재시작으로 삭제하지 않는다. 닫힌 대화는 로컬 재개 동작으로 다시 active로 바꾼다.
보관 TTL/자동 삭제 설정은 이번 첫 버전에 추가하지 않고 UI에 이 기본 정책을 알린다.

대화 DELETE는 owner를 조건으로 conversation row lock을 잡은 짧은 transaction 안에서 turn/source행과 개인 텍스트를
트랜잭션으로 삭제한다. 별도 conversation/turn 테이블에 질문/답변 tombstone을 남기지
않는다. AiUsageAttempt는 cascade 삭제하지 않으며 본문 없는 회계 기록을 보존한다.
인플라이트 provider 응답은 삭제된 conversation/turn을 upsert하거나 복구하지 못한다.
원문을 지우는 동작과 대화만 지우는 동작도 구분한다.

실측용 private raw 결과는 이 새 대화 저장소로 import하지 않는다. 프로덕션에서는
provider raw JSON/원문 quotes/요청 전체/인증키를 DB나 로그에 별도 보관하지 않는다.
백업의 데이터는 즉시 물리 삭제되는 것이 아니며, 향후 Phase5의 백업 만료/복구 후
삭제 재적용 정책 대상에 이3테이블을 포함하도록 문서화한다. 이 계획으로 새AWS나
백업 서비스를 도입하지 않는다.

## 4. 저장 이력 표시와 AI 재전송을 분리

목록/상세 GET은 provider 호출0/예약0이다. ANSWER_MODE=off에서도 본인 저장 대화는
볼 수 있다. 소유자/근거 metadata를 먼저 조회하고 필요한 assistant body만 읽는다.
AI 제외·권한 오류를 판정하려고 금지된 원문 본문을 먼저 materialize하지 않는다.

| 현재 근거 상태 | 저장 이력 표시 | 새 AI 요청 |
| --- | --- | --- |
| 현재 버전·소유자·AI 허용 일치 | 원래 질문/답변·인용 표시 | 새 동의 후 사용 가능 |
| 버전 변경/출처의 AI 제외/work-only 등 기존 gate 제외 | 보관된 과거 답변에 변경/재사용불가 표시. 기존 로컬 열람 정책 내에서만 과거 인용 확인 | 이 근거에 의존하는 assistant/resolved_q/clarification 텍스트를 planner/query/answer에 재전송하지 않음 |
| lifhop에서 원문 삭제·실제 retained version purge/소유권 불일치 | 파생 assistant/해석/확인질문은 숨기거나 제거한 표시만. 삭제 원문을 대화로 되살리지 않음 | 해당 파생 문맥 사용 불가 |

Entry 수정으로 전역 policy_revision이 바뀌었다는 이유만으로 수일 전 대화를 영구
불능으로 만들지 않는다. 새 사용자 동작 시작 시 metadata로 실제 의존성을 다시 검사해
일치하면 현재 revision으로 snapshot을 만든다. 동작 중에는 그 revision을 고정하고
각 전송/최종 저장 전 재검사한다. config가 달라져도 표시 답변은 바꾸지 않는다.
알려진 저장 format의 bounded text는 검증해 새 설정의 대화로 쓸 수 있으며, 알 수
없는 format만 재사용 차단한다. 과거 config hash 일치를 재로그인 조건으로 요구하지 않는다.

재사용 불가인 답변을 조용히 제외하고 대명사 질문에 답하지 않는다. UI에서 어느
문맥이 막혔는지 알리고 ‘새 문맥으로 질문’을 제공한다. 이는 같은 대화의 epoch를
올리는 명시적 동작이다. 새 질문은 독립적으로 작성하게 하고 이전 assistant/해석
텍스트는 포함하지 않는다. 과거 이력은 남고, 과거 근거를 새 버전으로 자동 치환하지 않는다.

`source_history.delete_record`/retained-version purge 경로에 최소 cleanup hook을 넣어,
원문 삭제 트랜잭션 안에서 TurnSource 역조회로 direct/inherited 파생 assistant body,
resolved_q/pending clarification을 NULL/redacted로 만들고 진행 중 단계를 막는다.
사용자가 직접 입력한 원래 질문/제목은 독립 작성 기록이므로 자동 제거 대상과 구분한다.
대화 전체를 지우면 이 사용자 텍스트도 삭제된다. AI 제외는 로컬 열람권한을 자동
박탈하는 것이 아니므로 저장 이력 삭제와 구분하되 재전송은 항상 차단한다.
역참조가 없거나 잘못된 경우에도 GET/dispatch의 metadata gate가 최종적으로 차단한다.

## 5. API와 저장된 사용자 동작

신규 `app/api/answer_conversations.py`, `app/schemas/answer_conversation.py`를 추가한다.
기존 `/answers`, `/semantic/search`, `/answers/recommendations`의 독립 요청 계약은
유지한다. HTTP handler끼리 호출/내부 HTTP/평가용 monkeypatch를 쓰지 않는다.
현재 query/recommend/answer의 작은 서비스만 재사용/필요한 부분만 추출한다.

| 경로 | 동작 |
| --- | --- |
| `POST /answer-conversations` | owner의 빈 대화 생성, 필터 고정. provider0 |
| `GET /answer-conversations` | 본인 목록 cursor pagination(50개), 제목/날짜/상태. provider0 |
| `GET /answer-conversations/{id}` | owner 상세·턴50개/가용성·안정 인용, unfinished turn_id/state/lease_expires_at/action_expires_at. provider0 |
| `POST /answer-conversations/{id}/close`, `/reopen` | 종료/재개, id+expected_revision 검사. provider0 |
| `DELETE /answer-conversations/{id}` | 본인 대화/턴 삭제, provider0 |
| `POST /answer-conversations/{id}/turns` | q≤256자, request_id, expected_revision, base_turn_id?, context_mode=continue|fresh, confirm_external_ai=true. 사용자 질문·고정 동작을 DB에 claim |
| `POST /answer-conversations/{id}/turns/{turn_id}/plan` | 동일 request_id+명시 동의. 최초/fresh는 로컬 search 계획; 후속은 planner 최대1회 |
| `POST .../turns/{turn_id}/search` | search분기만. query embedding1회→로컬 Semantic→서버 내부 근거선택/저장 |
| `POST .../turns/{turn_id}/evidence` | reuse분기만. DB의 evidence reference 턴 근거 재확인/선택, provider0 |
| `POST .../turns/{turn_id}/answer` | ready 분기, DB 고정 snapshot/선택근거로 answer1회→정산→parse→DB 저장 |
| `POST .../turns/{turn_id}/stop` | 재접속 후 lease 만료 전에도 자기 unfinished turn을 즉시 stopped로 전환, 이후 단계 차단, provider0 |
| `POST .../turns/{turn_id}/interrupt` | 만료된 lease/action을 로컬 interrupted로 정리, 모델 재호출/회계 수정0 |

각 nested 조회/단계는 `(conversation_id,user_id,turn_id,request_id)`를 모두 검증하며
foreign/not-found는404로 통일한다. 단계별 confirm_external_ai=true와 DB의 동의 계약
버전/scope 일치가 필요하다. 대화 생성/읽기/재개는 외부 전송에 대한 동의가 아니다.
클라이언트가 resolved_q·history·답변·source IDs·필터를 임의로 전달하지 않게 한다.

첫 Search & ask 전송 시 새 대화와 첫 turn을 만든다. 첫 query/answer는 기존처럼
최대2호출이다. 사용자가 링크를 열거나 재로그인했다는 이유로 새 turn/provider를
실행하지 않는다. 상세 GET에서 복원된 대화의 다음 입력은 새 명시적 동의를 받는다.

### 순서·동시 요청·재실행

conversation row의 짧은 FOR UPDATE 트랜잭션에서 expected_revision과 unfinished
turn 유무를 검사하고 seq/epoch·context를 결정한다. 같은 request_id 재POST는 기존
turn/status를 반환할 뿐 paid stage를 재실행하지 않는다. 다른 request_id의 동시
후속 질문은409로 충돌을 알린다. 클라이언트는 자동 재제출하지 않는다.
base_turn_id는 같은 대화의 앞선 완료·열람가능 답변으로 제한하며 branch를 만들지
않는다. transcript seq는 그대로 늘고 어떤 답변에 이어 물었는지 표시한다.

claim 시 DB에 evidence_reference_turn_id를 고정한다. 선택 우선순위는 다음과 같다.
1. 명시적 base_turn_id(같은 대화의 completed 일반 답변; foreign/미완료/없는ID는 거부).
2. 진행 중인 pending clarification의 기준 일반 답변 turn_id.
3. 현재 context_epoch의 direct_selected 근거가 있는 가장 최근 completed 일반 답변.

선택한 기준 턴의 direct_selected 전체를 reuse/구근거 결합 후보로 사용하고, 그 턴의
inherited까지 이번 turn의 의존성에 복사·검증한다. 하나라도 재사용불가이면 오래된
다른 턴으로 조용히 fallback하지 않고409+새 문맥 안내다. 후보가 전혀 없는 경우만
reference=null로 기록한다. no_evidence는 source가 없다고 기존 reference를 지우지
않고, clarify도 자신의 기준 reference를 보존한다. 명시적 base가 있으면 무관한
pending/최근답변을 합치지 않고 그 base와 해당 epoch의 최초 질문을 우선한다.
context_root_turn_id에 이 최초 질문을 저장해 다음 턴도 같은 주제를 해석하도록 한다.
대화의 source/date filters는 바꾸지 않고 seq는 선형으로 유지한다. 명시적 base가
없고 최근 이력이 다른epoch이면 현재epoch만 사용한다. fresh는 prior history/reference를
상속하지 않고 현재 독립 질문을 새 root로 삼는다.

DB turn state는 created→planning→planned→searching 또는 selecting→ready→answering→
completed이며, clarification/no_evidence는 해당 단계에서 completed가 된다.
failed/stopped/interrupted도 terminal이고 이력에는 남지만 모델 대화에 넣지 않는다.
state/outcome을 DB CheckConstraint로 제한하고 전환은 조건부 UPDATE/CAS로 검사한다.
lease와 단계별 once marker를 commit한 **뒤** reserve/dispatch한다. marker가 있으면
released usage 행도 같은 stage를 재시도할 수 없다. ledger의 active-only call count에만
의존하지 않는다. model 호출 중 conversation row lock을 오래 잡고 있지 않는다.

브라우저는 위 단계별 POST를 await한다. Stop/이탈/로그아웃은 fetch를 abort하고
가능하면 stop POST도 보낸다. 서버는 매 단계 시작/전송 직전/결과 저장 때 중단·삭제를
확인한다. 이미 dispatch 권한/intent를 획득한 단계는 발송·완료·과금될 수 있다. stop은
그 전송을 철회한다고 보장하지 않으며, stopped 이후 새로운 단계는 시작하지 않는다. stop POST 실패/탭 강제종료 때도
다음 단계는 브라우저가 호출하지 않으며 서버에 자동 연결 작업/worker는 없다.

각 stage lease는 provider timeout보다 긴120초 후보다. 만료+진행 중이면 재접속의
명시적 interrupt POST에서 interrupted로 전환한다(DB 로컬 상태갱신만, 모델 재호출0).
회계행은 수정하지 않고 spent/uncertain을 그대로 표시한다.
재접속 직후에는 lease 만료를 기다리지 않아도 상세 GET의 unfinished 정보를 보고
‘진행 중 질문 중단’을 누를 수 있다. stop은 해당 unfinished 턴을 row lock/CAS로 즉시
terminal로 만든다. 이전 요청을 인메모리에서 기억할 필요가 없다. 이미 네트워크로
보낸 provider는 정산될 수 있지만 늦은 body는 폐기한다. 다른 active paid call이 아직
billing slot을 점유하면 새 질문의 전송은 busy로 차단하고 자동 반복하지 않는다.
created/planned/ready처럼 아직 다음 stage를 안 부른 턴도 stop 가능하다.
action_expires_at은 claim 시 고정한90초 후보이며 새 dispatch마다 서버도 확인한다.
만료된 action/lease는 interrupt POST로 닫고 다음 질문은 새 동작으로만 시작한다.
자동 갱신되는 lease로 영구 미완료 질문을 만들지 않는다. 결과 저장 전에 서버가
죽었으면 ‘과금될 수 있지만 저장된 답변 없음’을 알린다. 자동 복구·retry/resume은 없다.
다음 질문은 새 request_id/동의로 가능하며 미확정 사용량은 기존 예산에 계속 포함된다.

### 영속화 경계와 근거의 역할

claim transaction에서 원래 질문·filters·동의·선택 history IDs와 그 턴들의 모든
전이적 source anchors를 inherited=true로 먼저 복사한다. body 읽기/예약 전에
이 후보 metadata를 검증한다. 사용자가 지정한 base/pending 턴도 포함한다.
각 단계는 저장돼 있다는 이유로 유효하다고 간주하지 않고 아래 순서를 다시 적용한다.

| 시점 | 재검사·저장 |
| --- | --- |
| plan 직전/dispatch | inherited 전체 owner/version/AI gate 재검사 후 허용된 history만 읽고 전송 |
| search query dispatch | inherited 전체 재검사, 같은 action의 resolved_q만 전송 |
| search 검색후 구근거 결합 | 새 검색 후보+evidence reference의 direct_selected metadata 모두 현재 검사 후 body 읽기·full source byte선택 |
| reuse evidence | inherited 전체와 evidence reference의 direct_selected anchors를 재검사 후 body 선택 |
| 선택 확정 | 이번 선택 anchors를 direct_selected=true로 DB 저장; 같은 anchor가 inherited이면 두 flag를 함께 유지 |
| answer dispatch | inherited+direct_selected 합집합 재검사, 실제 payload/선택hash와 고정 snapshot 일치 확인 |

직접 선택/전송 예정 근거와 상속 의존성은 하나의 exclusive enum으로 표현하지 않는다.
dispatch_intent는 전송 직전의 보수적 표식이며 crash 시 실제 전송을 증명하지 않는다.
실제 회수된 provider output/ledger가 없는 요청을 성공 전송으로 보고하지 않는다.
cited는 성공한 결과의 인용만 final commit에서 설정한다. 선택했지만 미전송인 anchor도
안전하게 의존성에 남길 수 있으며, 이미 저장된 anchor를 새 버전으로 갱신하지 않는다.
유효 usage는 기존 ledger에서 spent로 확정한 뒤 parse한다. 출력 계약 실패는 실패로
표시하고 본문을 저장하지 않으며 과금은 보존한다. 답변 저장 실패도 자동 재생성하지 않는다.
마지막 저장에서는 owner shared lock→conversation/turn lock 순서로 생존·revision·
의존성·stage marker를 다시 검사하고, 완성 답변+안정 인용+completed+대화revision을
한 DB transaction으로 commit한다. 저장 성공 전에는 HTTP 성공 답변을 노출하지 않는다.
동시 대화/원문 삭제가 먼저 이기면 body는 폐기하고 회계만 남긴다. 삭제 후 upsert 금지.

## 6. 후속 해석·근거 선택·모델 입력

새 `followup_transport.py`, `followup_call.py`를 작은 독립 모듈로 만든다.
매 요청의 DB snapshot에서 현재 q, epoch 최초 질문, 최근2개 완료 응답과 선택한
base answer/필수 pending clarification을 구성한다. 이전 답변은 지시나 근거가 아닌
대화 해석 자료다. 원문 본문/전체 provider payload/소유자정보를 planner에 보내지 않는다.
파생 대화도 private data이므로 모델 전송 전에 모든 관련 의존성 gate를 적용한다.

planner JSON은 anyOf 세 분기만 허용한다:
- reuse + resolved_question(1–256자): 기존 근거의 재설명/비교.
- search + resolved_question(1–256자): 다른 사실/후속 기록 탐색.
- clarify + question(1–200자): 어느 대상을 말하는지 불명확.

중복 complete/status/citation 배열은 없다. 대명사/생략만 풀고 원래 요청에 없던
조건/검증 의무·필터를 추가하지 않도록 한다. 형태 검증은 의미 품질을 보장하지 않는다.
reuse는 근거 충분성 판정이 아니며 답변은 partial/insufficient가 될 수 있다.
clarify는 별도 outcome으로 저장하고 query/answer는0회다. 모호한 원래 q·기준답변
turn ID·최신 확인질문을 pending으로 보관해 다음 짧은 답변과 연결한다. 연속 clarify도
매번 사용자 동작/동의·planner1회이며 무한 자동 루프가 아니다.
직전 pending clarification이나 그 기준답변이 수정/AI제외/삭제 때문에 재사용불가이면
continue의 turn claim 및 plan gate는409 `CONVERSATION_CONTEXT_UNAVAILABLE`로
차단한다. 짧은 ‘첫 번째 거’를 독립질문으로 바꿔 모델에 보내지 않는다. 이미 claim된
후에 변경되면 해당 turn을 안전한 실패로 닫고 호출0/이전 비용 보존으로 표시한다.
UI는 pending 질문을 입력 대상으로 사용하지 않고 변경 사유와 context_mode=fresh의
독립 질문 안내를 보여준다. redacted 된 확인질문은 다시 복원하지 않는다.

검색은 resolved_question만 embedding하여 기존 query256자/2048byte 상한을 유지한다.
검색 순위 후보는 클라이언트를 왕복하지 않고 같은 서버 단계 안에서 full parent로
선택한다. 새 검색 후보를 우선하고 evidence reference 턴 근거의 중복되지 않는 후보를 뒤에 결합한다.
reuse는 고정 evidence reference 턴의 direct_selected anchors를 현재 허용 projection으로
다시 해석해 원문을 읽는다. 단순히 직전 seq의 근거를 가져오지 않는다.
원문을 최신 버전으로 조용히 치환하거나 재인덱싱하지 않는다.

no_hits/byte_limit/no_usable_evidence는 provider 오류와 구분한 no_evidence 완료 턴으로
저장하고 답변 생성은0회다. 서버의 범위 한정 안내를 표시하며 다음 질문은 이어갈 수
있다. 기존 의존성은 유지하고 새 source를 발견한 것처럼 표시하지 않는다.
해석 오류/전송/usage 오류·권한 변경은 동작 종료, 자동 search/재생성 fallback은 없다.

일반 provider 출력은 기존 part-results-v3를 유지한다. `payload(..., dialogue=None)`의
None이면 기존 wire와 지침을 유지하고, dialogue 전용 지침/structured history를 별도로
덧붙인다. narrative모드와 dialogue를 혼합하면 오류다. 이번 claims의 ID/quote는
**이번에 보낸 excerpts**에서만 가져오고 예전 인용을 자동 이월하지 않는다.
‘아까 뭐라고 답했어?’ 같은 기록 자체 확인은 저장 대화 UI로 안내하며 무인용 supported
자유챗 계약을 함께 만들지 않는다.

## 7. 문맥 길이·버전·표시 UI

**보관 이력은 오래 유지하되, 매번 전체를 모델에 보내지 않는다.** 최근2턴·epoch 최초
질문·선택된 base answer·필수 pending을 최대8KiB history 후보에 구성한다.
중복 turn은 한 번만 넣고, 초과하면 가장 오래된 선택적 턴 전체를 제외해 context_summary에
실제 보낸 턴/제외 이유를 표시한다. 필수 base/pending조차 못 넣으면 무전송 오류와
독립 질문/새 문맥 안내를 제공한다. 저장된 이력을 절단하거나 자동 요약하지 않는다.

모델 wire 상한 후보:
- 사용자 질문256자/2048bytes 유지. planner full request12KiB/output1024 후보.
- answer full request14KiB/output4096 후보, sources≤5·각full parent≤2000자.
- `choose_parents`가 history 포함 실제 payload로 byte/count budget을 검사한다.
  원문/문장 중간 절단 금지. 제외 근거는 omissions로 공개,0개면 answer 호출0.
- 새로운 conversations POST/PATCH의 HTTP body64KiB streaming cap을 JSON decode 전에
  적용(Content-Length 없음도 포함). 모델 wire 상한과 HTTP 한도를 혼동하지 않는다.
- 기존14,185byte 문맥의 무절단 복사 검사와 합성 최대 한도 검사를 구분한다.
  body 저장 크기/500anchor 증가량/페이지50개 조회 비용도 함께 측정한다.

프론트 신규 `api/answerConversations.ts`, `pages/ConversationsPage.tsx`,
`pages/ConversationPage.tsx`, 필요한 작은 턴/입력 component를 추가한다.
기존 Search & ask의 첫 요청은 새 대화 화면으로 연결하고 URL에는 conversation ID만
남긴다. draft·대화 본문을 URL/localStorage/sessionStorage/분석 로그에 저장하지 않는다.
각 턴에는 인용·원문변경/재사용불가·실행실패/과금가능 상태와 전달 문맥 범위를 표시한다.
답변을 복원하면서 재생성하거나 정상 completed 본문을 조용히 수정하지 않는다.

로그아웃/계정전환은 Abort+쿼리캐시/본문 메모리 폐기만 하고 저장DB는 유지한다.
query key는 계정별로 분리하고401·오류 응답·늦은 다른 세션 결과는 기존처럼 숨긴다.
새 로그인에서 GET으로 다시 owner검증 후 복원한다. access token digest를 DB 대화
소유권으로 쓰지 않는다. 다른 탭에서 진행된 턴/대화삭제는 revision 충돌 후 로컬
refresh로 확인하며 자동 유료 재실행은 없다. 닫기/재개는 provider0인 UI 동작이다.

## 8. 권한·삭제·잠금·회계

매 단계에서 conversation/turn 소유권과 state를 먼저 검사하고 전이적 의존성의
metadata를 current owner/version/record+source AI policy와 대조한다. source body는
이 검사를 통과한 뒤에만 읽는다. 기존 read_citation은 로컬 열람용이므로 AI gate로
간주하지 않는다. planner/query/answer 모두 파생 대화의 검사 대상이다.

동작 중 dispatch는 기존 shared owner lock으로 정책/원문 쓰기와 직렬화한다.
`query_check`, `prepare_payload`에 DB snapshot/관련 의존성 검사를 연결한다.
source writer는 기존 exclusive owner lock→conversation/turn cleanup lock 순서를
지킨다. source 검사/final 저장은 shared owner lock→conversation/turn lock 순서다.
대화 전용 stop/close/delete는 source body를 읽거나 바꾸지 않으므로 owner-exclusive
lock을 얻지 않고 owner조건+conversation→turn row lock만 짧게 쓴다. 이 transaction
안에서 뒤늦게 owner/billing lock을 획득하지 않는다. 진행 중 provider의 owner-shared
lock 때문에 사용자 stop이120초동안 대기하는 구현으로 만들지 않는다. 장시간 row lock 상태에서
별도 connection의 같은 row를 기다리거나 billing lock을 반대 순서로 획득하지 않는다.
ledger 정산은 owner lock을 풀고 수행하며 final body저장은 다시 current검사를 한다.

followup은 실제 생성 호출이므로 ai_usage의 허용 purpose/priced/출력상한/정산/
reconcile/summary에 별도 분기를 추가한다. 기존String(16)purpose에는 새 enum migration이
필요 없지만 대화3테이블의 migration은 필수다. 기존 회계행/모델 가격/불확실 과금을
재분류하지 않는다. config/profile과 request별 output bound를 ledger에 저장한다.

로컬 코드의 Luna 입력0.10/출력0.50 USD per million, bytes+1024 예약을 기준으로
planner12KiB+1024입력/output1024의 보수 예약은1844microUSD다.

| 사용자 질문 경로 | 최대 외부 호출 | 단계 합계 상한 후보 |
| --- | ---: | ---: |
| 최초/fresh 질문 | query+answer=2 | USD0.011 |
| 후속 reuse | planner+answer=2 | USD0.011844 |
| 후속 search | planner+query+answer=3 | USD0.012844 |
| clarify | planner=1 | USD0.001844 |
| 대화 열기/재개/종료/삭제 | 0 | USD0 |

금액은 구현 시 payload/가격hash와 함께 재검증할 후보이며 실행 승인이 아니다.
각 stage run_id는 owner+conversation+turn+action+단계 domain으로 분리하고 최대1회,
월예산/동시실행slot/uncertain 보호를 유지한다. 단계 사이 예산이 소진되면 중단하고
이미 낸 비용은 보존한다. 같은 stage의 자동 retry/resume은 없다.

저장 사실과 외부 전송 동의는 UI에서 구분한다. 질문 전송마다 q·제한된 저장대화·
필요시 검색·최대5개 허용원문의 전송 범위/호출상한을 고지한다. 예전 전송 동의가
재로그인 후 새 질문을 승인하지 않는다. 고정 source/date scope를 넓히거나 mode를
바꾸려면 새 대화를 만들며 새 범위 동의를 받는다. source 권한을 자동 확장하지 않는다.
총 browser deadline90초 후보, provider timeout/DB deadline과 각각 검사한다.
로그아웃/abort가 이미 시작된 요청·정산을 되돌린다는 약속을 하지 않는다.

## 9. 구현 순서와 회귀·검증

한 기능 안의 작업 순서이며, 매 단위마다 유료 소액 실험/별도 승인으로 잘게 나누지
않는다. 현재 요청은 **계획 수정/리뷰만**이다.

1. 모델/schema/Alembic:3테이블·FK/unique/partial index·본문상한·소유권 쿼리.
   새 schema에서 head upgrade/기존 사용자 무변경/DB제약/삭제cascade 검증.
2. CRUD/복원/삭제+상태머신:owner query·pagination·revision/once/lease·원문삭제 hook,
   단계별 성공/중단/서버죽음·재접속 조회/정리 테스트까지 먼저 만든다.
3. planner/정산+query/evidence/answer 연결:작은 서비스 추출, DB snapshot gate,
   일반 optional history·full source budget·완료 결과 원자 저장.
4. UI:목록/상세 route·Search연결·턴입력/되묻기·원문·닫기/재개/삭제·로그아웃 복원.
   OpenAPI로 TS types재생성, legacy 단일질문/manual/period/history 유지.
5. 합성 end-to-end/browser·관련/전체검사 완료 후 결과 제시. 실사용자는
   대화→로그아웃→재로그인→목록→후속질문·다른계정 차단·삭제를 확인한다.
   실제 모델 검증은 별도 동결 요청/시나리오/횟수·비용·중단정책 승인 후만 수행한다.

| 검증 | 필수 행동 |
| --- | --- |
| DB/CRUD | upgrade, composite owner FK, request/seq unique,unfinished partial index, list/detail pagination, turn/source cascade, 회계 유지 |
| 재접속 | DB Session/서버를 새로 만들어도 completed 이력 복원; logout/expired access token/재로그인/닫기·재개 후 후속질문; GET provider0 |
| IDOR | foreign conversation/turn/base IDs/cursor/stage 조합 차단, 모델 호출/본문 노출0 |
| 순서/과금 | 동시2탭/중복POST/단계역순/같은ID 재요청/lease전 재접속 stop(실행중 provider의 owner lock에 장기대기 안 함)/lease만료/서버죽음; paid stage≤1, noresume, uncertain 유지 |
| DB저장 실패 | spent 이후 parse/commit실패 원본재생성0, 늦은응답이 삭제된 대화를 복구하지 않음 |
| 출처/파생물 | 비인용 원문 및 여러턴전 inherited의 제외/수정/삭제가 planner/query/answer를 차단; 삭제시파생본문redact |
| 과거 표시 | 버전변경은 옛답변 표시+badge, source없으면 표시제한; Passage backfill후 stable citation 유지 |
| 대화 해석 | A/B와첫번째/그업체, 오래된base와다른epoch 지정, reference 우선순위/가용성 차단, 연속clarify/짧은확인, no_evidence뒤 이어묻기; 이전오답을 사실로승격 안함; pending 중 source 수정/AI제외/삭제 시409·모델0 |
| 용량 | recent2+base/pending/history8KiB/planner12KiB/answer14KiB/원문무절단/500anchor/큰페이지와본문 cap |
| UI | 모바일,새대화/닫기/재개/삭제/다른계정캐시/late응답/Stop/가용성off, 원문링크에서복귀 provider0 |
| 회귀 | answer/usage/reconcile/questionflow/recommend/semantic/period/history/source권한, 전체backend/frontend·lint/build/diff |

합성 transport/browser는 외부답변/embedding 전송0, AI제외 개인원문 읽기0,
추가import/인덱싱0으로 수행한다. 합성통과를 실제 문맥해석·검색·의미품질로 주장하지 않는다.
영속화된 오류도 없애지 않고 안전한 상태/비용으로 남겨 사용자가 구분할 수 있게 한다.

commit 후보는 DB+CRUD/tests → 보호/정산+서비스/tests → UI/통합검증/문서다.
독립 호환을 유지 못하면 backend 단위를 합친다. 사용자 승인 없이 커밋하지 않는다.
계획 확정 후 현재 문서만의 checkpoint: `docs: plan persistent conversational answers`.
구현에서 실제 채택한 보관/삭제 결정을 DECISIONS, 상태를 CURRENT,
재로그인 사용자흐름/한계를 UNIFIED_ANSWER에 기록한다. Phase3.3 미완료/Phase4 미착수.

## 10. 개정과 리뷰 상태

이전 개정1은 탭메모리/서명토큰·30분/6턴 방식의 계획이었다. 그 계획의 리뷰 결과는
DB 영속화 방식이 검증됐다는 뜻이 아니다. 이번 사용자의 명시적 요청에 따라3테이블/
owner별 저장·로그아웃 후 복원·삭제/회계·경합 계획으로 교체했다.

이번 개정2를 Antigravity `--sandbox --mode plan` compact 모드로 새로2회 검토했다.
- 1차3지적 모두 채택: claim/plan/search/evidence/answer의 source 저장·flag·gate 시점,
  재접속 직후 unfinished 조회/lease전 stop, 유효성 잃은 pending의409 차단을 구체화했다.
- 2차1지적 채택: 오래된base/clarify/no_evidence 뒤의 evidence reference 우선순위와
  기준 턴 전이적 의존성·context root 보존을 고정했다.
- 재접속 stop을 구현할 때 대화 전용 상태변경은 source writer의 exclusive owner lock을
  기다리지 않도록 잠금 순서를 추가 점검했다. 실제 단위 테스트 항목에도 포함했다.

총4지적/4반영/미채택0/사용자 결정이 필요한 미해결 reviewer 지적0. 2차 반영 뒤에는
3차 리뷰를 돌리지 않고 계획의 연결점·폐기된 탭 제한 잔재·상한/비용/필수흐름과 diff를
정적으로 확인했다. 이는 migration/API/browser/실제 모델의 실행 검증이 아니다.
리뷰어에게 계획과 최소 코드 맥락만 주었고 private 원문·DB·비밀 설정은 읽거나 보내지
않았다. reviewer 상세 prompt/output/codex_reviews 파일은 만들지 않는다.
위 계획 작성/리뷰 단계에서는 제품 코드·기존 문서·비공개 검증 원본/회계를 변경하지 않았다.
이후 사용자의 문서 정렬 요청으로 README·ROADMAP·CURRENT·DECISIONS와 답변 사용/
완료 계획 문서에 이 설계 방향과 미구현 상태를 반영했다. 기본 결정은 DECISIONS의
2026-10-20 persisted-conversation 항목, 구현 명세는 이 문서를 기준으로 한다.
제품 구현·새 유료 실험·과거 점수/원본 수정은 포함하지 않는다.
