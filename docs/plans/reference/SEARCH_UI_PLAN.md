# Search 독립 화면 구현 계획

작성일: 2026-10-03
상태: agy-plan-review-loop 1회 검토 후 구현 및 로컬 검증 완료. 사용자 확인·커밋 대기.
프런트엔드 테스트 65개, 린트·빌드 및 합성 API를 사용한 Chromium 검증을 통과했다.
실제 계정 및 모바일 기기 확인은 frontend/README.md의 안내에 따라 진행한다.

## 1. 목표와 완료 조건

상단 메뉴를 `Entries · Search · Import · Sources`로 구성한다.
Entries에서는 최근 기록을 둘러보고, Search에서는 조건을 지정해 기록을 찾는다.
밝은 패널 디자인과 영어 UI를 유지한다.

- `/entries`: 최근순 카드 목록, 총 개수, 20개 단위 페이지 이동, New note.
- `/search`: 큰 검색창, 접을 수 있는 세부 필터, 검색 결과 카드와 페이지 이동.
- 검색 결과 → 상세 → 다른 결과 → 돌아가기에서 검색어·필터·페이지가 유지된다.
- 상세의 돌아가기 문구와 상단 활성 메뉴가 진입 화면에 맞는다.
- 기존 검색 링크, 노트 CRUD, 주석·이력, 가져오기 후 목록 갱신이 유지된다.
- 320px 모바일부터 데스크톱까지 메뉴와 본문에 가로 넘침이 없다.

## 2. 화면과 검색 동작

### Entries

기존 왼쪽 검색 패널을 제거하고 목록에 화면 폭을 사용한다.
`GET /entries/search`에 검색 조건 없이 limit=20과 offset만 전달한다.
정렬은 기존 API의 created_at DESC, id DESC를 사용한다.
전체 기록의 최신순 목록이며 source_state를 이유로 임의 제외하지 않는다.
New note와 빈 목록 안내, 로딩·실패·재시도, 페이지 보정을 유지한다.

### Search

상단에 제목/본문 검색창과 Search 버튼을 배치한다. Enter로 제출한다.
바로 아래 `Filters`를 네이티브 details로 접고 펼칠 수 있게 한다.
활성 필터가 있으면 처음부터 열고 활성 조건 수를 표시한다.
Source, Source status, Type, Date field, Start date, End date를 이동한다.
날짜의 Asia/Seoul 기준과 종료일 포함 안내를 유지한다.

검색 결과는 폼 아래에 기존 카드 디자인으로 표시한다.
검색어가 있으면 `Title matches first`, 필터만 있으면 `Most recently added`를 표시한다.
키워드 없는 출처·유형·상태·날짜 검색도 지원한다.

- 조건 없는 `/search`: 간단한 안내를 표시하고 검색 API를 요청하지 않는다.
- 유효한 조건은 trim 후 비어 있지 않은 q, source, source_state, type,
  date_from 또는 date_to 중 하나다. date_field와 offset만으로는 검색하지 않는다.
- 모든 조건을 비워 제출하면 `/search` 초기 화면으로 돌아간다.
- 입력 중에는 검색하지 않는다. 제출한 조건을 URL에 저장하고 조회한다.
- 새 검색·필터 적용은 offset을 제거한다. Reset은 조건과 페이지를 모두 제거한다.
- 역전된 날짜는 제출 전에 안내하며 적용된 URL/결과를 변경하지 않는다.
- 로딩, 실패/재시도, 결과 없음, 잘못된 offset 안내를 유지한다.
- Search의 New note 버튼은 추가하지 않는다. 노트 생성은 Entries에서 시작한다.

## 3. URL과 상세 복귀

### 목록 주소

- Entries: `/entries` 또는 `/entries?offset=20`.
- Search: `/search?q=...&source=...&offset=20` 등 기존 필터 이름을 그대로 사용.
- 키워드는 기존의 literal phrase 의미를 유지하고 AI 검색이나 새 정렬은 추가하지 않는다.
- 상단 Search 메뉴는 `/search` 초기 화면을 연다. 마지막 검색을 전역 저장하지 않는다.

기존 `/entries?...`에 q/source/source_state/type/date_field/date_from/date_to 중
하나라도 있으면, 알려진 필터와 offset을 보존해 `/search?...`로 replace한다.
새 URL로 넘기기 전에 옛 Entries 화면의 검색 요청은 실행하지 않는다.
offset만 있는 기존 URL은 Entries로 유지한다. 빈 조건은 Search 초기 안내 규칙을 따른다.
limit은 클라이언트에서 항상 20으로 고정하며 알 수 없는 파라미터는 전달하지 않는다.

### 상세 주소와 복귀 컨텍스트

카드/사이드바 링크에 복귀 대상 URL을 명시한다.
예: `/entries/123?returnTo=%2Fsearch%3Fq%3Dworker%26offset%3D20`.
URL을 기준으로 복귀 화면을 정해 새로고침과 링크의 새 탭 열기에서도 보존한다.
정해진 진입 목록의 URL을 전달하고 상세 URL을 returnTo에 중첩하지 않는다.

`entryNavigation.ts` 같은 작은 유틸에서 다음을 일관되게 처리한다.

- returnTo는 `/`로 시작하고 `//`로 시작하지 않는 상대 URL로 파싱한다.
  파싱 결과의 origin이 현재 origin과 같고 pathname이 정확히 `/entries` 또는
  `/search`일 때만 허용한다. 쿼리가 붙은 `/search?q=worker&offset=20`도 유효하다.
  외부 URL, protocol-relative URL, 다른 경로, 잘못된 값은 `/entries`로 대체한다.
- 복귀 쿼리는 위에서 정한 목록 파라미터만 유지하고 일관되게 직렬화한다.
  필터 열거값/날짜 오류는 기존 API 오류 안내를 사용한다. offset 오류는 요청 전에 안내한다.
- 새 URL 컨텍스트가 없으면 기존 `location.state.entryListSearch`를 호환 처리한다.
  기존 검색 조건이면 Search, offset만 있으면 Entries로 해석한다.
- 컨텍스트 없는 직접 상세 진입, Import 결과 링크는 Entries로 돌아간다.
- 정상/실패 상세 화면 모두 `Back to entries` 또는 `Back to search`를 사용한다.
- Search에서 진입한 상세에서는 Search만 활성화하고 Entries의 기본 하위 경로
  활성화를 해제한다. Entries 및 New note 진입은 Entries를 활성화한다.
  Entries/Search 메뉴는 Link에 계산된 className과 aria-current를 명시해
  NavLink의 `/entries/:id` prefix 자동 매칭으로 두 메뉴가 활성화되지 않게 한다.
  상세의 활성 화면은 위 유틸로 검증한 복귀 대상의 pathname을 사용한다.
  Import/Sources 메뉴는 기존 NavLink 처리를 유지한다.
- 사이드바는 진입 목록의 동일한 조건/페이지를 조회한다. 목록 링크는
  `Browse all entries` 또는 `Back to search results`로 구분하고 컨텍스트를 전파한다.
- 목록 페이지 내 결과만 사이드바에 표시한다. 다른 페이지 탐색은 목록에서 한다.

기록 전환 시 편집/삭제 확인/주석·이력 상태 초기화는 현재 key 기반 동작을 유지한다.
노트 생성 취소/저장 후 상세에서도 Entries 페이지 컨텍스트를 유지한다.
삭제 성공은 복귀 대상 목록으로 이동하고, 마지막 페이지가 사라지면 그 화면에서
기존 마지막 유효 페이지 보정을 적용한다. 보정 조건은 offset > 0이고 offset >= total이다.
새 offset은 max(0, ceil(total / 20) - 1) * 20이며 0이면 파라미터를 제거한다.
이 보정은 replace로 수행하며 다른 검색 조건을 유지한다. 삭제 핸들러에서 목록 조회나
페이지 계산을 중복하지 않는다. 전체 결과가 0이면 Search에서 결과 없음과 Reset을 표시한다.

## 4. 구현 범위와 순서

1. 복귀 컨텍스트 유틸과 케이스 테스트를 작성한다. 외부 주소/중첩/직접 진입을 포함한다.
2. 기존 SearchForm을 독립 컴포넌트로 옮기고 `EntrySearchPage.tsx`를 추가한다.
   카드/페이지 이동/결과 상태는 두 화면에서 실제 공유하는 최소 컴포넌트만 추출한다.
   페이지 쿼리와 페이지 보정이 복제되면 해당 부분만 공통 훅으로 옮긴다.
3. EntryListPage를 최근 목록으로 단순화하고 옛 검색 주소 redirect를 적용한다.
4. main.tsx와 App.tsx에 Search 경로·메뉴·활성 상태를 연결한다.
   모바일 4개 메뉴는 줄바꿈 또는 메뉴 내부 스크롤로 수용한다.
5. EntryDetailPage, RecordSidebar, EntryCreatePage의 복귀/링크/삭제 후 이동을 변경한다.
6. CSS와 관련 테스트를 맞추고 실제 브라우저에서 합성 기록으로 점검한다.
7. 확인 후 CURRENT.md, frontend/README.md 및 ROADMAP의 UI 체크포인트를 갱신한다.
   구현 완료와 사용자 확인 대기를 구분해서 기록한다.

API/DB/worker/권한 정책 변경, 신규 패키지, 자동완성·검색 기록 저장·AI 답변은 범위 밖이다.
기존 `fetchEntrySearch`와 `['entries', serializedParams]` 캐시 키를 유지한다.
Entries와 Search의 동일한 API 조건은 캐시를 공유할 수 있다.
변경·삭제·버전 선택·가져오기 후 기존 `['entries']` prefix 무효화가 두 화면과
사이드바에 적용되도록 하며, 계정 전환 시 전체 캐시 초기화를 유지한다.
기존 미커밋 UI 변경 위에 적용하고 관련 없는 변경은 하지 않는다.

## 5. 검증 계획

### 자동 검증

- 기존 노트 CRUD/저장 실패 초안/삭제 확인/이력/가져오기 테스트를 유지한다.
- 기존 검색 테스트는 `/search` 기준으로 옮기고 옛 URL redirect 테스트를 별도로 남긴다.
- Search 초기 화면·Reset·공백 제출은 API 요청이 없다. 키워드 및 필터만 검색은 요청한다.
- 날짜 오류, 없는 결과, API 오류·재시도, 인증 없는 두 화면의 요청 차단.
- Enter 제출, URL로 복원, 페이지 이동, 필터 변경 시 첫 페이지 복귀.
- 옛 링크의 필터/offset 보존과 redirect 전 잘못된 요청 차단.
- Entries/Search의 카드 → 상세 → 사이드바 전환 → 복귀 문구/주소/활성 메뉴.
  상단 활성 className과 aria-current가 동시에 한 메뉴에만 적용되는지 확인한다.
- 컨텍스트를 URL로 가진 직접 상세 진입과 위험하거나 깨진 returnTo의 안전한 fallback.
- 노트 생성 취소·저장, 마지막 페이지 삭제 보정(offset == total 경계 포함),
  검색 0건으로 삭제 후 offset 제거 및 Reset으로 초기 화면 복귀.
- 데이터 변경 후 두 화면의 캐시 갱신과 로그인 계정 전환 시 캐시 제거.

실행: frontend에서 `npm test`, `npm run lint`, `npm run build`; 저장소에서 `git diff --check`.
백엔드 변경이 없으므로 이번 단계에서는 백엔드 테스트 재실행이 필수는 아니다.

### 브라우저 및 사용자 확인

로컬 API/frontend를 실행하고 `http://localhost:5173/entries`와 `/search`를 확인한다.
합성 기록과 모의 API로 먼저 화면/상호작용을 점검하고 실제 DB 검증과 구분한다.
320/390px, 태블릿, 데스크톱에서 4개 메뉴·필터·결과·3개 상세 패널을 확인한다.
새 탭 열기와 새로고침에서도 상세 복귀가 동일한 검색 주소를 유지해야 한다.
이후 사용자가 실제 계정에서 검색·복귀·주석·노트 흐름을 확인한다.
개인 기록을 검토용 프롬프트/스크린샷에 포함하지 않는다.

## 6. 커밋 체크포인트

UI 개선과 Search 분리 구현을 함께 사용자 확인한 뒤 커밋하는 것을 권장한다.
사용자 확인 전에는 커밋하지 않는다.
권장 메시지: `feat: add a dedicated search page and refresh archive UI`.

다음 제품 구현은 Phase 2.3 Codex 과거 기록 수집이다.
