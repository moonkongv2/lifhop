# Phase 2.4 — GitHub 과거 기록 수집 구현 계획

작성일: 2026-10-04
기준 커밋: `2598187` (Codex 읽기 보완)
상태: 구현 전 계획. Antigravity compact plan review 1회 완료, 지적 3건 반영.

## 1. 목표와 완료 기준

GitHub의 오래된 변경 이유와 당시 문서를 lifhop에서 검색하고 원본 근거를
확인한다. 로드맵대로 두 번의 사용자 확인 가능한 구현으로 나눈다.

| 단계 | 구현 범위 | 사용자에게 보이는 결과 |
| --- | --- | --- |
| 2.4A | 커밋·diff·선택 문서의 과거 스냅샷 | 오래된 커밋 검색 → 변경 이유·파일 변경·당시 문서 확인 |
| 2.4B | PR·리뷰·이슈·댓글 | 관련 논의 검색 → 원본·관련 커밋·대화 확인 |

2.4A만 구현하고 Phase 2.4 전체 완료로 표시하지 않는다. 2.4B도 개인 출시의
필수 범위다. AI 요약/답변, 자동 수집, 브라우저 collect-now는 후속 Phase다.

완료 조건:

- 선택한 저장소/브랜치에서 접근 가능한 기간을 끝까지 페이지로 읽고, 선택
  범위·종료 여부·제외·실패·누락을 보여준다. 범위 밖 기록의 존재를 추정하지 않는다.
- 같은 SHA가 여러 브랜치에 있거나 재실행해도 Entry가 중복되지 않는다.
- 준비/다운로드와 서버 적용 모두 중단 후 재개한다. ACK 유실/정책 변경/삭제를
  처리하고, 서버에 기록과 receipt가 저장되기 전에 적용 완료로 표시하지 않는다.
- 기존 Codex preview·receipt·API 요청/응답 계약을 유지한다.
- 출처/기록의 AI 권한·주석·버전·삭제 suppression을 그대로 사용한다. AI는 기본 off.

## 2. 첫 검증 범위와 설정

기존에 선택한 `moonkongv2/jy_yamyam`을 첫 검증 저장소로 사용한다.
기본 브랜치는 `main`으로 선택하되 시작 시 존재/권한/저장소 ID를 다시 확인한다.
다른 브랜치는 목록만 보여주며 자동으로 수집 대상으로 확대하지 않는다.

로컬 private config에 다음을 명시한다. 비밀과 토큰은 넣지 않는다.

- 저장소 locator `owner/name`, 최초 확인한 numeric repository ID.
- 선택 브랜치, 문서 경로 allowlist, 제외 경로, parser/filter 버전과 자원 한도.
- 기본 문서 allowlist: `README.md`, `ROADMAP.md`, `DECISIONS.md`, `docs/**/*.md`.
  없는 경로는 대상 0개로 표시한다. glob은 저장소 상대 POSIX 경로에만 적용한다.
- 코드 파일 전체 본문은 수집하지 않는다. 커밋에서 반환된 선택 가능한 텍스트
  patch는 보존하되 credentials/키/환경 dump 등 민감 경로·내용은 필터로 제외한다.
- 요청 수 예상값/현재 API 예산을 보여준다. Phase 2.1의 372커밋은 과거 측정값이며
  현재 개수나 전체 수집 비용을 보장하지 않는다.

Public 저장소는 익명 읽기를 허용한다. 전체 diff를 읽으면 요청이 수백 번 필요할
수 있어, 선택 저장소의 Contents: read 토큰을 환경변수 `GITHUB_TOKEN`으로
받는 경로도 지원한다. 토큰을 새로 만들거나 저장하지 않고 CLI 인자/preview/
checkpoint/서버/리뷰어에 전달하지 않는다. 2.4B는 Pull requests/Issues의 read
권한이 추가로 필요할 수 있으므로 구현 때 endpoint별 최소 권한을 검증한다.

## 3. 현재 코드와 필요한 변경

| 현재 | 2.4A 변경 |
| --- | --- |
| `app/acquisition/github.py`: 저장소/브랜치 inventory와 커밋 1개 샘플 | 검증 도구 유지; 별도 collector에서 전체 페이지·diff·문서 준비 |
| CanonicalItem의 GitHub scope/prefix 검증, 공통 버전/upsert | repository/object별 구체적 schema와 identity 검증 추가 |
| DevSession/Document/Conversation payload | GitHub commit/document 구조화 payload와 normalizer 추가 |
| RunCreate/CollectorItem/Coverage가 Codex 전용 | provider별 엄격한 요청·coverage를 허용, 기존 Codex 직렬화 유지 |
| receipt가 `run.scope[4:]`로 Mac UUID 전제 | provider에 맞는 identity 검증; 모든 route의 run/item provider·scope 일치 확인 |
| CollectionRun/Item의 provider·scope·coverage JSONB | 기존 durable receipt/lock 구조 재사용 |
| Sources의 CollectionRuns가 Codex 고정 | 출처 선택, GitHub 범위·갭·진행/결과 표시 |
| 기존 Entry detail/history/검색 | GitHub evidence reader와 원본/관련 기록 링크 추가 |

새 generic importer framework를 만들지 않는다. provider 분기는 adapter와
schema/identity 검증 경계에 한정한다. PostgreSQL JSONB와 기존 모델로 충분한지
구현 시작 시 확인한다. 영속 컬럼/제약을 바꾸면 Alembic migration과 upgrade
테스트를 함께 추가한다. Redis/SQS/새 worker/S3/AWS 서비스·의존성은 필요 없다.

## 4. 정체성과 canonical 계약

`provider=github`, `source_scope=repo:<numeric_repository_id>`를 사용한다.
저장소 이름/owner 변경은 locator 변경이며 새 저장소 identity가 아니다.
동일 이름으로 다른 ID가 반환되면 다른 source로 명시 확인하며 기존 run을 재개하지 않는다.

| 대상 | external_id | Entry type |
| --- | --- | --- |
| 커밋 | `repo:<id>:commit:<sha>` | PROJECT_EVENT |
| 문서 스냅샷 | `repo:<id>:document:<commit_sha>:<sha256(path)>` | DOCUMENT |
| PR/이슈/리뷰/각 댓글 (2.4B) | `repo:<id>:<object_kind>:<stable_object_id>` | PROJECT_EVENT / CONVERSATION, B 구현 때 계약 확정 |

서버는 repository ID·SHA·path hash를 payload에서 검증하여 external_id와 대조한다.
별도 `CollectorItem.identity` 필드는 추가하지 않는다. receipt/preflight/outcome의
identity는 요청의 `external_id`와 같은 값이다. 공통 helper는 `provider=codex`이면
기존 `scope[4:] + ':'`와 UUID/thread/turn 계산을 유지하고, `provider=github`이면
`run.scope + ':'` 및 위 object identity 전체를 검증한다. 다른 provider는 거절한다.
`github`이면 Codex payload, `codex`이면 GitHub payload를 받지 않는다.
provider/scope/identity가 서로 다른 run에 항목/실패/outcome을 등록할 수 없다.

커밋 payload: repository ID, SHA/tree SHA, message, author/committer의 이름·시각,
원본 author login(있으면), parent SHAs, 파일 경로/이전 경로/status/stats/patch와
patch availability, explicit omissions. 메시지 첫 줄을 제한된 제목으로 표시한다.
본문과 diff는 정규화 텍스트로 검색 가능하게 하며 원본 링크/구조화 근거를 유지한다.
`event_at`은 commit committer date, author date는 별도 보존한다.

문서 payload: repository ID, commit SHA, blob SHA, path, content, snapshot reason
(historical change / selected-head baseline), 원본 링크와 omissions.
문서 스냅샷 시각은 해당 commit 시각이며 실제 마지막 수정일과 같다고 주장하지 않는다.
경로 이름 변경은 commit의 previous_filename/status로 연결하고 새 경로 identity를
보존한다. 경로별 최신 문서를 과거 전체의 대표로 덮어쓰지 않는다.

branch membership/선택 head와 observed_at 등 실행마다 바뀌는 값은 manifest/run에
저장한다. immutable commit/document body에 넣어 재실행마다 새 버전을 만들지 않는다.
추후 누락 patch를 더 읽거나 sanitizer가 바뀌면 기존 버전 보존 규칙을 따른다.

## 5. 수집 준비: 고정된 범위를 읽고 재개하기

### 5.1 저장소와 브랜치 고정

1. repository metadata로 ID/현재 이름/권한을 확인한다.
2. 선택 브랜치의 head SHA를 고정하고 private preparation checkpoint에 저장한다.
3. `commits?sha=<pinned_head>&per_page=100&page=N`을 순차적으로 읽는다.
4. repository ID + SHA로 합집합을 만들어 중복 상세 요청을 피한다. 브랜치별
   membership와 페이지 종료 여부는 coverage에 따로 기록한다.
5. GitHub가 반환한 next Link는 host/path/query 범위를 검증한다. redirect/임의 URL을
   따라 토큰을 전달하지 않는다. 페이지 반복·SHA 불일치·schema 변경은 갭이다.

head가 나중에 바뀌어도 준비 재개는 고정된 SHA를 사용한다. 새 head는 새 run이다.
강제 push로 pinned object가 접근 불가능하면 REF_UNAVAILABLE로 표시하고 범위를
몰래 바꾸지 않는다. 삭제된 브랜치/도달 불가능 객체를 복구하는 기능은 아니다.

### 5.2 커밋과 파일 변경

커밋 상세의 `files` 페이지도 모두 순회하며 SHA/정적 필드 일치와 파일 중복을
검사한다. 반환 patch 없음과 빈 patch는 구분한다. binary/large의 구체 원인을
API가 알려주지 않으면 PATCH_UNAVAILABLE로 남기고 원인을 지어내지 않는다.

GitHub의 3,000-file cap, 로컬 response/file/patch/record 한도, 페이지 제한에
닿으면 해당 evidence의 completeness를 partial로 표시한다. cap까지 반환된
경우 전체 파일 수가 검증되지 않으면 complete로 단정하지 않는다.

### 5.3 문서의 실제 과거 내용

- 수집한 각 커밋의 변경 파일에서 allowlist와 일치하는 경로를 선정한다.
  삭제는 commit evidence로 남기고 빈 문서 스냅샷을 만들지 않는다.
- 추가/수정/rename된 문서는 `contents/<path>?ref=<commit_sha>`로 그 시점의
  내용을 읽는다. rename의 이전 경로는 기존 과거 스냅샷/commit에서 추적한다.
- 선택 head의 allowlist 문서도 확인한다. 이미 수집한 historical snapshot 중
  같은 path/blob SHA가 있으면 별도 baseline Entry를 만들지 않고 run의 head-document
  mapping이 그 스냅샷을 참조한다. 여러 개면 선택 head의 도달 가능한 이력 중 가장
  최근 해당 스냅샷을 연결한다. 같은 내용이 다시 등장한 별도 변경 시점은 보존한다.
- 같은 path/blob의 historical snapshot이 없으면 head commit SHA 기준 baseline을
  만든다. 이는 head에서 관측한 내용이며 실제 마지막 수정 시점이 아니다. 문서
  Entry 중복 검사는 commit SHA/path 기준, head baseline 추가 검사는 path/blob
  기준이다. 이력 종료 미검증이면 baseline 유무로 과거 문서 coverage를 완전으로
  표시하지 않는다. 같은 head SHA/path baseline이 여러 브랜치에 있으면 한 번만 저장한다.
- Contents API는 symlink target을 일반 파일처럼 반환할 수 있으므로, pinned
  commit의 tree에서 경로의 각 요소와 leaf mode를 확인한다. `100644/100755`만
  허용하고 symlink `120000`와 submodule `160000`은 따라가지 않는다.
- head의 glob은 allowlist에 필요한 tree만 탐색한다. immutable tree SHA로
  로컬 캐시하고 truncation은 하위 tree 조회/명시 갭으로 처리한다.
- UTF-8/base64/실제 decoded 크기를 검증한다. binary·LFS pointer·크기 초과는
  explicit gap으로 보존한다. 외부 download_url이나 LFS 서버를 자동 호출하지 않는다.
- path가 allowlist 밖이거나 민감 경로이면 이름/내용 필터 정책대로 제외한다.
  non-allowlist 제외와 선정한 문서의 접근 실패를 별도로 표시한다.

### 5.4 준비 checkpoint와 검토할 bundle

준비 checkpoint는 GitHub 응답을 아직 읽는 단계의 진행 기록이다. repository ID,
pinned heads, config/parser/filter digest, 페이지/파일 offset, 완성된 항목 hash,
retry-at을 private 파일에 atomic write한다. 페이지 전체의 캐시/항목이 durable하기
전에 next page로 체크포인트를 앞당기지 않는다. 전체 응답을 메모리에 누적하지 않는다.

준비가 끝나거나 사용자가 partial 범위로 seal을 명시하면 immutable manifest와
sanitized payload, HTML 검토 파일을 만든다. 준비 중인 폴더는 apply할 수 없다.
seal 후 내용을 바꾸는 재개는 금지하며 갭 보완은 새 preview/run으로 진행한다.
local cache/journal도 개인 데이터이며 private permissions/cleanup/ignore 대상이다.

초기 자원 한도는 response 8 MiB, 문서 1 MiB, wire record 1 MiB,
patch/file별 제한, bundle 256 MiB, run items 100,000, page/request/time budget을
설정에 명시한다. 문서는 JSON encoding/metadata를 포함해 wire 한도를 넘을 수
있으므로 content를 무음 자르지 않고 item-size gap 또는 명시적 partial로 처리한다.
수치 조정은 실제 synthetic 측정 후 문서화한다. 용량 제한에 도달하면 재개 가능한
지점을 남기고 completeness를 속이지 않는다.

## 6. 요청 한도·실패·credentials

공식 REST API `2026-03-10`과 순차 GET을 사용한다. 응답뿐 아니라 HTTP 오류의
허용된 rate-limit/Retry-After/SSO/expiry 헤더를 읽는 reader가 필요하다.

| 상황 | 행동 |
| --- | --- |
| 401/token 만료 | AUTH_FAILED로 준비 중단; 새 토큰으로 동일 pinned 범위 재개 |
| 403/429와 rate-limit 근거 | Retry-After/reset을 반영해 checkpoint 후 paused; 예정 시각 출력 |
| rate-limit 근거 없는 403/SSO | ACCESS_DENIED/SSO_REQUIRED, 자동 반복 요청 금지 |
| timeout/network/5xx | 제한된 exponential backoff; 예산 초과 시 재개 지점 보존 |
| 404 | 접근 불가/원본 unavailable, 삭제 확정으로 표시하지 않음 |
| 409 | 사전 metadata와 빈 branch inventory로 empty가 확인될 때만 empty; 다른 conflict는 갭 |
| repo rename/redirect | 자동 redirect 금지; 새 locator가 동일 repo ID인지 확인 후 명시 재개 |

한 시간 기다리는 프로세스를 만들지 않는다. pause는 종료하고 같은 준비 명령으로
재개한다. rate-limit 해제 시각 전에 요청을 반복하지 않으며 토큰/비밀은 로그에서 제외한다.
실제 public 전체 읽기도 API 예산을 확인한 뒤 진행하며 토큰 없이 당일 완료를
보장하지 않는다. 토큰이 필요한 검증은 구현 중 환경 제공 절차를 안내한다.

## 7. 서버 적용과 Codex 호환성

- Codex/GitHub별 RunCreate와 item schema를 구체적으로 검증한다. 기존 Codex
  payload/run 직렬화와 digest는 byte-equivalent이며 추가 필드 default로 바뀌지 않는다.
- GitHub scope/manifest에는 repository identity와 선택 범위를 고정한다. 기존
  `/collection-runs`의 create/preflight/items/outcomes/receipts/finish를 확장한다.
- apply checkpoint는 API origin + lifhop owner + provider/scope + manifest/parser/
  filter에 묶인다. 불일치 시 안전한 차이 항목만 알려주고 이전 ACK를 지우지 않는다.
  다른 lifhop 계정 적용은 새 reviewed run을 만든다.
- owner lock·정책·suppression 검사와 Entry/version/receipt의 atomic commit을 유지한다.
  run/항목 receipt가 이미 있으면 서버 digest와 대조하고 재실행한다.
- 정책은 preflight와 commit 직전 재검사한다. source/record AI deny와 주석은 재수집으로
  초기화하지 않는다. lifhop 삭제는 GitHub 원본을 삭제하지 않는다.
- 준비 단계의 GitHub fetch error는 manifest coverage의 명시 갭이며 업로드되지 않는다.
  선정했지만 정규화할 수 없는 항목은 body-free INVALID_ITEM outcome을 사용한다.
- coverage에는 branch별 pinned head·walk_complete와 commit/document counts,
  숫자가 lower bound인지, 수집 종료 사유/갭을 표시한다. 기존 Codex flat Coverage는
  그대로 두고 GitHub coverage는 별도 엄격한 schema로 만든다.
- 요청은 `CodexRunCreate | GitHubRunCreate`, 응답은 현재 `RunResponse`에 대응하는
  `CodexRunResponse | GitHubRunResponse`를 provider로 선택한다. 각각의 coverage
  타입을 고정하고, 기존 Codex create에서 provider를 생략하는 입력도 기존처럼
  Codex로 처리한다. 직렬화/digest/추가 기본값의 회귀를 fixture로 확인한다.
- create/list/read/finish와 내부 `run_response()` 모두 같은 provider별 응답 검증을
  사용한다. GitHubCoverage에도 finish가 읽는 `gaps`를 유지한다. 알 수 없는
  provider/잘못된 coverage는 저장 전에 거절하여 조회에서 500이 나지 않게 한다.
- `expected_items`는 기존처럼 RunCreate/RunResponse의 최상위 필수 정수다.
  GitHubCoverage에 중복 필드를 만들지 않는다. 정상화된 manifest 항목과 body-free
  outcome의 합으로 계산하고 최종 receipt 수와 비교한다. 기존 `/finish`는 요청
  body 없는 POST이며 새 FinishRunRequest나 존재하지 않는 source-runs route를 가정하지 않는다.
- expected_items는 seal한 manifest의 항목/실패 outcome 수다. 모든 receipt가 저장되어도
  coverage가 partial이면 전체 backfill complete라고 표시하지 않는다. empty와 실패를 구분한다.

공통 client에서 Codex bundle validation을 import하는 부분은 provider별 validator로
분리한다. Codex run replay·scope 오류·삭제·ACK 유실·버전/권한 regression을 먼저
검증하고 GitHub를 연결한다. 단순 provider Literal 변경만으로 완료하지 않는다.

## 8. 브라우저에서 확인할 사용자 흐름

1. 로컬 CLI에서 저장소/브랜치/문서 목록과 요청 예산을 확인한다.
2. 준비/재개 후 HTML에서 오래된 커밋과 당시 문서를 검토한다.
3. 같은 bundle을 lifhop 계정으로 명시 apply한다.
4. Sources의 GitHub run에서 저장소 이름/ID, pinned heads, 기간·walk 종료,
   commit/document 처리 수·갭·완료/부분/empty 결과를 확인한다.
5. Search의 GitHub source/date 조건으로 커밋 메시지와 당시 문서/patch를 찾는다.
6. 상세에서 commit message/metadata/file diff, 문서 snapshot 시점, GitHub 원본 링크,
   같은 commit에 수집된 문서/관련 commit 링크를 확인한다.
7. 같은 apply와 새 같은-snapshot preview를 재실행해 Entry/버전 중복이 없음을 확인한다.

Sources는 provider별 제목과 개수를 사용하며 GitHub를 sessions/turns라고 표시하지
않는다. 기존 Codex UI/20-item pagination은 유지한다. GitHub 문서는 스냅샷임을
표시하며 현재 README처럼 오해시키지 않는다. 모든 UI label은 영어다.
GitHub renderer는 Markdown/patch를 안전한 text로 표시하고 imported HTML/명령을
실행하지 않는다. 원본 링크는 검증된 https GitHub locator만 사용한다.

## 9. 구현 순서와 커밋 경계

### 2.4A

1. **Canonical/API 계약:** GitHub payload/identity/coverage, shared run 검증과 Codex
   호환성 테스트. 필요한 migration이 있다면 이 단계에 포함.
2. **수집 준비/apply:** pinned traversal·diff/doc·sanitizer·bounded journal·seal·재개,
   실제 loopback HTTP/격리 PostgreSQL ingestion·receipt 테스트.
3. **브라우저 흐름:** Sources/provider results, GitHub evidence/문서 연결, OpenAPI
   generated types, 테스트와 사용자 가이드 `GITHUB_BACKFILL.md`.
4. 전체 checks와 선택 public source의 private preview를 검증한 뒤 사용자 확인.
   실제 계정 apply는 reviewed bundle에 대한 명시적 사용자 실행/승인을 따른다.

각 경계에서 정상 동작하는 커밋을 만든다. 모델/collector/UI에 관련 테스트·문서를
함께 넣는다. 사용자가 승인하기 전 자동 커밋하지 않는다.

### 2.4B — A 사용자 확인 후 별도 세부 계획

- PR/issue 전체 접근 가능 목록과 각 review/comment 페이지를 읽는다.
  Issues API에 포함된 PR은 pull_request 필드로 구분하여 두 번 저장하지 않는다.
- discussion root와 review/comment를 stable ID별 Entry로 저장하고 원본 parent/PR/
  issue/commit 연결을 보존한다. 댓글 추가가 root의 한도나 삭제 suppression을 우회하지 않게 한다.
- root/body/comment 수정은 updated_at 기반 공통 관측 버전으로 처리한다.
  source가 공개하지 않는 과거 편집/삭제본을 복원했다고 주장하지 않는다.
- PR은 state=all, issues 역시 전체 상태를 선택한다. 생성 이후 계속 변할 수 있는
  목록은 snapshot 시각/관측 시각과 pagination 불확실성을 기록하고 중복 ID를 제거한다.
- review state·submit time·review diff hunk·file/line context(원본이 주는 경우),
  author/body/time, merge/close/관련 SHA를 보존한다. 커밋 관련 discussion 링크를 제공한다.
- PR/issue가 없는 저장소는 성공한 0개 결과다. 자료가 없는 selected 실제 저장소는
  synthetic discussion fixture로 동작을 검증하고 실제 내용 검증 한계를 기록한다.

## 10. 검증 계획

### Backend / collector

- legacy Codex requests/preview/digests/checkpoints/receipts와 Session UI 계약 regression.
- 같은 SHA가 두 브랜치에 등장, 저장소 rename/동일 이름 다른 repo ID, malformed scope,
  provider 혼합, payload와 ID 불일치, 타 owner/run 접근·receipt/outcome 변조 차단.
- 100개 이상 commit 페이지/300개 이상 files 페이지, 중복/반복 Link, cap/truncation,
  pinned head 변경/강제 push/unavailable, 빈 저장소와 409 conflict 구분.
- 과거 문서 추가·수정·rename·삭제, head baseline, allowlist/제외/glob/path encoding,
  symlink target 위장/submodule/LFS/UTF-8/base64/크기 초과/metadata wire overhead.
- historical snapshot과 head의 같은 path/blob 중복, 동일 내용 재등장의 별도 시점,
  두 head에서 공통 baseline, 이력 partial인데 head만 확인한 경우의 coverage.
- Codex/GitHub create/list/read/finish 응답 schema와 혼합 출처 상태 조회,
  legacy provider 생략 요청, expected_items/receipt 합계 mismatch, unknown provider 거절.
- rate-limit 403/429/Retry-After/reset, 권한 403/SSO/401/404, redirect token 유출 방지,
  network timeout/5xx, invalid schema. timestamp/signature/빈 author를 원본대로 처리.
- 준비 page/cache atomic write 이전/이후 종료, budget pause/resume, seal 이후 tampering,
  잘못된 config/owner/origin resume, concurrent apply, lost ACK, rollback, server restore.
- 실제 localhost HTTP + fresh migrated isolated PostgreSQL: ingest/replay·정책 거절·삭제
  suppression·원본 필터링·후보 버전·주석/AI deny 보존; 예상 요청 수/peak memory 측정.
- deterministic normalization: observed_at/branch 집합 변화가 immutable body를 바꾸지 않음.

### Frontend / 사용자

- GitHub/Codex Sources 결과·loading/error/retry/provider pagination·empty/partial 표시.
- GitHub source/date 검색→commit/diff/document→목록 복귀, provenance/history/annotations,
  source/record AI off·delete/allow-reimport. unsafe links/imported HTML 실행 금지.
- 320/390/768/1440px, 긴 commit message/path/patch, 키보드/영어 UI 확인.
- backend suite, frontend tests/lint/build, OpenAPI type generation consistency,
  migration upgrade(필요 시), diff whitespace와 Git status 확인.
- 실제 `moonkongv2/jy_yamyam`의 오래된 commit와 문서 SHA를 GitHub 원본과 대조하고
  interrupted preparation/resume·재실행 중복 없음을 확인한다. 개인 자료를 Git/test/
  reviewer prompt에 넣지 않는다.

## 11. 한계와 다음 단계

선택 브랜치에서 도달 가능한 객체와 API가 제공하는 자료만 수집한다. API cap,
patch 미제공, 삭제 ref, 권한·quota·원본 변경으로 누락될 수 있다. preview 필터는
완전한 비밀 제거 보장이 아니므로 검토 자료는 private로 유지한다.
대규모 repository, 실제 private/org SSO/만료 토큰, AWS 배포는 해당 검증 전까지
미확인으로 보고한다. 이 계획은 구현/서버 적용을 완료한 것으로 표시하지 않는다.

2.4A 검증 후 2.4B를 구현하고 ChatGPT/Codex/GitHub 통합 검색·출처·기간·coverage를
확인해야 Phase 2 종료다. 이후 Phase 3의 개인 평가 질문/근거 집합부터 시작한다.

## 12. 공식 자료와 검토 결과

2026-10-04 확인. 구현 시작 시 API/schema/최소 권한을 다시 대조한다.

- [GitHub commits API](https://docs.github.com/en/rest/commits/commits?apiVersion=2026-03-10):
  선택 SHA, pagination, 상세 files 한도/권한.
- [Repository contents](https://docs.github.com/en/rest/repos/contents?apiVersion=2026-03-10):
  ref 지정, 크기/encoding, symlink/submodule 반환 주의.
- [Git trees](https://docs.github.com/en/rest/git/trees?apiVersion=2026-03-10):
  file mode와 truncated tree의 대처.
- [REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api):
  익명 60 requests/hour, rate-limit 헤더·재시도 규칙. 이는 전체 수집 완료 시간 보장이 아니다.
- [PR reviews](https://docs.github.com/en/rest/pulls/reviews?apiVersion=2026-03-10),
  [Issue comments](https://docs.github.com/en/rest/issues/comments?apiVersion=2026-03-10): 2.4B 계약 참고.

### Antigravity 검토 결과

- Compact plan review 1회 완료. 첫 파일 참조 실행은 headless command 권한이
  자동 거부되어 결과가 없었다. 권한 설정을 바꾸지 않고 본문/계약을 직접 전달한
  도구 없는 검토로 1회 결과를 얻었다. 추가 review loop는 실행하지 않았다.
- 지적 3건 반영: provider별 receipt identity 계약 명시, 요청뿐 아니라 전체 run
  응답/finish의 coverage 검증 명시, head baseline과 과거 스냅샷의 중복 기준 분리.
- 일부 제안은 수정해 반영했다. 현재 코드에 별도 CollectorItem.identity,
  CollectionRunRead, FinishRunRequest, source-runs endpoint는 없다. existing
  external_id/RunResponse 계약을 기준으로 작성했고 expected_items는 최상위에 유지한다.
- blob 기반 문서 identity는 채택하지 않았다. 같은 내용이 재등장한 서로 다른 변경
  시점을 합치므로 commit/path identity를 유지하고 불필요한 head baseline만 제외한다.
- 사용자 결정이 필요한 지적 없음. 코드·API 계약 대조와 문서 whitespace/status
  검사로 검증한다. 구현·migration·개인 기록 apply·커밋은 이번 작업에서 실행하지 않는다.
