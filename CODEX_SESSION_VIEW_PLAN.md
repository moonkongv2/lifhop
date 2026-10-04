# Codex 세션 보기와 AI 메시지 구분 구현 계획

작성일: 2026-10-04
상태: 구현 및 로컬 검증 완료, 사용자 브라우저 확인 대기. 계획 커밋 `bdfcd57`.
Antigravity compact plan review 1회 완료, 유효한 지적 3건 반영.
기준 커밋: `63f0c1a` (Phase 2.3 구현 `36de1de`).

## 1. 목표와 사용자 흐름

Codex 기록을 세션 단위로 찾아 읽고, 질문에 대한 최종 답변과 작업 과정을
구분한다. PostgreSQL에는 기존처럼 turn별 Entry와 관측 버전을 유지한다.

1. Entries에서 Codex 세션 카드를 연다.
2. 세션의 사용자 요청·최종 답변을 turn 순서대로 읽는다.
3. 필요한 turn의 작업 과정을 펼쳐 진행 설명·명령 결과·diff를 확인한다.
4. Search에서 일치한 turn을 찾아 그 세션의 해당 위치로 이동한다.
5. 기존 turn별 주석·버전 확인·삭제·AI 설정을 이용하고 목록으로 돌아간다.

완료 조건:

- 같은 소유자·출처·source_scope·thread_id의 현재 남아 있는 Codex Entries가
  한 세션 카드로 표시된다. 다른 Mac/계정/fork는 합쳐지지 않는다.
- 목록 페이지는 서버가 세션으로 묶은 후 계산한다. 여러 페이지의 turn을
  프런트엔드에서 임시로 합치는 방식은 사용하지 않는다.
- 확인된 final_answer는 기본 본문, commentary는 펼칠 수 있는 작업 과정에
  표시한다. phase가 없는 메시지는 구분 불명으로 보존·기본 표시한다.
- 기본 검색은 사용자 메시지·최종 답변·구분 불명 메시지·명령 결과·diff를
  검색한다. Include work commentary 옵션으로 진행 설명까지 검색한다.
- 기록 삭제·주석·버전·권한·수집 재시도와 기존 비 Codex 흐름이 유지된다.
- 옛 preview와 receipt를 변경하지 않고 재실행할 수 있다.

이번 범위는 Codex 보기·검색 보완이다. 세션 전체 삭제/권한/주석, 다른 출처의
세션화, AI 요약·답변, 새 수집 서비스와 자동 수집은 포함하지 않는다.

## 2. 현재 구조와 필요한 변경

| 현재 구조 | 보완 |
| --- | --- |
| `DevSessionPayload`에 thread/turn/fork/archive/order 저장 | assistant message phase와 원본 turn 순서 추가 |
| collector가 모든 agentMessage를 assistant로 저장 | 공식 phase 값을 보존, 미지정/지원 밖 값은 unknown |
| reasoning 등 미지원 항목 수집 제외 | 계속 제외; commentary와 reasoning을 혼동하지 않음 |
| Entry.content와 EntryVersion.content에 전체 정규화 증거 | 유지; 별도 기본 읽기/검색 projection 추가 |
| Entries/Search가 같은 turn 검색 API와 20개 페이지 사용 | Entries용 혼합 세션 목록 API, Search용 turn 검색 유지 |
| payload는 EntryVersion JSONB에 저장 | current_version_id의 payload에서 묶음/읽기 정보를 조회 |
| returnTo가 Entries/Search만 허용 | 세션 이동을 위한 별도 검증된 navigation helper 추가 |

설치 Codex CLI 0.158.0의 공식 생성 스키마에서 agentMessage.phase와 turn 목록
순서를 구현 시 재확인한다. 로컬 임시 생성 스키마가 현재 없으므로 내용은
새로 생성해 확인한다. 새로운 의존성이나 네트워크 문서에 기대지 않는다.

## 3. 메시지와 순서 메타데이터

### AI 메시지

- 공통 CanonicalMessage 전체를 바꾸지 않고 DevSessionPayload에
  `message_phases: {message_id: commentary | final_answer | unknown}`을 추가한다.
- phase는 원본 값을 사용한다. 마지막 메시지, 문장 내용, 길이로 추정하지 않는다.
- 한 turn에 final_answer가 여러 개면 순서대로 전부 표시한다.
- final_answer가 없으면 없는 상태를 표시한다. commentary를 최종 답변으로 승격하지 않는다.
- 사용자 메시지는 항상 기본 내용에 남는다. unknown assistant도 기본 내용에
  남고 Message phase unknown 안내를 표시한다.
- phase는 수집된 assistant ID만 가리킬 수 있다. 잘못된 참조·중복 식별자·
  과도한 metadata 크기는 검증한다. 새 필드도 기존 1 MiB turn 예산에 포함한다.
- `bounded_payload()`가 메시지를 용량 제한으로 제거하면 해당 message_id의
  phase 참조도 동시에 제거한다. trimming 이후 참조 검증과 크기 계산을 다시
  수행하고 그 최종 payload로 digest를 만든다. 정상적인 부분 기록이 남은
  참조 때문에 INVALID_ITEM으로 바뀌지 않아야 한다.

### turn 순서

- `turn_position`을 원본의 오름차순 turn 목록을 처음부터 읽으며 부여한다.
  기간 필터/제외/변환 실패 전에 순번을 잡아 빠진 turn 때문에 순서를 재정의하지 않는다.
- legacy full thread와 paginated turn 목록 모두 동일한 순서 계약을 사용한다.
- 위치는 버전의 관측 메타데이터이며 세션 식별자에 포함하지 않는다.
- 현재 turn들의 위치가 모두 있고 유일하면 그 순서로 표시한다. 누락·중복이
  있으면 원본 순서 확인 불가를 표시하고 알려진 event_at 오름차순, NULL 마지막,
  Entry ID 순으로 안정적으로 정렬한다. 이 대체 순서를 원본 순서라고 부르지 않는다.
- 세션 기간은 알려진 event_at/source_updated_at만 사용한다. 등록 시각을
  원본 시각으로 대체하지 않는다.

## 4. 옛 preview·버전·재수집 호환성

새 metadata는 **없을 때 기존 model_dump에 나타나지 않도록** 직렬화한다.
구체적인 Pydantic serializer 방법은 설치 버전에 맞추되, 아래 byte/digest
계약 테스트를 먼저 작성한다. 공통 conversation/document 출력은 바꾸지 않는다.

- v1 canonical payload의 dump, payload_digest, content_hash가 기존과 동일해야 한다.
- 새 collector parser는 `codex-app-server-0.158.0-turn-v2`로 구분한다.
  bundle format과 filter 정책은 변하지 않으므로 그대로 유지한다.
- client의 지원 parser 목록은 v1/v2를 명시적으로 허용한다. 임의 parser를
  자동 수용하지 않는다. 옛 manifest/checkpoint/receipt는 그대로 사용한다.
- v1 preview의 canonical validation/ACK digest/replay는 같은 결과여야 한다.
- v2 preview는 새 metadata가 들어간 정확한 payload로 다시 검토해야 한다.
- parser 업데이트만으로 source_updated_at을 바꾸거나 최신이라고 주장하지 않는다.
  같은 출처 시각의 v2 증거는 기존 규칙에 따라 retained 후보가 될 수 있다.
  현재 버전을 자동 교체하지 않으며 사용자 버전 선택 후 새 표현을 적용한다.
- 현재 버전이 v1이면 phase와 원본 위치는 unknown이다. 지금까지 저장한 본문을
  재분류해 덮어쓰거나 source 파일 없이 final이라고 추정하지 않는다.

## 5. 저장 본문과 기본 표시/검색 내용

### 원본 보존과 파생 내용

Entry.content/EntryVersion.content/payload/해시는 그대로 유지한다. 읽기 기본 내용은
현재 버전의 payload.order를 순회하며 commentary 메시지만 제외해서 만든다.
사용자·final/unknown assistant·명령·결과·diff·누락 안내는 기존 순서를 유지한다.
작업 과정 펼치기에서는 전체 증거 순서를 읽을 수 있고 commentary임을 표시한다.

검색 때마다 모든 payload를 Python에서 변환하거나, turn 페이지를 가져온 뒤
필터링하지 않도록 `Entry.primary_content` nullable Text 파생 컬럼을 추가한다.

- Codex 현재 버전 선택 시 projection helper로 같은 트랜잭션에서 갱신한다.
- NULL은 projection 불가 또는 비 Codex를 뜻한다. 빈 문자열은 의도된 빈
  projection이며 전체 본문 fallback으로 commentary를 다시 포함하지 않는다.
- 옛 Codex payload는 phase unknown으로 처리하므로 기존 내용을 유지한다.
  payload 자체가 없으면 기존 content fallback과 분류 불가 안내를 사용한다.
- migration은 컬럼과 기존 Codex projection을 채운다. 대량 데이터에는 bounded
  batch를 사용한다. 본문/버전/해시/current pointer/주석/권한은 변경하지 않는다.
- migration의 변환 코드는 당시 규칙으로 고정해 미래 runtime 변경에 좌우되지
  않게 한다. 알려진 phase가 없는 초기 데이터는 안전하게 기존 content를 복사한다.
- `select_version`의 모든 경로에서 새 projection과 current pointer가 일치해야 한다.
  가상의 새 EntryVersion을 만들거나 source freshness 규칙을 우회하지 않는다.
- 향후 AI 검색도 이 구분을 재사용할 수 있지만 이번에 AI 경로를 구현하지 않는다.

### 검색 계약

`GET /entries/search`에 `include_work_commentary=false`를 추가한다.

- Codex: 기본값은 primary_content (NULL일 때만 content fallback), 옵션 true는
  전체 content를 검색한다. 제목 매칭과 기존 literal ILIKE/ranking/date 정책은 유지한다.
- 비 Codex: 기존 검색 결과와 정렬을 유지한다.
- SQL이 검색·total·pagination을 동일한 조건으로 처리한다. 결과 preview도
  검색에 사용한 본문을 써서 기본 결과에 commentary만 보이는 문제를 막는다.
- 검색 응답은 기존 total/items/limit/offset 구조를 유지하고, item만 명시적인
  `EntrySearchItemResponse`로 확장한다. 기존 EntryResponse 필드와 content의
  의미는 유지하고 다음 필드를 추가한다.
  - `preview_text`: 실제 검색 대상 본문에서 만든 길이 제한 preview. 기본
    Codex 검색은 primary_content를 사용하고 NULL일 때만 content로 대체한다.
    include-work=true이면 전체 content를 사용한다. 비 Codex는 기존 content 기준이다.
  - `session_ref: {source_scope, thread_id} | null`: owner에 속한 current version의
    payload에서 검증해 만든다. external_id 분해나 추가 turn별 API 호출로 만들지 않는다.
  - `matched_in_commentary_only: bool`: 옵션 true이며 검색어가 있을 때 전체
    content만 일치하고 제목/기본 본문은 일치하지 않으면 true. filter-only는 false다.
- Search 카드 렌더링은 기존 content 대신 preview_text를 사용한다. 표시 옵션을
  바꿔도 저장 content나 직접 Entry API의 본문 의미는 바뀌지 않는다. 구분 불명
  legacy 내용은 기본 검색/preview에 남는다.
- 옵션 변경은 offset을 초기화하고 URL에 보존한다. 옵션만 설정한 빈 검색은
  실행 조건이 아니다. 명시적 source/type/date 조건은 기존처럼 검색을 실행한다.
- 이번에는 Search를 세션별로 집계하지 않는다. 정확히 일치한 turn을 찾는다.

## 6. 세션 목록 API와 페이지 기준

새 `GET /archive`는 `kind: entry | codex_session` 목록, total, limit, offset을
반환한다. 기존 `/entries` API는 유지한다. `/entries/search`는 pagination wrapper와
기존 Entry 필드를 유지하면서 앞 절의 검색 표시 필드를 추가한다.

- 모든 query는 인증된 owner로 제한한다.
- Codex Entry와 현재 EntryVersion을 join하고, 유효한 thread_id가 있는 기록을
  `(user_id, provider, source_scope, thread_id)`로 GROUP BY 한다.
- thread 식별자가 없거나 지원 가능한 URL 길이를 넘는 기록은 개별 Entry로
  보여주고 세션 분류 불가를 표시한다. external_id 문자열을 분해해 추측하지 않는다.
- 다른 출처와 분류 불가 Codex는 단일 Entry 행으로 UNION ALL 한다. 두 branch의
  조건은 서로 배타적이며 Entry 하나는 정확히 한 행/그룹에 속한다. 그룹의 total과
  결과를 구한 뒤 limit/offset을 적용한다.
- 정렬은 `max(created_at) DESC, max(Entry.id) DESC`로 고정한다. 단일 Entry는
  자신의 created_at/id를 사용한다. session/entry 모두 같은 타입의 숫자 tie-breaker를
  사용하며 배타적인 그룹의 max ID는 서로 다르다. 등록 시각이 같은 batch에서도
  변경 없는 데이터의 페이지가 겹치거나 빠지지 않아야 한다.
  세션 카드가 모두 먼저 나오는 별도 provider 정렬은 사용하지 않는다.
- 카드는 title, scope/thread, retained_turn_count, 알려진 source 기간,
  partial/review 여부, fork 정보, 정렬 불명 여부를 제공한다. 본문 전체는 보내지 않는다.
- 제목은 확인된 원본 순서의 첫 남아 있는 Entry.title을 사용한다. 순서를
  모르면 최초 저장된 남아 있는 Entry.title을 대표 제목으로 사용하고 추정임을 밝힌다.
- 카드의 turn 수는 현재 저장된 수다. 삭제·필터·실패한 source turn을 포함한
  원본 전체 개수나 수집 완료를 의미하지 않는다. 수집 coverage는 Sources의 run에서 확인한다.
- 모든 turn이 삭제되면 세션 카드도 사라진다. 별도 세션/부모 Entry를 만들지 않는다.
- 부분적인 archived/fork metadata 충돌은 임의로 단일 사실로 확정하지 않는다.
  카드가 current evidence로 판단 가능한 정보만 보여준다.
- 초기엔 기존 규모에서 JSONB join/aggregate를 사용한다. EXPLAIN과 합성 다중
  owner 데이터를 확인하고 필요성이 입증될 때만 migration index를 추가한다.

## 7. 세션 상세 API와 화면

브라우저 경로: `/sessions/codex?scope=...&thread=...&focus=ENTRY_ID`.
세션 identity는 scope/thread로 유지해 대표 turn 삭제로 주소가 바뀌지 않게 한다.
ID/검색 조건은 URL encoding하고 길이를 검증한다.

- `GET /codex-sessions/turns?scope=...&thread_id=...&limit=20&offset=...`
  는 summary/turn summaries/total/page 정보를 반환한다. 본문 payload를 20개씩
  통째로 보내지 않는다. 실제 retained turn 수와 source 기간을 사용한다.
- `focus_entry_id`가 있으면 같은 owner/세션 내 위치를 찾아 해당 페이지로 이동한다.
  다른 세션/owner ID로 본문·존재를 유출하지 않는다. 삭제된 focus는 없어진 기록
  안내 후 세션의 첫 남아 있는 페이지를 표시한다. 세션이 비면 404/empty 안내.
- `GET /entries/{id}/presentation`은 해당 current version의 ordered evidence,
  phase/omissions와 버전 ID를 반환한다. 본문은 열린 turn에서 필요할 때만 읽는다.
- turn의 사용자 요청/기본 답변을 표시하고 Work details에 전체 작업 순서를
  보여준다. 첫 진입/focus turn은 열고 나머지는 필요에 따라 연다.
- 기존 EntryHistory/turn actions로 주석·버전·개별 삭제·AI 설정을 제공한다.
  직접 `/entries/{id}` 접근도 동일한 기본 읽기와 작업 과정 구분을 사용한다.
- fork는 별도 세션이며 같은 owner에게 원본 세션이 남아 있을 때만 연결한다.
- 삭제/버전 선택/주석/설정 변경 후 archive·search·session·turn presentation·
  기존 Entry/history cache를 갱신한다. 마지막 page/turn 삭제 시 유효한 위치로 이동한다.
- 세션 상세와 turn 상세의 돌아가기 규칙은 별도 helper에 정의한다. 허용하는
  내부 경로/parameter만 재구성하고 외부 URL, nested returnTo, 임의 pathname을 거부한다.
  Entries/Search origin 조건을 유지하는 session context를 명시적으로 전달한다.
- query key에 scope/thread/page/include-work/current-version을 구분한다. 현재
  logout/account-switch의 전체 private cache 제거와 stale-response 방지를 유지한다.

## 8. 구현 순서와 예상 파일

### A. 표현 메타데이터·호환성

`app/importers/canonical.py`, `app/collectors/bundle.py`, `reader.py`, `codex.py`,
수집 API schema와 관련 tests. v1 hash/receipt regression을 먼저 만든 뒤 v2 metadata를 추가한다.
용량 trimming과 phase map 동시 정리 및 최종 canonical validation도 이 단계에 포함한다.

### B. 기본 본문 projection·검색

`app/models/entry.py`, Alembic migration, 새 `app/services/codex_presentation.py`,
`source_history.py`, `entry_search.py`, API/schema. migration/선택 버전/옵션 검색을 검증한다.
EntrySearchItemResponse와 preview_text/session_ref/matched_in_commentary_only 계약을
구현하고 카드가 실제 검색 대상의 preview를 읽는지 검증한다.

### C. 서버 세션 목록·상세

새 `app/api/codex_sessions.py`, archive API/schema/service, `app/main.py`.
소유권/그룹 total/pagination/focus를 검증한다. existing source/history policy는 재사용한다.

### D. UI·안내·사용자 검증

EntryListPage/EntrySearchPage/EntryDetailPage/EntryResults, 새 세션 reader와 navigation
helper, query/API types, App routes, 기존 CSS, frontend tests.
최소 범위 스타일을 쓰고 새 UI package를 추가하지 않는다. 모든 제품 UI는 영어다.

구현 종료 시 CURRENT.md, CODEX_BACKFILL.md, frontend/README.md에 실제 상태와
검증 절차를 기록하고, DECISIONS.md에 파생 본문/세션 보기 결정을 기록한다.
ROADMAP의 2.3 뒤 UI 보완 순서를 구현 시작 시 반영한다. 계획 검토 중에는 이
계획 파일만 수정한다. 커밋은 사용자 검증 후 A–B/C–D 등 확인 가능한 경계에서 권한다.

## 9. 검증 계획

### backend

- commentary/final/unknown/missing/unrecognized phase, final 0개/여러 개,
  잘못된 phase 참조, 한글/코드/명령/diff/크기 제한.
- v2의 assistant 메시지를 trimming해도 phase map에 orphan ID가 없고 최종
  payload가 canonical validation과 ingestion을 통과하는지 확인한다.
- v1 synthetic preview digest와 receipt가 이전 규칙과 byte-equivalent, 재실행
  동일 결과. 문서/대화/옛 dev_session canonical regression.
- v2 같은 출처 시각 retained → 명시적 버전 선택 → projection 갱신,
  재수집 중복 없음. 주석/AI deny/삭제 suppression 유지.
- migration upgrade, 기존 body/hash/versions/주석/권한 불변, NULL vs 빈 projection.
- commentary에만 있는 단어는 기본 검색 불일치, 옵션으로 일치; unknown은 기본
  검색 가능. total/ranking/pagination/preview/비 Codex/date boundary regression.
- 1세션 25turn + 다른 세션/노트 혼합: 세션은 한 카드, 20그룹씩 페이지,
  동일시각 tie, 서로 다른 owner/Mac/thread/fork/current version 상태.
- session/entry 여러 개가 같은 created_at인 20그룹 경계에서 모든 페이지를
  순회해 ID/세션 중복이나 누락이 없고 반복 호출 순서가 같은지 확인한다.
- 검색 응답의 content는 기존 값, preview_text는 선택한 검색 대상이며 기본
  preview에 알려진 commentary가 없는지 확인한다. session_ref는 current payload에서
  나오고, 작업 과정 전용 일치 표시가 title/primary/filter-only 조건에 맞는지 확인한다.
- legacy thread ID 없음, 순번 누락·중복·시각 NULL, 부분 수집, archived 충돌,
  삭제된 대표/중간/마지막 turn, 마지막 페이지 축소, 서버 focus 이동.
- presentation/session/summary/검색 모든 endpoint owner isolation과 malformed input.
  stale current-version 응답과 선택 버전 기준의 evidence 확인.
- 실제 localhost HTTP + fresh PostgreSQL schema의 합성 v1/v2 ingestion과 화면 API
  연결. 개인 source 내용을 테스트 fixture나 reviewer prompt로 보내지 않는다.

### frontend / browser

- mixed Entries 카드·빈 상태·error/retry·20세션 페이지; manual CRUD regression.
- 기본 final/unknown 표시, Work details 토글, final 없음 안내, 누락/순서 안내.
- Search 기본/옵션/URL/reset/page → 세션 focus → 앞뒤 turn → 목록 복귀.
- 새 탭/reload/back/forward, direct Entry URL, 안전한 return context, 계정 전환.
- turn 삭제·버전 선택 후 관련 목록/카드/reader 업데이트; owner 정책/주석 UI 유지.
- 320/390/768/1440px, 긴 URL/제목/명령/diff, 키보드/접근 가능한 버튼과 heading.
- OpenAPI 타입 갱신, frontend tests/lint/build, backend 전체 suite, git diff --check.

### 사용자 확인

1. 합성 세션에서 기본 답변/작업 과정 구분과 검색 옵션을 확인한다.
2. 같은 세션의 25개 turn이 한 Entries 카드에 묶이고 상세는 페이지를 따라
   읽을 수 있는지, 중간 turn 검색이 정확한 위치로 이동하는지 확인한다.
3. 기존 v1 개인 preview는 보존한다. 실제 phase 확인이 필요하면 동일 범위의
   v2 로컬 preview를 새로 만들고 검토 후 명시적으로 apply한다.
4. retained 후보라면 현재 버전을 선택한 뒤 구분 표시를 확인한다. 개인 기록
   적용/삭제는 자동으로 실행하지 않는다. 현재 실제 개인 apply 여부는 미확인이다.

## 10. 한계와 완료 판단

- phase 없는 옛 메시지는 구분 불명으로 남는다. 수집이 불가능한 원본이나 이미
  빠진 turn을 복원하지 않는다. 위치 fallback은 확인된 원본 순서가 아니다.
- 세션은 현재 남아 있는 기록의 묶음이다. 원본 세션 전체 수집/삭제를 뜻하지 않는다.
- offset 페이지는 concurrent ingestion/deletion으로 이동할 수 있다. 이번에는
  snapshot cursor를 도입하지 않고 유효한 페이지 보정과 안정된 tie-breaker를 제공한다.
- 세션 grouping/JSONB aggregate는 작은 합성 데이터에서 EXPLAIN으로 확인했다.
  실제 대규모 성능은 미검증이다.
- 구현은 로컬 검증까지 완료했다. 개인 기록 적용과 사용자 브라우저 확인은
  남아 있으며, 구현 커밋은 사용자 확인 후 권장한다.

## 11. 계획 검토 결과

- Reviewer: Antigravity, `--sandbox --mode plan`, compact 1회.
- 지적 3건 모두 수용: 검색 응답/preview/세션 참조 계약 명시, trimming 시 phase
  참조 동시 정리, 혼합 목록의 동일시각 정렬 키와 페이지 경계 테스트 구체화.
- 거절/사용자 결정 필요 사항 없음. 추가 loop는 요청하지 않아 실행하지 않았다.
- 검증: 관련 코드와 계획의 계약 대조, plan whitespace 검사, Git 상태 확인.
  계획 검토 당시 이 파일만 추가했으며 앱 테스트·migration·개인 기록 적용·커밋은 하지 않았다.

## 12. 구현 및 검증 결과

- turn별 Entry/버전은 유지하고, 서버에서 현재 기록을 세션 단위로 묶어 페이지를
  계산한다. 검색은 일치한 turn의 세션 페이지로 이동한다.
- 명시적 commentary를 기본 본문/검색에서 분리하고 Work details와 검색 옵션으로
  제공한다. unknown과 명령 결과/diff는 기본 본문에 남는다.
- nullable primary_content migration을 개발 DB에 적용했다. v1 payload/digest와
  기존 버전/본문은 보존하고 현재 버전 선택 시 projection을 갱신한다.
- 공식 스키마와 실제 읽기를 확인한 CLI 0.160.0 지원을 추가했다. 기존 0.158.0과
  v1 preview도 지원한다. 개인 v2 preview는 33turn, commentary 63개/final 32개이며
  서버에 자동 적용하지 않았다.
- 백엔드 244개, 프런트엔드 83개 테스트 통과. lint/build 통과. 실제 localhost
  HTTP와 격리 PostgreSQL에서 25turn 수집/재실행/검색/세션 페이지를 확인했다.
- 합성 API 응답을 사용하는 Chromium에서 320/390/768/1440px 레이아웃과 검색→
  해당 turn→기록→세션→검색 복귀를 확인했다. 실제 개인 기록 UI와 다른 브라우저,
  모바일 기기는 미검증이다.
- 합성 기록 생성 명령과 개인 preview 검토/적용 절차는 `CODEX_BACKFILL.md`에 있다.
