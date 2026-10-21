# 코드 효율·문서 및 파일 정리 작업 계획

작성일: 2026-10-21

상태: 2026-10-21 사용자 지시로 구현 착수. **A 문서·파일 변경 및 자동 검사 완료,
실제 브라우저/사용자 확인 대기. B–E 미착수**.
아래 체크 항목은 완료 표시가 있는 항목만 수행 결과다.
기존 Phase4.1 S1 미커밋 작업은 보존한다. 상세 실행 결과는 11절을 따른다.

## 1. 목표와 제품 단계

사용자가 검색 결과를 열고, 저장 대화를 복원하고, 수집 상태를 확인할 때 발생하는
불필요한 본문 전송·반복 SQL·파일 순회를 줄인다. 동시에 다음 작업자가 현재 상태와
과거 실험 기록을 구분할 수 있도록 문서를 정리한다.

현재 제품 단계는 GitHub collect-now S1 구현 후 사용자 검증 대기다.
[Phase4.1 계획](PHASE41_COLLECTION_PLAN.md)과
[S1 사용 안내](../guides/PHASE41_COLLECTION.md)의 사용자 검증·실제 소스 수집 기준은 유지한다.
예약 실행·재시도, 증분 reconciliation, Codex agent와 A7 검증은 남아 있다.
Phase3.3 조건부 종료의 [D01–D09](../evaluation/phase33/PHASE33_CONDITIONAL_EXIT_PLAN.md)를 이 작업의
성능 개선이나 합성 테스트로 해결됐다고 표시하지 않는다.

이 계획은 유지보수 작업을 정의한다. 제품 milestone 순서를 바꾸거나 S2의 선행 조건으로
모든 최적화를 추가하지 않는다. 권장 순서는 A → B → C이며 D/E는 관련 작업에 묶는다.
각 작업을 독립적으로 검증·제시한 뒤 다음 작업으로 진행한다.

## 2. 감사 기준과 증거의 한계

| 항목 | 감사 및 계획 작성 기준 |
| --- | --- |
| 브랜치 / HEAD | `main` / `b80fa10428ad74d6bdbabaa3c896c66c72425cdb` |
| 로컬 upstream | `origin/main`: `29f346f8a90e3828c28d47eab41c9d397bb5687a`; 로컬 15 ahead / 0 behind |
| 작업 트리 | 기존 추적 파일 수정 11개, 미추적 파일 11개, staged 변경 없음. S1 신규 파일 포함 |
| 감사 범위 | 관련 backend/frontend 호출 경로, 활성 문서 및 관련 이력, CI·생성 파일·파일 참조 |
| 실제 감사 검사 | ESLint 무캐시, TypeScript app/node `--noEmit --incremental false`, Python 287개 AST 문법 검사, `git diff --check` 통과 |
| 미실행 | 테스트·빌드·DB 조회/마이그레이션·성능 측정·실제 수집·AI 호출 |
| 개인 자료 | `.local/` 내용과 `.env` 미열람. 문서에 명시된 용도와 ignored 여부만 확인 |

아래 줄 번호는 위 작업 트리 기준이다. 구현 시작 시 함수명과 실제 호출자를 다시 확인한다.
반복 처리의 존재는 확인됐지만 지연 시간·메모리·비용 절감률은 아직 측정하지 않았다.
문서에 기록된 기존 962/207개 테스트 결과는 이번 감사에서 재실행한 결과가 아니다.

| ID | 확인한 코드 / 호출 경로 | 확인된 비용 |
| --- | --- | --- |
| F1 | `app/services/entry_search.py:87–103` `search_entries`; `app/schemas/entry.py:72–76`; `/entries/search` → `EntryResults` | 전체 Entry와 검색 본문을 읽고 preview를 Python에서 자름. 검색 스키마가 상세 스키마를 상속하여 응답에도 전체 content가 남음 |
| F2 | `app/services/passage_search.py:126–148` `ranked_passages`, `search_passages`; `/passages/search` | 결과마다 passage·aliases·snapshot count 조회. N개 결과에 데이터 SELECT `3 + 3N`; timeout 설정 SQL·인증은 별도 |
| F3 | `app/services/answer_conversations.py:76–110` `view_turn`, `detail`; `conversation_context.py:28–65` `availability` | 최대 50턴에서 출처·가용성·usage를 반복 조회하고 defer한 answer를 개별 로딩. 같은 버전 projection metadata도 반복 조회 |
| F4 | `frontend/src/components/CollectionRuns.tsx:17–19`, `GitHubCollection.tsx:17–24`; `app/services/collection_runs.py:56–65`, `collection_jobs.py:22–26` | 완료 여부와 무관한 5초 polling. run별 receipt 집계, subscription별 최신 job 조회 |
| F5 | `app/workers/collection_worker.py:71–82` `bounded_get`; `app/collectors/github_reader.py:31–69` `get` | 매 GET 전 spool root 순회·크기 합산. reader도 cache/item 크기를 재합산. wrapper는 cache hit에도 실행됨 |
| F6 | `app/services/embedding_jobs.py:97–108` `prepare_indexing`; `embedding_store.py:49–57` `slice_anchors`; `ai_policy.py:69–109` `embedding_inputs` | 같은 parent를 검증·로딩한 뒤 caller가 본문과 start를 다시 조회. PROJECT_EVENT 범위 검증도 반복 가능 |
| F7 | `app/services/answer_evidence.py:49–68` `recommend`; `semantic_search.py:56–66` `read_slice` | 기존 추천 경로에서 slice 검증 후 parent 재조회 및 group key 별도 조회. 최초 ORM 조회에 사용하지 않는 vector 포함 |

## 3. 공통 변경 경계

- owner/auth, source·record AI 정책, current version, deletion/suppression,
  정확한 범위·hash·인용, 과금·동의·멱등성·lease 검증을 보존한다.
- 같은 잠금·트랜잭션 안의 중복 읽기를 줄일 수 있으나, 준비/전송/publication 사이의
  재검증은 합치지 않는다. 권한 캐시를 요청 밖으로 확장하지 않는다.
- 검색 순위·그룹 의미·문자 범위·본문 원문·비용 산정·기존 manifest 계약을 유지한다.
- 새 DB, Redis, OpenSearch, broker, ANN 인덱스나 범용 repository 계층을 도입하지 않는다.
  새 의존성과 스키마 변경은 현재 계획에 필요하지 않다.
- 실제 AI 호출, 개인 소스 수집, 재인덱싱, 권한 변경, AWS provisioning은 작업 검증에 필요 없다.
- 기존 원본·버전·receipt·유료 결과·승인 종료 기록을 정리 대상으로 삼지 않는다.

## 4. 작업 A — 활성 문서 정합화와 확인된 파일 정리

우선순위: P1 문서 정합화, P2 잔여 자산 정리. 앱 코드 최적화와 별도 변경 단위로 진행한다.

후속 정리 완료: [루트 Markdown 배치 계획](DOCUMENTATION_LAYOUT_PLAN.md)은
현재 52개 문서를 분류하고 루트 6개 유지·46개 이동 절차를 정의한다.
46개 이동과 문서 지도·참조 수정이 완료됐다. 기존 A의 브라우저 미검증과 B–E 미착수 상태는 유지한다.

### 변경 범위

1. [CURRENT.md](../../CURRENT.md)의 상단, `Current product slice`, `Next`를 S1 사용자 검증 대기로 맞춘다.
   현재 상태·작동 기능·다음 작업·제약·증거 링크만 남기고, 반복된 과거 실행 이력은
   추적되는 역사 문서로 분리한다. 최초 목표는 활성 안내 약 150줄 이내이며,
   줄 수를 맞추려고 안전·승인·미해결 사항을 생략하지 않는다.
2. 이동 전 inbound 링크와 heading anchor를 조사한다. 역사 본문의 날짜·결과·승인 범위는
   보존하고, 기존 문서에는 새 위치 링크를 둔다. 실험별 상세 문서와 중복되는 서술은
   사실을 변경하지 않는 범위에서 링크로 축약한다.
3. `ROADMAP.md:84–95`의 옛 foundation에 기준 시점을 명시하고 상단/4.1 checkpoint를
   현재 구현과 맞춘다. milestone 순서·범위는 바꾸지 않는다.
4. README의 이미 도입된 기술을 미래 후보에서 현재 스택으로 옮긴다.
   `frontend/README.md:325`의 Markdown 재업로드 설명을 identity/upsert에 맞추고,
   Codex 사용자 확인 여부는 기존 증거의 날짜·범위에 맞춘다.
5. DECISIONS는 결정을 유지하고 superseded/구현 note를 찾기 쉽게 연결한다.
   이번 계획만으로 새 아키텍처 결정을 추가하지 않는다.
6. 참조를 재확인한 뒤 아래 후보만 개별 판단한다.

| 대상 | 처리 기준 |
| --- | --- |
| `frontend/src/App.css`, `src/assets/react.svg`, `vite.svg`, `hero.png`, `frontend/public/icons.svg` | 정적·동적 import, CSS url, HTML, CI·스크립트·문서 참조가 없음을 재확인 후 제거 후보. 실제 Icon은 inline SVG |
| `test_result.txt` | 오래된 62건/6실패 출력. 독자적 장애 증거이면 역사 기록으로 보존하고, 아니면 추적에서 제거. 계속 생성할 필요가 있으면 출력 경로와 정확한 ignore 규칙 정의 |
| `frontend/public/favicon.svg` | index.html에서 사용하므로 유지 |
| 미추적 S1 코드·테스트·migration·안내 | 구현 산출물이므로 유지 |
| schema.ts, package-lock.json, migration chain, fixtures | CI 생성/검사, 설치 재현, 업그레이드 및 테스트 입력에 사용하므로 유지 |
| Phase3 평가·실험 문서, extension 연구 코드 | 실패·설계·연구 증거로 유지. 이동은 필요성과 참조를 확인한 경우만 수행 |
| `.local/`, `.env`, 개발 환경·캐시 | 이 작업에서 열거나 삭제하지 않음. 기존 ignore 규칙 유지 |

### 완료·검증 기준

- [x] 현재/다음 단계의 상충 설명이 해소되고 사용자 검증 미완료가 유지된다.
- [x] 역사 문서 이동은 내용 보존을 hash로 확인하고 링크·anchor를 검증한다.
- [x] 삭제 후보의 사용처 검색 결과와 최종 판단을 기록한다.
- [ ] 자산 제거 시 frontend lint/type/build 및 기본 화면 확인을 수행한다.
  lint/type/build와 모킹된 기본 화면 39개 테스트는 통과. 실제 브라우저 확인은 도구 연결 오류로 미완료다.
- [x] 링크·상태 정합성·diff 검사를 수행한다. 자산 삭제도 포함하므로 관련 frontend 검사도 실행했다.

사용자 확인: CURRENT의 현재/다음/제약과 README의 진입 안내를 읽고,
S1 검증 대기와 D01–D09 이월 범위가 명확한지 확인한다.
커밋은 문서 검토 후 권장: `docs: reconcile current status and preserve audit history`.
자산 삭제는 필요하면 별도 `chore: remove unused frontend starter assets`로 나눈다.

## 5. 작업 B — 검색 응답과 Passage 집계 개선 (F1/F2)

우선순위: P1. 두 하위 작업을 독립 검증 가능한 커밋으로 나눈다.

### B1. Exact 검색 요약 응답

- 검색용 요약 스키마를 상세 Entry 응답과 분리하고 표시·navigation에 필요한 필드를 명시한다.
- preview를 SQL substring으로 제한하고 목록에서는 전체 content/primary_content를 로딩하지 않는다.
  검색 조건 자체의 본문 matching은 유지한다.
- 먼저 API 소비자·테스트를 조사한다. content 제거는 공개 스키마 변경이므로 프런트와
  생성 타입을 함께 갱신한다. 기존 상세 GET 및 호환성 보존 대상 `GET /entries`는 유지한다.
- 기존 검색 응답을 필요로 하는 별도 소비자가 발견되면 호환 방식을 정한 뒤 진행한다.
  content를 유지한 채 preview만 줄이고 F1 전체 해결로 표시하지 않는다.

### B2. Passage 결과 집계

- 페이지에 등장한 group ID에 대해서 aliases와 distinct Entry 수를 일괄 계산한다.
- aliases 상한 5개와 순서, snapshot_count, grouping 후 페이지·quota 의미를 유지한다.
- 우선 집계만 배치화한다. 안전한 passage reader 배치화는 추가 이득이 확인될 때 수행한다.
  total과 page를 무조건 단일 window count로 합쳐 빈 페이지의 total을 잃지 않는다.

### 완료·검증 기준

- [ ] 합성 긴 문서의 body 길이를 늘려도 검색 응답은 요약 필드 상한에 따라 제한된다.
- [ ] 검색 SQL의 SELECT 목록에 불필요한 전체 본문이 없고 상세 조회는 원문을 유지한다.
- [ ] B2의 aliases/count SELECT 수가 페이지 결과 수에 비례해 증가하지 않는다.
- [ ] 결과 ID·순위·total·aliases·snapshot_count가 기준 구현과 일치한다.
- [ ] 소유권·stale version·변조 hash·deleted/denied 로컬 검색 계약과 빈 페이지를 검증한다.
- [ ] `tests/test_entry_search.py`, `tests/test_passages.py`, frontend 검색 관련 테스트와
  생성 API 타입 검사를 통과한다.

위험: API 호환성, group 정렬, NULL/Unicode preview, 동시 변경의 일관성.
사용자 확인: 로컬 `/search`에서 Exact/Passages 검색 → 다음 페이지 → 원문 → 뒤로 가기.
결과·원문·navigation은 같고 목록에서 전체 원문을 미리 내려받지 않아야 한다.
커밋은 관련 검증·사용자 확인 후 권장:
`perf: bound entry search summaries`, `perf: batch passage search aggregates`.

## 6. 작업 C — 저장 대화 복원 조회 개선 (F3)

우선순위: P1. 대화 내용과 삭제 가용성 판정 순서를 우선 보존한다.

- 현재 선택 페이지와 unfinished 턴의 합집합에 대해 source/usage를 묶어 읽는다.
- 중복 anchor/version metadata를 요청 내에서 한 번 조회하고 턴별 상태로 매핑한다.
  필요 없는 모든 projection을 읽는 대신 가능한 범위에서 정확한 anchor에 제한한다.
- 삭제 판정이 끝난 뒤 표시 가능한 턴의 answer만 일괄 로딩한다.
- unfinished가 페이지에도 존재하면 동일 view 계산을 재사용하되 응답 shape는 유지한다.
- 전체 대화를 로딩하거나 `availability`의 500-anchor 제한을 무작정 확대하지 않는다.
  페이지 전체 합집합이 제한을 넘으면 bounded batch로 조회하고 턴별 기존 제한은 유지한다.

### 완료·검증 기준

- [ ] 합성 1/10/50턴에서 source/usage/body 쿼리가 턴별로 반복되지 않는다.
  anchor batch 추가분과 고정 조회 수를 구분해 기록한다.
- [ ] deleted answer는 body 조회 및 반환 대상에서 제외되며, updated/excluded의
  기존 조회 허용 의미는 바뀌지 않는다.
- [ ] 재열기·페이지 이동·다른 계정·삭제·정책 변경·unfinished·usage 응답이 동일하다.
- [ ] GET에서 provider 호출·유료 단계 재실행이 0임을 stub으로 확인한다.
- [ ] `tests/test_answer_conversations.py` 및 frontend conversations 관련 회귀를 통과한다.

위험: metadata gate 이전 본문 로딩, anchor 상한 의미 변화, unfinished 중복/누락.
사용자 확인: 합성 저장 대화의 닫기·재열기·과거 페이지 읽기와 삭제된 근거 표시.
커밋은 검증·사용자 확인 후 권장: `perf: batch saved conversation detail reads`.

## 7. 작업 D — 수집 상태 조회와 spool 계산 개선 (F4/F5)

우선순위: P2. S1 사용자 검증과 S2 준비에 맞춰 수행하고 D1/D2를 나눈다.

### D1. 상태 조회

- 선택 페이지 run ID들의 receipt outcome을 한 번에 집계한다.
- subscription별 최신 job을 묶어 조회한다. 빈 job·빈 count의 응답은 기존과 같게 한다.
- 활성 작업은 5초 갱신을 유지하고 유휴 상태는 느린 polling(초기 후보 30초)으로 전환한다.
  별도 worker나 다른 탭이 시작한 작업을 발견할 수 있도록 polling을 완전히 끄지 않는다.
- collect/cancel 성공, focus 복귀, 수동 refresh 시 즉시 갱신한다.
  독립 query invalidation은 병렬 처리하되 필요한 키를 삭제하지 않는다.

### D2. 파일 용량 계산

- 먼저 가짜 reader·임시 합성 spool로 rglob/stat 횟수와 파일 수별 증가량을 계측한다.
- 현재 전체 쓰기 경로를 조사한다: response cache, item, preparation journal,
  manifest/preview, identity/config, 교체 쓰기와 중단 후 잔여 파일.
- 전체 순회 비용이 유의미하면 기존 단일 spool lock 안에서 초기 재산정 후 통제된 쓰기의
  실제 크기 증감을 반영한다. 새 용량 계산 경로를 쓰기 완료·실패 처리와 함께 검증한다.
- quota·응답 상한 여유·개별 파일 symlink 검증·재시작 재산정은 유지한다.
  외부 변경을 감지/통제할 수 없는 경로는 기존 검사를 유지한다.
- 자동 spool 삭제, 수집 병렬화, 증분 graph 알고리즘 구현은 이 작업에 포함하지 않는다.
  용량 캐시 복잡성이 이득보다 크면 D2는 측정 결과와 함께 보류할 수 있다.

### 완료·검증 기준

- [ ] run/job 목록 SQL 수가 목록 길이에 선형 비례하지 않는다.
- [ ] 가짜 타이머에서 활성/유휴 polling과 즉시 갱신, 외부 시작 작업 발견을 검증한다.
- [ ] D2를 구현하면 GET마다 과거 job 전체 순회가 발생하지 않고, 재시작/교체/쓰기 실패/
  quota 초과/symlink 상황에서도 실제 저장량을 과소평가하지 않는다.
- [ ] lease takeover·cancel·disable/re-enable·중복 receipt·crash replay를 유지한다.
- [ ] collection runs/jobs/collector 테스트와 `GitHubCollection.test.tsx`를 통과한다.

사용자 확인: 합성 Sources 화면에서 collect/cancel/완료/유휴 상태와 갱신 확인.
실제 GitHub 접근은 필요 없다.
커밋은 각 하위 검증 후 권장: `perf: batch collection status reads`,
`perf: avoid repeated collection spool scans`(D2 구현 시).

## 8. 작업 E — 동일 요청의 parent 읽기 재사용 (F6/F7)

우선순위: P2. preview와 기존 추천 경로를 각각 좁게 수정한다.

- indexing preview 내부 helper가 검증된 parent/text/start와 anchors를 함께 전달하도록 한다.
  필요하다면 기존 `slice_anchors` 인터페이스를 wrapper로 보존한다.
- 기존 추천 경로는 vector 대신 필요한 컬럼을 조회하고 slice 검증 결과와 parent를 함께 사용한다.
  같은 parent의 본문 읽기는 요청 안에서만 재사용하며 각 slice hash 검증은 유지한다.
- 새 saved-conversation selection 흐름에 이 리팩토링을 자동 확대하지 않는다.
- 반복 JSON 직렬화는 우선 유지한다. 실제 요청 byte 상한 계산을 추정값으로 대체하지 않는다.

### 완료·검증 기준

- [ ] 동일 parent에 대한 불필요한 재조회가 감소하고 추천 조회에서 vector를 가져오지 않는다.
- [ ] 기존 manifest digest, anchors, input bytes/비용 상한, 추천 순서·omissions가 동일하다.
- [ ] PROJECT_EVENT primary range 검증, allowlist, owner/policy/version/hash 실패가 유지된다.
- [ ] 전송·publication 단계의 독립 재검증과 usage 처리는 변경되지 않는다.
- [ ] embedding jobs/store 및 answer evidence 관련 테스트를 통과한다.

위험: 검증된 값의 수명 확대, 입력 표현 변경에 따른 digest/승인 계약 파손.
사용자 확인: 합성 preview/추천 결과가 이전과 같고 AI 실행 없이 비교 가능함을 확인한다.
커밋은 관련 검증 후 권장: `perf: reuse validated parents within local previews`.

## 9. 검증·측정 절차

아래는 각 작업의 구현 시 절차다. 실제 수행 범위와 결과는 11절에 기록한다.

1. 시작 HEAD·작업 트리와 기존 사용자 변경을 기록한다. 변경된 기준에서는 감사 줄 번호와
   가정을 다시 확인한다. 기존 S1 수정과 최적화 변경을 섞어 덮어쓰지 않는다.
2. 코드 수정 전후 동일 합성 입력으로 결과와 비용을 비교한다.
   SQL은 ORM event로 데이터 SELECT를 세고 DBAPI에서 추가하는 timeout SQL을 별도로 설명한다.
   응답 bytes, 파일 순회/stat 횟수는 직접 측정한다. wall-clock은 동일 환경에서 반복해
   중앙값·범위와 fixture 규모를 기록하며 절감률을 미리 보장하지 않는다.
3. backend fixture는 마이그레이션을 자동 실행한다. 구현 테스트를 실행할 때는 실제 접속 대상이
   disposable `_test` DB인지, 임시 schema 및 cleanup 범위가 제한되는지 먼저 확인한다.
   감사의 read-only 환경에서 그대로 실행하지 않는다. 조건이 없으면 정적 검사까지만 보고한다.
4. AI/AWS/GitHub 경계는 stub 및 외부 네트워크 차단으로 검증한다. `.env`의 실제 key나 개인
   DB를 사용하지 않는다. 임시 합성 파일은 전용 임시 디렉터리에 두고 생성한 것만 정리한다.
5. 관련 테스트, frontend lint/type, 필요 시 build를 실행하고 마지막 통합 시점에 실용적인 범위의
   전체 suite를 수행한다. generated schema 변경은 CI와 같은 생성·diff 경로로 확인한다.
6. 앱 기능 확인은 합성 API/DB로 수행하고 실제 사용자 원문·유료 결과를 출력하지 않는다.
   테스트가 실패하면 제품 assertion, 환경 설정, 기존 실패를 구분해 보고한다.
7. 각 작업 종료 시 diff·Git status와 변경 범위를 확인하고 실제 완료·미완료만 CURRENT에 반영한다.
   알고리즘·계약에 지속 결정이 생긴 경우에만 DECISIONS에 기록한다.

| 결과 기록 항목 | 필수 내용 |
| --- | --- |
| 기준 | before/after commit 또는 작업 트리 식별, 합성 fixture 크기 |
| 동등성 | 결과 ID/순서/응답·manifest·권한 실패 등 비교 범위 |
| 비용 | 데이터 SQL 수, 응답 bytes, 파일 접근 횟수; 필요 시 지연·메모리 |
| 실행 검사 | 정확한 명령·성공/실패·미실행 이유 |
| 사용자 확인 | setup, 로컬 URL/조작, 예상 결과, 남은 확인 |
| 한계 | 실제 corpus/동시성/배포 환경에 대한 미측정 영역 |

기존 [S1 안내](../guides/PHASE41_COLLECTION.md)의 setup을 재사용하되 개인 DB에 합성 데이터를
무단 추가하지 않는다. 필요하면 분리된 합성 환경을 구성한다. S1 승인·Phase3 평가 결과를
성능 작업의 테스트 통과로 대체하지 않는다.

## 10. 최종 완료 기준과 보류 항목

- [ ] A의 활성 안내가 실제 상태와 일치하며 역사·평가 증거와 참조가 보존된다.
- [ ] B/C는 동작·보호 계약 동일성과 반복 조회/응답 크기 개선의 합성 증거를 남긴다.
- [ ] D/E는 구현 완료 또는 측정에 근거한 보류 사유를 구분한다. 보류를 완료로 표시하지 않는다.
- [ ] 신규 인프라·의존성·실제 유료 호출·개인 데이터 변경 없이 변경 목적을 검증한다.
- [ ] 각 작업은 기존 미커밋 S1 구현과 구분되는 review/commit 단위로 제시한다.

대규모 corpus의 vector 검색 실행계획, DB pool/lock 경합, 실제 모바일 브라우저 메모리,
운영 지연·비용은 별도 계측 과제다. 현재 근거만으로 ANN·외부 검색 엔진·전역 캐시를
도입하거나 source 검증을 줄이지 않는다. 사용되지 않는 의존성은 확정되지 않았으며
패키지 일괄 제거·범용 API wrapper 통합·관련 없는 리팩토링은 수행하지 않는다.

## 11. 실행 기록 — A, 2026-10-21

### 변경과 보존

- CURRENT를 2,694줄에서 129줄로 정리했다. S1 사용자 검증 대기, D01–D09,
  미해결 uncertain3건/USD0.006801, 삭제/권한/외부 실행 경계와 운영 제약을 유지했다.
- 변경 직전 CURRENT 전체는 [CURRENT_HISTORY_20261021.md](../history/CURRENT_HISTORY_20261021.md)에 안내 머리말과 함께
  보존했다. snapshot 본문 SHA-256이 작업 시작 원문과 같음을 확인했다.
  같은 루트에 두어 과거 상대 링크를 유지했다. 기존 CURRENT anchor를 직접 참조하는
  저장소 링크는 검색에서 발견되지 않았다.
- README 기술 목록과 ROADMAP의 현재 checkpoint/역사적 foundation을 구분하고,
  frontend README의 Markdown identity 및 Codex 화면 확인 범위를 수정했다.
  DECISIONS에는 기존 구현 note/조건부 종료/S1 결정을 찾는 링크만 추가했다.
- `test_result.txt`는 고유한 과거 실패 출력을 잃지 않도록
  `docs/history/legacy-test-result.txt`로 이동했다. 원문 SHA-256 동일성을 확인했고
  `docs/history/README.md`에 출처와 과거 6실패/56통과의 의미를 설명했다.
  생성·사용 경로가 없으므로 새 ignore 규칙은 추가하지 않았다.
- 사용 참조가 없는 App.css, react.svg, vite.svg, hero.png, public/icons.svg를 제거했다.
  코드·스크립트·CI·HTML과 동적 import/glob·CSS 참조를 재검색했다.
  favicon, index.css, inline Icon, schema/lockfile/migrations/fixtures는 유지했다.
- 시작 시 파일 hash 목록과 비교해 기존 backend/S1 코드·테스트·생성 schema·설정이
  바뀌지 않았음을 확인했다. 개인 `.local/` 자료·환경 설정 내용은 열지 않았다.

### 실제 검사 결과

| 검사 | 결과 |
| --- | --- |
| 원문 보존 | CURRENT snapshot, legacy test output 각각 SHA-256 동일 |
| 로컬 링크/anchor | 수정 안내 문서와 신규 역사 안내 검사 통과 |
| `npm run lint` | 통과 |
| `npm test -- src/pages/entries.test.tsx` | API fetch를 stub한 기본 화면 테스트 39개 통과 |
| `npm run build` | TypeScript 및 Vite build 통과; 기존 규모의 main chunk 504.23kB 경고 |
| diff/파일 범위 | 공백 검사 통과, 기존 S1 코드 변경 없음 |
| 실제 브라우저 | 도구 연결이 sandbox metadata 오류로 시작되지 않아 미검증 |
| backend/외부 실행 | DB/migration, 실제 수집/AI/AWS 호출 및 backend 테스트 미실행 |

최초 보존 스크립트의 비ASCII bytes literal 문법 오류는 실행 전에 실패했고 수정 후
성공했다. 첫 문서 patch의 동일 파일 delete/add 표현도 적용 전 거절됐으며,
CURRENT를 별도로 갱신한 뒤 나머지 patch를 적용했다. 앱 검사 실패는 없었다.

### 사용자 확인과 다음 단계

CURRENT의 현재/다음/제약과 역사 문서 링크를 검토한다. 실제 화면 확인은
`cd frontend && npm run dev` 후 로컬 `/login`의 메뉴·아이콘·폼을 먼저 확인하고,
기존 합성 계정 환경이 있다면 `/entries`와 `/search`의 카드·navigation을 확인한다.
기본 주소는 `http://localhost:5173`이며 새 수집/AI 요청은 필요 없다.
현재 theme/화면은 그대로여야 한다. 실제 브라우저 검증은 자동 검사로 대체 판정하지 않는다.

AGENTS의 slice별 사용자 검증 규칙과 본 계획의 순서에 따라 A 결과를 먼저 제시한다.
다음은 B1/B2이며 아직 구현하지 않았다. 사용자 검토 후 A의 문서/자산을 별도 커밋으로
정리하는 것을 권장한다. 기존 S1 변경과 공유하는 문서 hunk를 확인한 뒤 나누고,
새 snapshot/history 파일을 빠뜨리지 않는다. 현재 커밋은 만들지 않았다.
