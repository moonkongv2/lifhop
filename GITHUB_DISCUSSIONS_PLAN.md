# Phase 2.4B — GitHub PR·이슈·리뷰·댓글 수집 계획

작성: 2026-10-06. 상태: 구현·로컬 검증 및 소유자 합성 데모 브라우저 확인 완료.
실제 비어 있지 않은 저장소·비공개 접근 및 개인 계정 실제 자료 적용은 미확인.
Antigravity 계획 검토 1회 완료 및 보완 반영. 실행·확인 가이드: `GITHUB_DISCUSSIONS.md`.

## 1. 목표와 완료 기준

선택한 저장소의 접근 가능한 PR·이슈와 그 안의 리뷰·댓글을 수집한다.
사용자는 Entries에서 저장소를 열고 Discussions 탭에서 PR·이슈를 골라,
본문과 토론을 시간 순으로 읽고 관련된 기존 커밋 기록으로 이동한다.
Search는 개별 기록을 찾고 해당 토론의 정확한 위치로 연결한다.

완료 기준:

- 열린/닫힌/병합된 PR과 열린/닫힌 이슈의 목록 및 하위 기록을 페이지 끝까지 탐색한다.
- 실제 수집 범위, 제외, 권한 부족, 중단, API 제한을 미리보기와 Sources에 표시한다.
- 같은 미리보기 재전송은 중복을 만들지 않고, 수정된 기록은 관측 버전으로 보존한다.
- 소유권, 수집 중지, 삭제 억제, 주석, AI 제외가 기존 Entry와 동일하게 작동한다.
- PR·이슈 하나가 목록 한 행을 차지하고, 댓글·리뷰는 토론 내부에서 읽는다.
- 기존 2.4A 미리보기, 체크포인트, 검색과 저장소 탐색이 그대로 작동한다.

현재 2.4A의 415개 실제 자료 검증은 격리 DB에서 완료되었다.
개인 계정 적용과 소유자 브라우저 확인은 CURRENT.md 기준 아직 미확인이다.
이 문서는 계획을 작성하며, B 구현 시작 전 해당 상태를 확인한다.

## 2. 범위

### 포함

| 기록 | REST API | 저장 단위 |
| --- | --- | --- |
| PR | `GET /repos/{owner}/{repo}/pulls?state=all` 및 개별 PR | PR 본문·상태 1 Entry |
| 이슈 | `GET /repos/{owner}/{repo}/issues?state=all` 및 개별 이슈 | 이슈 본문·상태 1 Entry |
| 일반 댓글 | `GET /repos/{owner}/{repo}/issues/{number}/comments` | 댓글마다 1 Entry, PR에도 사용 |
| PR 리뷰 | `GET /repos/{owner}/{repo}/pulls/{number}/reviews` | 리뷰마다 1 Entry |
| 코드 리뷰 댓글 | `GET /repos/{owner}/{repo}/pulls/{number}/comments` | 댓글마다 1 Entry, 답글 관계 보존 |
| PR 커밋 연결 | `GET /repos/{owner}/{repo}/pulls/{number}/commits` | PR 메타데이터의 관계, 별도 Entry 생성 안 함 |

Issues 목록의 `pull_request`가 있는 항목은 이슈 Entry로 만들지 않는다.
PR의 안정 ID는 Pulls 응답의 PR ID를 사용한다. Issues 응답의 PR 항목 ID는
이슈 ID이므로 PR ID로 사용하지 않는다. 댓글의 부모는 저장소 ID·번호·PR/이슈
종류로 연결하며, 댓글 수집 전에 부모의 실제 ID를 확정한다.

B는 저장소의 모든 접근 가능한 PR·이슈를 대상으로 한다. A의 선택 브랜치와
범위가 다르며, 다른 브랜치의 PR도 포함한다. 다른 저장소·fork를 자동 수집하지 않는다.

### 제외

- GitHub Discussions 제품의 게시판, Actions 로그, 첨부 바이너리, reactions.
- PR 전체 파일 diff의 별도 복제. 코드 리뷰 댓글에 제공된 diff hunk는 보존한다.
- 삭제되거나 API로 제공되지 않는 기록과 과거 편집 내용의 복원.
- issue timeline 기반 교차 참조 수집, 본문 문자열만으로 추정한 관계.
- 자동 스케줄, collect-now 서버 실행, AI 요약 제목·답변: 후속 단계에서 진행.

PR에 제공된 head/base/merge SHA와 PR 커밋 목록은 서로 다른 역할로 기록한다.
본문의 `#123`·URL만으로 커밋이나 이슈의 공식 관계를 만들지 않는다.

## 3. 저장 모델과 안정 ID

기존 Entry/EntryVersion/CollectionRun/receipt/SourcePolicy를 재사용한다.
새 테이블, 큐, 의존성을 추가하지 않는다. 토론 그룹은 현재 Entry의 구조화된
메타데이터에서 조회한다. 영구 스키마 변경이 필요해지면 구현 전에 이유를 설명하고
모델·마이그레이션·upgrade 검증을 추가한다.

CanonicalPayload의 discriminated union에 다음 종류를 추가한다.

| kind | external_id (`repo:<repository_id>:` 뒤) | Entry 분류 |
| --- | --- | --- |
| `github_pull_request` | `pull_request:<pull_id>` | PROJECT_EVENT |
| `github_issue` | `issue:<issue_id>` | PROJECT_EVENT |
| `github_issue_comment` | `issue_comment:<comment_id>` | PROJECT_EVENT |
| `github_review` | `review:<review_id>` | PROJECT_EVENT |
| `github_review_comment` | `review_comment:<comment_id>` | PROJECT_EVENT |

모두 provider=`github`, source_scope=`repo:<numeric_id>`를 사용한다.
PR/이슈 번호나 제목을 identity로 사용하지 않는다. API receipt 검증 정규식과
CanonicalItem 검증을 함께 확장한다. scope·repository_id·kind·ID 불일치를 거절한다.

### 공통 구조화 필드

- repository_id, repository 이름, object_id, number 또는 parent_number,
  parent_kind, parent_external_id, 원본 html_url.
- author의 login/ID 또는 명시적인 부재, body, body의 empty/unavailable 상태.
- 원본 created_at/updated_at 등 실제 제공된 시각과 filter_version.
- omissions와 completeness. 허용 필드를 명시하고 extra 필드는 거절한다.

PR/이슈에는 원본 title, state, state_reason(제공 시), labels, closed_at,
PR의 merged/merged_at, draft, base/head/merge SHA를 보존한다.
PR에는 관측한 커밋 SHA 목록과 그 목록의 완전성도 기록한다.
리뷰에는 state, submitted_at, commit_id를 보존한다.
코드 리뷰 댓글에는 review_id, in_reply_to_id, path, diff_hunk, line/side,
원래 위치·commit_id/original_commit_id 등 API가 실제 제공한 값을 보존한다.

하위 기록에 부모 본문·본문 발췌·원본 제목을 복사하지 않는다.
부모 연결은 ID·종류·번호로 충분하다. 부모를 읽을 수 없을 때에도
`PR #12 — Parent not retained` 같은 표시가 가능하다.

### 시각과 버전

- PR·이슈·댓글: event_at은 생성 시각, source_updated_at은 해당 객체의 updated_at.
- 리뷰: event_at은 submitted_at. REST 응답에 수정 시각이 없으므로
  source_updated_at은 None으로 둔다. 읽은 시각·부모 updated_at으로 대체하지 않는다.
- 제출되지 않은 PENDING 리뷰도 접근 가능하면 draft 상태로 보존한다.
  submitted_at이 없으면 날짜 미상으로 표시한다. APPROVED 등의 빈 본문도 유효하다.
- 바뀐 리뷰는 새 관측 버전을 보존하고 review_required로 표시한다.
  기존 기록의 current 자동 교체는 검증 가능한 더 최신 원본 수정 시각이 있을 때만 한다.
- 편집 전 역사와 누락된 생성 시각은 추측하지 않는다. 404만으로 삭제를 확정하지 않는다.
- 관측 시각·실행 UUID는 run 메타데이터에 두어, 내용이 같은 기록의 해시를 바꾸지 않는다.

기존 external_entries의 중복 버전 방지·완전성 저하 방지·수동 current 선택을 유지한다.
각 댓글·리뷰의 주석과 AI 허용 여부도 개별 Entry에 남는다.

## 4. 기존 A 계약 보존

`app.collectors.github_discussions`에 B용 CLI를 추가한다.
A의 RepositoryReader, 필터, private bundle, 검증·apply 유틸리티를 재사용한다.
범용 수집 프레임워크로 리팩토링하지 않는다.

- B config는 `.local/github-discussions-collector.json`로 분리한다.
  repository ID/이름, 예산, 제외 경로와 필터 정책을 명시한다.
- parser는 B 전용 버전으로 분리한다. 기존 A config/manifest를 다시 쓰지 않는다.
- GitHubCoverage에 선택적인 `discussions` 블록을 추가한다.
  A 요청·응답에 블록이 없으면 직렬화에서도 생략한다.
  coverage serializer에서 이 새 필드만 None일 때 제외한다.
  전역 `exclude_none=True`로 기존 payload의 다른 null 필드를 제거하지 않는다.
  기존 run의 값 비교·manifest_digest·canonical digest를 그대로 유지한다.
- 블록에는 PR/이슈/일반 댓글/리뷰/코드 댓글 수, 목록 탐색 완료 여부,
  관측 시작·끝, 실패·제외 수, 관계 목록의 누락을 담는다.
  부모/하위 기록의 개수는 봉인된 예정 항목 기준이다. body-free 실패 outcome도
  포함하며 expected_items는 items와 outcomes의 전체 수와 일치시킨다.
  발견한 원본 수와 성공 적용·unchanged·실패·차단 수는 별도 지표로 구분한다.
  기존 100,000-item run 상한을 넘기 전에 준비를 중단하고 누락/하한을 표시한다.
- 기존 commits/documents/head_documents 필드는 유지한다. B-only 실행은 A 수집 수가 0이다.
  `branches=[]`, `commits=0`, `documents=0`, `head_documents=[]`와 명시적인
  `gaps` 배열을 공급한다. gaps에는 실제 B 누락 코드를 넣고 누락이 없을 때만 빈 배열이다.
  A/B를 혼합한 새로운 manifest를 이번 단계에서 만들지 않는다.
- GitHubCollectorItem, run 응답, OpenAPI/frontend 생성 타입을 함께 확장한다.
  기존 GitHub Run의 provider discriminator는 그대로 유지한다.
- seal에서 종류별 항목/outcome 수와 coverage·expected_items를 대조한다.
  create_run은 선언된 개수 합계와 expected_items를 확인하고, 수집 범위/개수의
  동일 UUID 재전송 비교를 유지한다. 아직 전송되지 않은 실제 항목은 여기서 검증하지 않는다.
  finish에서 검증된 external_id 종류별 receipt 수를 선언과 대조하여 불일치를 거절한다.
  body-free outcome도 해당 종류로 집계하며 재전송은 동일 receipt 한 건이다.

실제 v1 fixture로 config digest, 요청 직렬화, 봉인 검증, receipt 재전송과
기존 run 응답을 검증한다. 새로운 기본값 때문에 기존 요청이 409가 되면 실패이다.

## 5. 준비·재개·미리보기

### CLI와 수집 순서

```sh
.venv/bin/python -m app.collectors.github_discussions init-config --help
.venv/bin/python -m app.collectors.github_discussions prepare --help
.venv/bin/python -m app.collectors.github_discussions seal --help
.venv/bin/python -m app.collectors.github_discussions apply --help
```

명령은 A와 같은 prepare → seal → 명시적 apply → cleanup 흐름을 제공한다.
세부 옵션은 구현 시 `--help`와 검증 가이드에 고정한다.
`--github-cli-auth`는 기존 방식처럼 gh 토큰을 메모리에서만 사용한다.
소스는 선택한 저장소의 GET API로 제한하고 토큰·개인 원문은 출력/커밋하지 않는다.

1. 저장소 ID와 접근 권한을 확인하고 새 preparation UUID/관측 시작 시각을 고정한다.
2. PR/이슈 목록은 `state=all`, `sort=created`, `direction=asc`, 페이지당 100으로 읽는다.
   시작 시각 이후 생성된 항목은 다음 실행 대상으로 분리한다. 시작 전 생성된 항목이
   관측 중 수정되는 것은 허용하며 실제 관측 시각을 남긴다.
3. 부모의 상세 정보와 일반 댓글을 읽는다. 부모가 PR일 때만 리뷰·코드 리뷰 댓글·
   PR 커밋을 추가로 읽는다. 순수 이슈에는 `/pulls/` 하위 API를 호출하지 않는다.
   필터링한 구조화된 항목을 private preparation에 저장한다.
4. 같은 ID는 중복 제거한다. 페이지 반복, next URL의 외부 호스트·다른 저장소,
   잘못된 ID와 예산 초과를 감지한다. 부모가 수집 중 사라지면 억지로 생성하지 않는다.
5. 모든 단계의 진행 위치, 획득한 ID, 요청·용량 예산, retry 시각을 저장한다.
   quota/retry-after에 따라 재개하며, 새 디렉터리로 quota를 우회하지 않는다.
6. seal은 자료·개수·해시·누락을 검증한다. 이후 manifest와 항목은 수정 불가다.

### 가변 데이터와 캐시

커밋과 달리 토론은 수집 중에도 바뀐다. 한 시점의 원자적 스냅샷을 보장하지 않는다.
새 실행은 새 preparation 디렉터리에서 시작해 이전 실행 캐시를 사용하지 않는다.
private 캐시는 해당 실행에서 관측한 응답으로 취급한다.

부모별 수집 전/후 상세 GET은 캐시를 우회한다. 부모 updated_at이 달라졌으면
해당 부모 작업의 봉인 전 staged 결과와 캐시를 폐기하고 1회 다시 읽는다.
다시 바뀌면 확보한 자료를 보존하고 MUTABLE_SOURCE_CHANGED 누락을 표시한다.
부모 시각이 같아도 모든 하위 편집을 감지했다는 의미는 아니다.
중단 후 재개한 부모는 수집 전 상세 GET부터 다시 검증한다.
완료한 부모는 최초 관측 자료로 유지하며 관측 구간을 표시한다.

`walk_complete`는 API 페이지 탐색 완료를 뜻한다. 이것과 원자적 스냅샷 여부를
분리한다. 항상 `Snapshot collected over a time window`를 안내하고,
동시 변경·접근 실패·예산 중단 등 발견한 누락은 Partial로 처리한다.

PR 커밋 API는 최대 250개를 제공한다. PR 상세 commits 수와 실제 수를 비교한다.
상한/불일치가 있으면 PR_COMMIT_MEMBERSHIP_INCOMPLETE로 표시하고 연결 목록을
하한으로 취급한다. 이번 단계에서는 A의 브랜치 커밋 목록으로 완전성을 추정하지 않는다.

### 필터·용량·실패

- 기존 민감정보 필터를 본문·제목·diff hunk·경로·작성자 표시 등 저장할 문자열에 적용한다.
  URL은 선택 저장소의 원본 연결인지 확인하고, 민감 query나 사용자 임의 URL을 제거한다.
- 구조화 필드별 제한과 canonical 전체 1 MiB 제한을 함께 지킨다.
  PR 커밋 목록·diff·본문이 합산 초과하지 않도록 예산을 배분한다.
- 자식은 부모의 과대 본문을 복제하지 않는다. 큰 부모가 실패해도 유효한 자식은
  부모 연결만 갖고 남을 수 있으며 부모 미보존 사유를 표시한다.
- 401/403/rate limit/404/전송 실패/유효성 오류/필터 제외/본문 일부 제거를 구분한다.
  새 gap 코드는 기존 enum을 확장하며 같은 이름이 API·manifest·Sources에서 일치해야 한다.
- 성공적으로 확인한 0개는 Empty이고, 접근 실패로 0개인 경우 Failed/Partial이다.
  실제 저장소가 0개여도 GitHub에 검증용 PR·이슈를 만들지 않는다.

미리보기에는 종류별 수, PR·이슈 제목/번호, 상태, 개별 토론, 리뷰 상태,
원본/수집 시각, 누락, 관련 커밋의 역할을 표시한다. 민감자료는 private 파일에만 둔다.

## 6. 적용·권한·삭제

기존 CollectionRun 생성 → items/outcomes → finish와 원자적 receipt 저장을 사용한다.
적용 전·재개 시 소유자/API/device/preview 일치와 소스 수집 허용 여부를 확인한다.
새 종류도 서버에서 identity·repository·parser·filter·digest를 검증한다.

삭제는 기존대로 **개별 Entry 삭제**이다. 부모 삭제가 자식 일괄 삭제를 뜻하지 않는다.
삭제된 부모는 재수집 억제되며, 부모 본문을 자식이나 보존 버전으로 재구성하지 않는다.
남은 자식은 자신의 권한으로 조회하되 `Parent not retained`를 표시한다.
삭제 확인 문구도 전체 토론 삭제로 오해되지 않게 `Delete this record`를 사용한다.
자식 삭제는 해당 자식만 억제한다. 소스 수집 중지는 같은 저장소의 모든 B 기록에 적용한다.

부모·자식·관련 커밋 조회는 항상 같은 owner/repository를 검증한다.
외부 링크로 다른 저장소의 Entry를 연결하지 않는다. 부모 AI 허용이 자식을
자동 허용하지 않으며, 이번 단계에서 토론 전체 AI 묶음이나 외부 AI 전송은 만들지 않는다.

## 7. 저장소 탐색과 Search

### API

기존 GitHub repository 서비스에 typed B 분류와 개수를 추가한다.
잘못된 구조의 기존 자료는 Unclassified에 유지한다.

- `GET /github-repositories/discussions?scope=repo:<id>`: PR/이슈 그룹 목록.
  기존 `app/api/github_records.py`에 추가한다.
  종류/상태 필터와 offset/limit, source event date 내림차순·안정 ID 순서를 사용한다.
- `GET /github-repositories/discussions/{parent_kind}/{parent_id}?scope=repo:<id>`:
  보존된 현재 부모 요약과 접근 가능한
  자식 목록. 자식은 event_at 오름차순·미상 날짜 뒤·안정 ID 순서로 페이지를 나눈다.
  날짜 미상은 원본 순서가 확실하다는 안내를 하지 않는다.
  parent_kind는 `pull_request|issue`, parent_id는 GitHub 원본 numeric object ID이다.
  lifhop Entry ID나 PR/이슈 번호가 아니다. scope와 함께 parent_external_id를 구성한다.
- 선택적 `focus_entry_id`: 동일 소유자·저장소·부모 관계를 검증한 후 해당 자식의
  페이지를 계산한다. 삭제되거나 다른 토론의 ID면 안전한 not-found 응답을 돌려준다.
- 부모가 미보존이어도 남은 자식의 parent_external_id로 orphan 그룹을 조회할 수 있다.
  부모 본문/제목을 노출하지 않고 상태 필터에는 `Unknown`으로 분류한다.

그룹을 만든 뒤 목록 페이지를 나눈다. 부모·자식 페이지당 20, 최대 100을 적용한다.
부모가 있으면 그룹 정렬·날짜 필터는 부모 생성일 기준이다. orphan은 보존된 자식의
가장 이른 유효 event_at을 사용하고 `First retained comment date`로 표시한다.
부모의 생성일로 표시하지 않는다. 전부 날짜 미상이면 NULLS LAST·parent_kind/ID로
안정 정렬한다. 기간 필터에서는 제외하고 `Unknown date` 필터로 따로 찾을 수 있게 한다.
자식 시간은 토론 내부 정렬 기준이다.
전체 자식 본문을 목록 조회에서 로드하지 않는다. 현재 버전 메타데이터 분류를
SQL 조회에 반영하고, 버전 선택 변경이 목록·thread·검색에 함께 반영되는지 검증한다.
기존 `/entries/{entry_id}/github-presentation`의 typed payload/관계 조회도 B 종류로
확장한다. 개별 Entry reader와 sidebar에서 같은 토론 연결을 사용할 수 있어야 한다.

관련 커밋은 같은 owner/repository에서 보존된 SHA만 내부 링크로 연결한다.
미수집 SHA는 `Not retained locally`와 검증한 GitHub 원본 링크를 표시한다.
base/head/merge/review/original_review/PR member 역할을 구분한다.

### 화면

- `/repositories/github`에 Discussions 탭 추가. 상단에 PR/이슈 수와 댓글/리뷰 수를 분리한다.
- 행은 종류·번호·짧은 제목·상태·원본 날짜·리뷰 필요/누락 표시를 갖는다.
- 토론 화면은 부모 본문과 시간 순 자식 목록. 리뷰 상태, 코드 위치/diff는 접어서 읽는다.
- Markdown/HTML은 기존 안전한 renderer를 재사용한다. 임의 원본 HTML은 실행하지 않는다.
- Entries는 계속 저장소 한 카드. 전체 댓글 수만큼 카드를 늘리지 않는다.
- Search는 개별 Entry 결과를 유지하고 PR/이슈 맥락과 토론 focus 링크를 추가한다.
- URL에 tab/filter/offset/parent/focus와 안전한 returnTo를 보존한다.
  새로고침·새 탭·뒤로가기·sidebar가 같은 위치로 돌아온다.
- Sources는 B 관측 구간과 유형별 수·누락을 표시한다. A의 커밋/문서 결과를 바꾸지 않는다.
- 새 UI 문구는 영어로 작성한다. 320/390/768/1440px에서 긴 제목/코드 위치를 확인한다.

## 8. 검증 계획

### 자동 검증

1. 정규화/identity: PR 중복 제거, Issues의 PR ID 혼동, 부모 번호 충돌,
   삭제된 작성자, 빈 승인 리뷰, PENDING/날짜 미상, 코드 답글·원래 위치.
2. 가변 수집: 순수 이슈에 PR 전용 API를 호출하지 않음, 다중 페이지,
   반복/악성 next, 목록 중복, 동시 생성/편집,
   부모 재시도, 재개 캐시, 권한 부족·quota·예산·250개 커밋 관계 제한.
3. 필터: 제목·본문·diff·URL 비밀정보, 과대 부모·자식, 총 1 MiB 경계,
   body-free 실패 outcome. 미리보기에 비밀 값이 나타나지 않는지 확인한다.
4. 계약: A v1 config/manifest/digest/receipt 및 기존 null 직렬화 회귀,
   B-only 필수 coverage 필드·빈 branches·실제 gaps, 예정 종류별 수 불일치 거절,
   B types/OpenAPI 생성 일치, scope/owner/parser/filter 불일치 거절,
   변경된 봉인 자료 거절.
5. 격리 PostgreSQL + 실제 HTTP: 같은/동등 미리보기 재전송,
   updated_at 편집·오래된 자료·수정 시각 없는 리뷰의 버전 선택,
   주석 보존, 소스 수집 중지, 부모/자식 삭제 억제, 타 소유자 focus 차단.
6. 탐색: 그룹 후 페이지네이션, GitHub 원본 부모 ID로 orphan 접근,
   orphan 날짜 fallback/미상 날짜 필터, 현재 버전 전환, 검색 focus,
   미수집/다른 저장소 SHA, 날짜 미상, 기존 A·Codex·일반 Entry 회귀.
7. frontend 테스트·lint·build, 관련 backend 테스트 후 가능한 전체 suite,
   Chromium에서 responsive·returnTo·직접 URL·새 탭·빈 결과·오류 상태 확인.

### 실제 저장소와 소유자 확인

구현 시 우선 `moonkongv2/jy_yamyam`의 PR/이슈 개수를 read-only로 확인한다.
개수는 현재 미확인이다. 접근 가능한 기록이 있으면 소수 표본의 원본과 미리보기를
대조한 후 전체 준비·격리 적용을 검증한다. 0개면 Empty를 검증하고 합성 fixture로
토론·리뷰·답글 UI를 확인한다. 합성 기록은 `[Synthetic]` 표기를 사용한다.
private/org 권한은 실제 검증한 범위를 명시하며 검증되지 않으면 한계로 남긴다.

소유자 확인 가이드 `GITHUB_DISCUSSIONS.md`를 구현과 함께 작성한다.
필요한 backend/frontend/DB 실행, prepare/seal/apply 명령, private 미리보기 위치,
`http://localhost:5173` 확인 순서를 제공한다. 확인할 동작:

1. Sources에서 해당 실행의 종류별 수와 누락을 확인한다.
2. Entries → 저장소 → Discussions에서 PR·이슈가 한 행씩 보이는지 확인한다.
3. 토론을 열어 본문/일반 댓글/리뷰/코드 댓글과 원본 날짜를 대조한다.
4. Search에서 댓글을 찾아 정확한 토론 위치로 이동하고 목록으로 돌아온다.
5. 격리 fixture로 재전송·버전 선택·부모/자식 개별 삭제 안내를 확인한다.

개인 계정 적용은 소유자가 미리보기를 검토한 뒤 명시적으로 실행한다.

## 9. 구현 순서와 커밋 경계

1. **계약/서버:** typed payload·normalizer·coverage·receipt 검증 확장,
   B 테스트 및 A v1 회귀. `feat: add GitHub discussion evidence contracts`
2. **collector:** B 전용 config/CLI·페이지 수집·가변 관측·필터·봉인·apply,
   합성 fixture·실제 준비/격리 HTTP 확인. `feat: collect GitHub PR and issue discussions`
3. **탐색/UI:** 그룹/토론 API, Discussions 탭, Search focus, Sources 결과,
   responsive/권한 확인. `feat: add GitHub discussion browsing`
4. **가이드/상태:** 검증한 범위에 맞춰 GITHUB_DISCUSSIONS.md와 CURRENT.md 작성.
   개별 Entry·원본 시각 없는 리뷰·관측 구간의 장기 결정은 DECISIONS.md에 기록한다.
   ROADMAP은 milestone 범위/순서가 달라질 때만 수정한다.

각 경계는 테스트가 통과한 검토 가능한 상태여야 한다. 커밋 생성은 별도 승인 시 진행한다.
소유자에게 결과·실행한 검사·남은 한계·확인 절차를 전달한 후 다음 slice로 넘어간다.
Phase 3 진입 전 A/B 실제 수집 범위와 빈 결과/권한 한계를 함께 정리한다.

## 10. 참조

- 저장소 계약: `GITHUB_BACKFILL_PLAN.md`, `GITHUB_BACKFILL.md`,
  `GITHUB_REPOSITORY_VIEW_PLAN.md`, `CURRENT.md`, `DECISIONS.md`.
- [GitHub Issues REST API: PR 포함 및 ID 구분](https://docs.github.com/en/rest/issues/issues)
- [GitHub PR REST API: PR 상세·커밋 목록 제한](https://docs.github.com/en/rest/pulls/pulls)
- [GitHub 리뷰 REST API: 상태·제출 시각](https://docs.github.com/en/rest/pulls/reviews)
- [GitHub 일반 댓글 REST API](https://docs.github.com/en/rest/issues/comments)
- [GitHub 코드 리뷰 댓글 REST API](https://docs.github.com/en/rest/pulls/comments)

API 세부사항은 2026-10-06 공식 문서 기준이며, 구현 시 기존 API version 헤더와
실제 응답 fixture를 대조한다.
