# GitHub 저장소별 탐색 구현 계획

작성일: 2026-10-05
기준 커밋: `2a6e874`
상태: 2026-10-06 구현 완료, 사용자 브라우저 확인 대기. Antigravity compact plan review 1회 완료, 지적 3건 반영.

## 1. 목표와 범위

Entries에서 GitHub 기록을 저장소 카드로 묶고, 저장소 안에서 커밋과 문서를
쉽게 탐색한다. 커밋별 Entry와 문서 스냅샷별 Entry는 그대로 보존한다.
검색·향후 AI에서 개별 근거를 찾는 단위와 목록에서 탐색하는 단위를 분리한다.
Phase 2.4A 다음의 UI checkpoint로 진행하고 사용자 확인 후 2.4B로 넘어간다.

완료 기준:

- 같은 저장소의 수백 개 기록이 Entries에서는 하나의 카드로 표시된다.
- 저장소 상세에서 커밋을 실제 기록 날짜순으로 탐색하고 기존 diff reader를 연다.
- 문서는 경로별로 묶어 최근 보관 스냅샷과 과거 스냅샷을 확인한다.
- 검색은 개별 Entry를 반환하며 저장소·날짜·관련 탐색 링크를 제공한다.
- 주석·버전·삭제 suppression·AI 권한·수집 receipt와 기존 Codex 탐색을 유지한다.

AI 요약/제목 생성, 추가 수집, 저장소 전체 삭제/권한 변경, PR/이슈 목록,
새 worker/AWS 서비스/의존성은 이 계획의 범위에 포함하지 않는다.
기존 미커밋 GitHub 인증/검증 보완은 보존하고 이번 UI 변경과 구분한다.

## 2. 현재 구조

| 위치 | 현재 동작 | 변경 |
| --- | --- | --- |
| `app/services/codex_sessions.py::archive` | Codex만 묶고 나머지는 개별 Entry | 공통 archive 조회에 GitHub 저장소 묶음 추가 |
| `app/schemas/codex_session.py::ArchiveItem` | entry / codex_session | github_repository 종류와 요약 응답 추가 |
| `app/api/github_records.py` | 현재 버전 evidence와 같은 SHA 관련 기록 | 저장소 요약/커밋/문서 탐색 API 추가 |
| `app/schemas/entry.py`, `app/services/entry_search.py` | 검색의 Codex session_ref | 현재 버전에서 가벼운 GitHub repository_ref 추출 |
| `ArchiveResults.tsx` | 최근 추가 순 카드와 서버 페이지 | 저장소 카드, 탐색 단위 개수와 정렬 설명 |
| Entry detail / Search / navigation utils | Entries·Search·Codex 복귀 | 저장소 상세 복귀와 검색의 저장소 링크 지원 |

owner → Entry → 해당 Entry의 current_version 순서로 조회한다. 예전 버전의
payload가 별도 저장소나 phantom record를 만들지 않도록 한다.
새 서비스를 추가하더라도 archive에 필요한 부분만 이동하며 Codex 전반을 리팩토링하지 않는다.

## 3. 저장소 카드와 집계

- 묶음 키: authenticated owner + `provider=github` + 검증된
  `source_scope=repo:<numeric_repository_id>`. 이름 변경으로 카드를 분리하지 않는다.
- 현재 payload의 repository_id와 scope 일치를 확인하고 커밋/문서 종류를 분류한다.
  유효한 GitHub scope가 있지만 payload가 유실/비정상인 기록도 저장소의
  `Unclassified` 수에 포함해 별도 목록으로 접근 가능하게 한다.
  scope 자체가 비정상이면 개별 카드에 분류 불가 안내를 남긴다.
- 카드: 저장소 이름, 보관 커밋 수, 문서 경로 수와 스냅샷 수, 보관 기록 기간,
  partial/review 경고. 이름은 최근 보관 관측의 유효한 이름, 없으면 scope로 표시한다.
- 기간은 알려진 event_at의 min/max; 누락 날짜 개수도 표시한다.
  날짜를 payload의 문자열이나 수집 시각으로 추정하지 않는다.
- 개수는 현재 보관 Entry 기준이다. 관측 버전 수나 GitHub 전체 커밋 수가 아니다.
  source-deleted 기록도 보관 중이면 포함하고 표시한다. lifhop에서 삭제하면 제외된다.
  전체 수집 범위/갭은 Sources에 연결해 보여준다.
- Entries 전체는 기존 `Most recently added` 정렬을 유지한다. 저장소 카드의
  위치는 구성 Entry의 max(created_at), 동률은 max(id)로 정한다.
  새 수집이 카드 하나를 올릴 수 있지만 과거 커밋이 개별 최근 카드로 쏟아지지 않는다.
- owner 조건으로 그룹을 만든 뒤 전체 개수와 LIMIT/OFFSET을 적용한다.
  기존 페이지 20개를 가져온 다음 브라우저에서 묶는 방식은 사용하지 않는다.
- Entries의 total은 카드/탐색 단위 수라고 UI에 명시한다.

## 4. 저장소 상세 화면

경로: `/repositories/github?scope=repo:<id>&tab=commits&offset=0&returnTo=...`
URL에 선택 탭과 페이지를 보존한다. 커밋/분류 불가 목록은 `offset`, 문서 경로
목록은 `doc_offset`, 선택한 문서의 스냅샷 목록은 `snapshot_offset`을 사용한다.
문서 선택은 `tab=documents&path=<encoded path>`로 표현한다. 각 값은 기본 0이며
0 이상의 safe integer만 허용한다. 경로 변경 시 snapshot_offset만 0으로 초기화하고
doc_offset은 보존한다. `All documents`는 path/snapshot_offset을 제거해 원래
경로 목록 페이지로 돌아간다. 탭 변경 시 다른 탭 상태는 보존한다.
상단에 이름·보관 기간·개수·Sources 링크,
`Commits`, `Documents`, 필요할 때 `Unclassified` 탭을 둔다.

### 4.1 커밋

- event_at DESC NULLS LAST, id DESC로 서버 페이지를 나눈다. limit 기본 20, 최대 100.
- 날짜 구분은 Asia/Seoul로 표시한다. 같은 날짜가 여러 페이지에 걸릴 수 있음을 허용한다.
  날짜 없는 기록은 `Date unknown`으로 표시한다.
- 각 행에는 메시지 첫 줄을 공백 정리/길이 제한한 제목, 짧은 SHA, 날짜,
  partial/review/source-deleted 상태를 표시한다. 원본 제목·본문은 수정하지 않는다.
- 기본 목록에서 diff/전체 본문을 출력하지 않는다. 행을 누르면 기존 Entry reader를 연다.
- 알려진 날짜가 같은 기록도 id로 순서를 고정하며, Git 토폴로지 순서라고 주장하지 않는다.

### 4.2 문서

- 먼저 path별로 묶은 목록을 서버에서 페이지로 나눈다. path ASC를 기본으로 한다.
  경로는 줄바꿈 가능하게 표시하고 안전한 텍스트로 렌더링한다.
- 경로마다 event_at DESC NULLS LAST, id DESC의 첫 기록을
  `Latest retained snapshot`으로 표시한다. 이것은 서버에 보관한 가장 최근 기록이며
  현재 GitHub 파일이나 선택 브랜치 HEAD의 내용임을 보장하지 않는다.
- 경로를 선택하면 스냅샷 목록을 같은 날짜순으로 별도 서버 페이지로 조회한다.
  각 스냅샷은 날짜·SHA·partial 상태와 기존 문서 reader 링크를 제공한다.
  동일 내용이 다시 등장한 스냅샷도 유지한다. 이름 변경 전후 경로는 합치지 않는다.
- Phase 2.4A의 선택 head/branch와 head-document mapping은 Sources의 수집 범위로
  연결한다. 이 checkpoint에서는 여러 run/branch 중 하나를 자동으로 현재 문서로
  지정하지 않는다. 실제 HEAD 기준 문서 탐색은 별도 기준 선택이 필요한 후속 기능이다.
- 커밋에서 파일 삭제가 보이더라도 최신 보관 스냅샷을 현재 존재하는 파일로 표시하지 않는다.

### 4.3 오류와 빈 상태

로그인 필요, loading, retry 가능한 오류, 각 탭 0건, 존재하지 않는 저장소,
현재 보관 기록이 모두 삭제된 저장소를 처리한다. 타 owner의 저장소는 404다.
페이지가 삭제로 범위를 벗어나면 마지막 유효 페이지로 이동한다.

## 5. API와 보안

기존 `/archive`를 확장하고 다음 owner-scoped GET을 추가한다.

| API | 응답 |
| --- | --- |
| `/github-repositories?scope=...` | 저장소 요약 |
| `/github-repositories/records?scope=...&kind=commit|unclassified&limit=...&offset=...` | 가벼운 기록 요약, total |
| `/github-repositories/documents?scope=...&limit=...&offset=...` | path별 대표 스냅샷과 개수, total |
| `/github-repositories/document-snapshots?scope=...&path=...&limit=...&offset=...` | 해당 path의 기록 요약, total |

scope/path/페이지 입력을 검증한다. 전체 content/files/patch를 목록 API로 보내지 않는다.
source-deleted 상태와 completeness/review 정보를 포함한다. 모든 join은 owner와
Entry/current_version 연결을 검증하며 path 조회도 provider/scope를 함께 제한한다.
목록의 타입 분류는 bounded metadata를 사용하고 실제 evidence reader의 엄격한
검증은 유지한다. 분류 실패는 숨기지 않는다.

검색의 `EntrySearchItemResponse`에 nullable `repository_ref`를 추가한다.
ref는 검증된 source_scope, 표시용 repository 이름(유효하지 않으면 null),
kind(commit/document/unclassified), 문서이면 path를 담는다. search_entries의
현재 버전 조회에서 필요한 metadata만 추출하고 owner/scope 일치를 검사한다.
이름이나 분류가 없더라도 유효한 scope이면 저장소 탐색 링크는 제공할 수 있다.
scope 자체가 비정상이면 ref는 null이다. 검색 결과마다 별도 presentation/저장소
요약 요청을 보내지 않는다. session_ref와 검색 rank/count/pagination 계약은 유지한다.

DB 모델/Entry identity/수집 계약은 변경하지 않는다. 기본안은 migration 없이
현재 JSONB/컬럼으로 조회한다. 측정으로 인덱스가 필요해지면 migration과 upgrade
검증을 추가하고 이유를 기록한다. OpenAPI와 generated TypeScript types를 동기화한다.

## 6. 검색·상세·복귀 동작

- 검색 조건/정렬/개별 결과 수는 유지한다. GitHub 결과에 저장소 이름과
  커밋/문서 구분을 표시하고 `Browse repository` 링크를 제공한다.
- 저장소에서 Entry를 열면 `Back to repository`로 탭·페이지·문서 경로까지 복귀한다.
  Search에서 직접 Entry를 열면 기존 `Back to search`를 유지한다.
- returnTo와 repositoryReturn은 허용한 로컬 경로·query만 다시 구성한다.
  외부 URL, protocol-relative URL, 잘못된 scope/path/page, 재귀 return 값을 거절한다.
  safeRepositoryReturn은 offset/doc_offset/snapshot_offset을 각각 검증하고,
  scope/tab/path와 외부 목록 복귀용 returnTo만 허용해 URL을 다시 구성한다.
  탭과 path 조합도 검증한다. 문서 목록과 스냅샷 목록의 페이지를 서로 덮어쓰지 않는다.
  새 탭/새로고침도 동일하게 동작한다. Codex sessionReturn을 보존한다.
- 상세 sidebar도 repository context를 유지하며 해당 커밋/문서 목록을 사용한다.
  기존 전체 Entry sidebar로 연결되어 저장소 탐색을 이탈하지 않게 한다.
  기존 EntryListContext(Entries/Search)는 외부 복귀용으로 유지하고, 별도 검증된
  RepositoryContext를 RecordSidebar에 전달한다. 이 context가 있으면 기존
  useEntrySearch 대신 저장소 전용 query를 사용한다. Commits/Unclassified는
  records API의 같은 kind/offset, Documents의 path 선택 상태는 document-snapshots
  API의 같은 path/snapshot_offset을 조회해 실제 Entry 링크를 표시한다.
  Documents의 path 미선택 상태에서 대표 문서를 열 때는 해당 path와
  snapshot_offset=0을 복귀 context로 설정하고 doc_offset을 보존한다.
  sidebar의 모든 Entry 링크는 전용 githubEntryTarget helper로 repositoryReturn과
  외부 returnTo를 함께 유지한다. 검색에서 직접 연 원문에는 기존 검색 sidebar를 사용한다.
- 주석/버전 선택/삭제/수집 적용에 따라 archive·저장소 요약·탭·검색·reader 캐시를
  갱신한다. 계정 전환과 logout은 private cache 전체를 기존 방식으로 비운다.

## 7. 구현 순서와 커밋 경계

1. 저장소 요약/목록 query·API·schema와 archive 그룹을 구현하고 backend 검증.
   검색 schema/service의 repository_ref와 nullable 하위 호환도 이 단계에 포함한다.
   제안: `feat: group GitHub archive records by repository`
2. 카드·저장소 탭·검색 링크·상세 복귀/sidebar·cache와 생성 타입을 함께 연결.
   제안: `feat: add GitHub repository browsing`
3. synthetic/실제 자료의 격리 검증 후 사용자 안내를 작성한다.
   CURRENT에 실제 구현/확인 상태, DECISIONS에 보관과 표시 단위의 결정,
   GITHUB_BACKFILL에 확인 절차를 기록한다. ROADMAP에는 2.4A/B 사이 UI checkpoint를 명시한다.
   제안: `docs: document GitHub repository browsing checks`

각 단계는 실행 가능한 검증 경계다. 구현 요청은 커밋 허가로 해석하지 않으며,
사용자 요청에 따라 문서/구현을 커밋한다. 기존 인증 보완은 독립 커밋 후보로 남긴다.

## 8. 검증 계획

Backend:

- 두 owner/여러 저장소/동일 이름 다른 ID/동일 ID 이름 변경/여러 Codex 세션과
  일반 노트를 섞어서 그룹 후 total/페이지 경계와 중복 없는 결과를 검증.
- current version 변경, 과거 payload 제외, 분류 불가/scope 오류, source-deleted,
  삭제 후 개수/마지막 카드 제거, 누락 날짜와 동률 순서를 검증.
- path 그룹을 페이지 전에 계산하는지, 동일 path 여러 SHA/동일 본문 스냅샷,
  여러 branch/run을 latest HEAD로 오인하지 않는지, path별 소유권을 검증.
- 다른 owner 저장소·path·record 접근과 임의 scope/path/offset에 대해 404/422 검증.
- 검색 repository_ref의 current version/owner/scope 검증, 분류 불가 fallback,
  session_ref 보존, 결과 수·순서 유지와 N+1 없는 조회를 검증.
- 새 grouped/목록 query는 선택한 415건과 여러 페이지 synthetic fixture로
  실행 시간/EXPLAIN을 확인한다. 매 행마다 payload 전체나 별도 query를 읽지 않는다.
  전체 backend suite와 생성 API 타입 일치 검사를 실행한다.

Frontend:

- 카드 count/라벨, 탭·페이지·path URL 복원, 빈 상태/오류/retry,
  상세·검색·sidebar 복귀, 범위 벗어난 페이지, 삭제와 버전 선택 cache 갱신 테스트.
  문서 경로 목록 2페이지에서 선택한 path의 스냅샷 2페이지로 이동하고,
  원문/sidebar 이동·새로고침 후에도 두 offset이 유지되는 회귀 테스트를 포함한다.
- 기존 Codex/노트/검색/logout/account-switch 회귀와 악성 return 값 차단을 검증.
- frontend tests/lint/build; Chromium 320/390/768/1440px에서 긴 이름/path/제목,
  키보드 링크·탭 탐색, overflow/page errors와 날짜 구분을 확인한다.
- 실제 415건 bundle을 개인 DB에 쓰지 않고 기존 격리 PostgreSQL/HTTP 검증
  helper로 적용해 저장소 1개·372 commits·43 snapshots를 확인한다.
  문서 경로 수는 실제 데이터로 계산한다. replay/버전/권한 동작을 재검증한다.

## 9. 사용자 확인과 한계

기존 db/API/frontend 실행 상태에서 `http://localhost:5173/entries`를 연다.
데이터 없는 계정은 synthetic seed, 실제 계정은 검토한 preview의 명시적 apply가 필요하다.
collector/worker 상시 실행은 이 읽기 화면 확인에 필요하지 않다.

1. Entries에서 저장소 카드 하나와 기존 Codex 세션/일반 노트를 확인한다.
2. 카드 → Commits: 과거 기록이 실제 날짜순이며 오래된 커밋의 diff를 읽고 돌아온다.
3. Documents: 같은 경로가 한 줄로 모이고 이전 스냅샷을 열어 당시 문서를 확인한다.
4. Search: 개별 기록 검색 → 원문 → 검색 복귀, 저장소 탐색 → 검색 복귀를 확인한다.
5. URL 새로고침/새 탭과 작은 화면에서 탭·페이지·복귀가 유지되는지 확인한다.

보관 개수는 수집 completeness가 아니다. 현재 GitHub와 자동 동기화하지 않는다.
동시 수집/삭제 시 offset 페이지가 이동할 수 있으며 기록 선택은 Entry ID로 유지한다.
과거 문서 삭제/rename를 최신 보관 내용으로 복원해 현재 상태라 주장하지 않는다.
외부 AI 호출/요약, 저장소 전체 조작, 실기기/다른 브라우저 검증은 별도 작업이다.
