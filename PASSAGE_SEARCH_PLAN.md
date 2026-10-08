# Phase 3.2A — RAG를 위한 로컬 문단 검색

작성: 2026-10-08. 상태: 3.2A 구현·로컬 검증·사용자 화면 확인 완료.

## 1. 목표와 단계

사용자가 Search에서 문장으로 질문하면 관련 문단을 보고, 해당 문단의
원본 버전과 위치를 확인한다. 새 기록·수정·버전 선택·삭제가 검색에도 반영된다.
이 단계는 이후 RAG가 사용할 검색 기반이다. 답변 생성은 3.3에서 구현한다.

- **3.2A 이번 범위:** 문단 저장·로컬 단어 검색·순위·출처 화면·평가 비교.
- **3.2B 후속 판단:** 의미 검색/임베딩/pgvector의 효과·비용·권한·실행 환경 검토.
- 기존 Exact phrase 검색과 Entry·버전·수집·AI 정책을 유지한다.
- 새 AI 서비스·Redis·OpenSearch·SQS 작업 종류·Python 패키지를 추가하지 않는다.
- PostgreSQL 17의 FTS와 GIN 인덱스를 사용한다. 언어 번역·의미 검색으로 설명하지 않는다.

### 현재 근거와 한계

승인된 3문항의 문장 전체 검색 결과는 모두 0개였다. 보조 키워드의 지정
근거 순위는 12~39위였고 평균 group recall@20은 1/3이었다. 합성 기록이
상위 20개를 밀어낸 경우는 없었다. 동일 승인 문장이 여러 README 스냅샷에
반복된다. 따라서 문장 전체 일치, 순위, 스냅샷 처리와 평가 단위를 함께 다룬다.

3문항은 같은 영문 문서에 기반한다. 한국어 질문 2개가 영문 본문에 일치하지
않는 문제를 로컬 단어 검색만으로 해결한다고 약속하지 않는다. 영어·한국어
동일 언어, 한국어→영어, 코드 식별자, 다른 출처/소유자, 부정 사례를 나눠 검증한다.
파일명 같은 약한 단어로 같은 문서를 찾은 것과 실제 정답 문단을 찾은 것을 구분한다.
3.1의 최종 약 20문항·일상·복수 출처·역사·제외/수집 누락 목표는 여전히 남아 있다.

## 2. 관찰 가능한 사용자 흐름

1. 로그인 → 기존 `/search` → **Passages** 선택.
2. 질문 입력, 기존 출처·날짜·유형·상태 필터 선택 → 검색.
3. 결과에서 제목, 일치 문단, 기록/출처 날짜, 버전, 출처 맥락을 확인.
4. **View passage** → 서버가 재검증한 원본 버전의 해당 구간.
5. **Open record** → 현재 Entry 읽기. 두 화면의 버전이 다른 경우 명시.
6. 목록으로 돌아가도 모드·질문·필터·페이지 유지. 새로고침·새 탭도 동일.

컨트롤은 영어다. 원문·질문은 작성 언어를 보존한다. 첫 진입/빈 질문에는
검색 요청을 하지 않는다. 빈 결과, 인덱스 미완료, 제한으로 누락된 자료,
일부 소스 삭제/변경은 구분해 표시한다. AI 답변처럼 보이는 생성 문장을 넣지 않는다.

## 3. 데이터 모델과 분할

### 새 테이블

`EntryPassage`: `id`, `version_id`(EntryVersion FK, CASCADE), `ordinal`,
`field`(title/content), `start`, `end`, `text`, `passage_hash`, `projection_version`,
`search_vector`(tsvector). unique(version_id, projection_version, ordinal).
offset은 Python Unicode 문자 기준, end는 exclusive다. 원문 정규화/번역을 하지 않는다.
`text`는 반드시 해당 EntryVersion 필드의 `[start:end]`와 일치한다.

`PassageIndexState`: entry_id PK/CASCADE, indexed_version_id, projection_version,
status(pending/ready/partial/failed), passage_count, bounded gap_codes, indexed_at.
EntryVersion.content_hash 및 필요 projection digest로 파생 상태를 검증한다.
오류에는 원문·전체 예외·비밀번호/접속 URL을 저장하지 않는다.

owner 컬럼 복제를 요구하지 않는다. 모든 조회는 Passage→Version→Entry를
조인하여 owner와 `Entry.current_version_id`를 확인한 뒤 순위/limit을 적용한다.
역사 버전 Passage를 현재 검색으로 노출하지 않는다. FK/버전 조인 불일치는 거절한다.
GIN(search_vector), version/ordinal B-tree 및 상태 조회 인덱스를 migration에 둔다.

### 분할 규칙 v1

- title은 별도 작은 Passage. 본문은 빈 줄·Markdown 문단/목록·메시지 경계 우선.
- 기본 1,200자, 최대 2,000자, 긴 문단은 200자 overlap으로 결정론적으로 분할.
- 줄/코드 블록을 가능하면 보존하되 상한을 넘는 블록도 동일 규칙으로 분할한다.
- 같은 입력+projection_version은 같은 offsets/hash/순서를 만든다.
- 최대 입력 8 MiB, 최대 512 Passage/Entry, 저장할 누락 코드·개수 상한 고정.
  예산 초과는 partial로 보이고 기존 Exact phrase 검색 경로는 이용 가능하다.
- 식별자·URL·숫자·이모지·결합 문자·CRLF·반복 문장을 보존한다.
- annotation은 원본 evidence로 섞지 않는다. PDF/OCR/이미지 파싱은 이번 범위 밖이다.

### Codex와 도구 기록

provider 처리는 기존 presentation/normalizer 옆의 작은 adapter에 둔다.
기본 Codex 본문은 읽기 화면과 동일한 user/assistant 구간이며 명시된 commentary,
command/result/diff는 work 구간으로 분리한다. unknown 메시지에 임의 재분류를 하지 않는다.
원본 전체 `EntryVersion.content`로의 위치 mapping을 normalizer 순서와 message ID로
검증한다. 같은 문장에 단순 첫 find()를 적용하지 않는다. 구조/위치 검증이 안 되면
해당 본문을 partial로 제외하고 제목만 인덱싱한다. 기존 Exact phrase의 경고 있는
fallback은 유지한다. work 구간은 기존 include_work_commentary 옵션에서만 검색한다.

## 4. 동기화와 기존 자료 backfill

### 현재 버전 변경의 동일 트랜잭션 반영

`sync_current_passages(db, entry)`를 공통 서비스로 둔다. 현재 선택된 버전에 대해
기존 파생 Passage를 교체하고 상태를 갱신한다. EntryVersion은 수정하지 않는다.
current/projection 교체 시 해당 Entry의 구 Passage를 같은 트랜잭션에서 삭제한다.
선택되지 않은 역사 버전의 문단은 보관하지 않는다. 복원하면 새 ID로 재생성하며
EntryVersion 원본은 기존 보존 규칙을 따른다. 파생 인덱스가 버전 수만큼 누적되지 않는다.
다음 쓰기 경로를 각각 명시적으로 연결하고 테스트한다.

- `entries.py`: manual 생성, 내용/제목/유형/날짜 변경.
- `source_history.select_version`: imported 새 버전 선택, 과거 버전 복원.
- `external_entries.py`: current version가 없는 기존 레코드 복구, idempotent replay.
- 최신 선택되지 않은 retained 후보 버전은 인덱싱하지 않는다.
- replay가 current/내용/projection을 바꾸지 않으면 파생 데이터도 중복 생성하지 않는다.

기존 owner_lock→record lock 순서를 유지한다. 실제 DB 오류가 나면 원본 변경과
인덱스 쓰기를 함께 rollback한다. 알려진 예산/구조 누락은 partial 상태로 저장한다.
정책 변경은 본문 재생성을 요구하지 않지만, 조회/향후 AI 준비 시 현재 정책을 다시 확인한다.
lifhop 삭제는 FK cascade로 파생 본문도 삭제하고 즉시 조회에서 제외한다.

### 기존 데이터

Migration은 schema와 pending 상태만 만들고 개인 본문 전체 backfill은 하지 않는다.
`scripts/index_passages.py --email ACCOUNT`는 getpass로 인증하고 owner 범위에서만
미완료·projection 변경 항목을 keyset으로 처리한다. batch 기본 20, entry별 bounded
읽기, 짧은 트랜잭션/owner lock, statement timeout 5초, lock timeout 2초, 재개 지원.
비밀번호·원문은 출력하지 않고 ready/partial/failed 개수와 다음 cursor만 출력한다.
savepoint로 실패 항목을 분리하고 원본 Entry/버전/수집 receipt는 변경하지 않는다.
동시에 수정/삭제된 항목은 잠금 후 current/hash를 다시 읽는다. 준비된 이전 내용으로
새 current를 덮어쓰지 않는다. 종료·실패·재실행 시 동일 버전 중복은 발생하지 않는다.

인덱스가 없는 기존 자료는 새 모드에서 미완료로 표시한다. 검색 GET 요청은
backfill/SourcePolicy 생성/버전 변경을 하지 않는다. 검색이 빈 결과인 것과
자료가 아직 인덱싱되지 않은 것을 혼동하지 않도록 owner coverage를 반환한다.

## 5. 검색·순위·스냅샷 처리

- q 최대 256자, 의미 있는 토큰 최대 16개. 불필요한 영어 기능어만 고정 규칙으로
  제거하고 언어/파일별 정답에 맞춘 동의어 목록을 만들지 않는다.
- 동일 설정의 `to_tsvector('simple', ...)` / 안전한 query 변환 함수를 사용한다.
  사용자 문자열을 tsquery/SQL 문법으로 직접 연결하지 않는다.
- 남은 토큰의 OR 후보를 가져오되 매칭 개수와 `ts_rank_cd`로 구분한다.
  전체 phrase/식별자 일치는 literal escape를 적용해 별도 boost한다.
- 순위는 전체 phrase 일치 → 서로 다른 본문 토큰 일치 수 → FTS 관련성 순으로
  고정하고, 출처 날짜/ID는 tie-breaker로 사용한다. 제목 공통어가 모든 본문을
  동일하게 올리지 않도록 title-only 결과와 실제 본문 일치를 구분한다.
- v1 점수/토큰 규칙을 파일에 고정하고 평가 보고서에 configuration hash를 기록한다.
  파일명만 맞으면 높은 검색 점수가 나오는 현상을 부정 사례로 검증한다.
- 기본 결과는 current EntryVersion만, source-deleted 기록은 제외한다.
  source_state=deleted를 명시하면 로컬 보기에서 출처 삭제 표시와 함께 포함한다.
  lifhop-deleted 기록은 어떤 옵션에서도 포함하지 않는다.
- 기존 source/date/type/state/work 필터를 owner 검증과 함께 후보 limit 전에 적용.
  날짜는 기존 Asia/Seoul 경계, event_at 미상 기록의 취급도 기존과 동일.
- 기본 최대 2개 Passage/대표 Entry로 한 긴 기록의 점유를 제한한다.
  owner/필터 적용 → 동일 문단 그룹과 대표 선택 → 대표 Entry별 순위의
  ROW_NUMBER로 2개 제한 → 최종 정렬 → LIMIT/OFFSET을 모두 DB에서 수행한다.
  전체 후보를 Python으로 읽어 그룹화하거나 페이지를 자른 뒤 합치지 않는다.
  total은 같은 조건의 제한 후 표시 그룹 수를 DB에서 집계한다. 본문 대신
  ID/점수/그룹 키로 집계하고 해당 페이지에 필요한 본문만 읽는다.
- GitHub 문서의 동일 문단은 owner·검증된 repository scope·path·field·본문 hash가
  모두 같을 때만 그룹화한다. 서로 다른 문단/경로/저장소/날짜 범위는 합치지 않는다.
- 그룹 대표는 필터 범위 안에서 알려진 최신 source event date, 그 뒤 ID로 고른다.
  최신 GitHub HEAD라는 의미를 부여하지 않는다. 출처 날짜와 retained snapshot
  label, 묶인 개수를 보여주고 펼쳐 다른 정확한 버전/위치를 볼 수 있게 한다.
  첫 카드에는 alias metadata 최대 5개만 포함하고 전체 개수·더 보기 여부를 표시한다.
  추가 alias는 동일 필터로 재검증하는 별도 페이지 API로 읽으며 한 번에 최대 50개다.
- 잘못된 provider metadata는 Entry별로 남기고 추측해 병합하지 않는다.
  날짜 필터 후 그룹화하며 다른 날짜의 링크를 섞지 않는다.
- 페이지마다 같은 corpus에서는 stable ordering/offset. concurrent 수정 시 결과가
  달라질 수 있음을 유지한다. 모든 일치문단은 React text node로 안전하게 렌더링한다.

## 6. API와 UI

- `GET /passages/search`: q, source, type, source_state, date_field/from/to,
  include_work_commentary, limit(기본20/최대50), offset. 필수 q 없는 요청은 422.
- 명시 response schema: result passage ID, Entry/version IDs, field/offsets/hash,
  bounded excerpt, title, source/date, completeness/gaps, context refs, grouped snapshot
  metadata, total, owner index coverage, timezone, search/projection version.
- 검색 DB statement timeout은 5초. 초과하면 명시된 search_timeout 코드의 503을
  반환하고 UI는 실패와 재시도를 안내한다. 빈 결과나 잘린 total로 대체하지 않는다.
  한 결과의 본문은 최대 2,000자, 전체 응답은 최대 1 MiB로 고정하고 상한을 검증한다.
- `GET /passages/{id}`: owner/current/hash 상태 재검증. 삭제/다른 owner/교체된
  문단은 모두 404 및 UI의 unavailable·새 검색 안내. stale 본문은 반환하지 않는다.
- `GET /passages/{id}/snapshots`: 동일 query/출처/날짜/work 필터와 그룹 키를
  서버에서 재검증하여 alias의 버전/위치 metadata만 페이지 반환한다.
  limit 기본20/최대50, offset, total; 기존 필터 밖 버전과 다른 owner는 제외한다.
- 기존 `GET /entries/search` schema/정렬/식별자 literal 동작은 유지한다.
- Search에 Exact phrase(기존 기본값)/Passages 모드. `mode=passages`만 URL에 추가하고
  기존 URL·Search→reader→목록 복귀 경로는 유지한다. mode별 query cache를 분리한다.
- Passage 카드와 `/passages/:id` 읽기 페이지는 기존 session/repository refs와
  로그인·삭제 오류 처리를 재사용한다. Return URL은 기존 허용 경로 검증을 유지한다.
- 임의 HTML/ts_headline 결과를 dangerouslySetInnerHTML로 넣지 않는다.
- 생성 API types, routing, 필터 파서(listParams), hooks, loading/empty/partial/error,
  keyboard 접근성, 390/768/1440px를 함께 검증한다.

## 7. 평가: 동결된 정답과 새로운 검색 단위

기존 3문항/질문/키워드/claims/anchor와 두 baseline 파일을 그대로 보존한다.
동일 corpus snapshot에서 기존 literal, 새 passage-natural, 새 passage-keywords를
각각 실행한다. 같은 backend service를 API와 평가 CLI가 호출한다.

- Entry-level 기존 점수와 Passage-level 새 점수를 구분한다. 새 점수는 해당
  version/field의 반환 위치가 gold를 덮는 경우만 성공이다. title-only hit는 body
  evidence의 성공으로 처리하지 않는다.
- gold가 여러 Passage에 걸치면 같은 version/field에 속한 결과 범위의 합집합이
  전체 gold 구간을 덮어야 한다. 다른 버전을 이어 붙이거나 gap을 허용하지 않는다.
  top-K 안의 결과만으로 전체 구간을 덮을 때 성공이다. 유효 rank는 처음으로
  전체 구간을 덮는 최소 K, 즉 필요한 결과의 최대 rank이며 MRR에도 이를 사용한다.
  예를 들어 필수 문단이 2위·15위면 rank 15, top5/10 실패·top20 성공이다.
- 동일 문단 그룹은 반환된 검증된 alias의 version/offset까지 확인한다. 대표 버전만
  보고 다른 날짜의 근거를 성공으로 처리하지 않는다. group membership을 보고서에 기록한다.
  카드의 alias 5개 상한 때문에 정답을 놓치지 않도록 동일 read-only snapshot에서
  검색 서비스의 필터/그룹 조건으로 gold alias membership을 DB 조회한다.
  평가 보고서에는 확인한 gold alias ID/구간과 그룹 개수만 담고 전체 alias를 적재하지 않는다.
- 다른 스냅샷의 유사/부분 문장을 사후 정답으로 추가하지 않는다. 동일 본문 hash의
  검증된 alias 이외 확장은 별도 owner 승인·새 revision·별도 점수로만 다룬다.
- top 5/10/20, 모든 필수 근거 찾기, MRR, historical N/A, 실패 포함 분모 규칙 유지.
  auxiliary는 독립 query 평균→case 평균, 두 키워드 결과를 합치지 않는다.
- 기존 보고서와 같이 원문/질문/정답/annotation은 출력하지 않는다. passage IDs,
  검증 상태, 집계, version/구간 metadata만 포함한다.
- latency, backfill 시간, Passage 수/DB 크기, index coverage·누락을 집계한다.

### 완료 기준과 실패 취급

동일 언어·기본 문단·숫자·식별자 합성 사례는 실제 정답 문단이 top5 안에
나오고, 제목만 맞는 오답이 정답으로 채점되지 않아야 한다. 삭제·다른 owner·
stale current·정책 누락/차단 전송은 0건이다. 지정 query budgets 안에 종료한다.

실제 pilot은 top20 group recall 개선과 순위를 보고하되 3/3을 출시 약속으로
하지 않는다. 교차 언어가 여전히 실패하면 별도 실패로 남긴다. 그 실패를 감추기
위해 영문 query로 교체하거나 gold를 변경하지 않는다. recall 목표 0.80,
all-groups 0.70은 현재보다 다양한 승인 세트에서 추후 확인할 품질 목표다.
기능·보안 검증은 통과해야 완료하며 품질이 부족하면 결과와 한계를 명시하고
3.2B의 로컬/허용된 외부 의미 검색 비교 범위를 결정한다.

## 8. 구현 순서와 커밋 경계

1. 모델/migration, 분할·위치 mapping, 합성 fixture → upgrade/rebuild/delete 검증.
2. 현재 버전 동기화, backfill CLI/coverage → 각 writer 경로·재실행·동시 변경 검증.
3. 검색 API/ranking/grouping/reader → owner/filters/삭제/순위/페이지 검증.
4. Search UI 모드/문단 카드/reader/복귀 → frontend tests/lint/build/API types.
5. 평가 adapter와 body-free 비교 보고서 → frozen pilot 비교, 한국어/교차언어 한계.
6. 사용자 확인 후 CURRENT/DECISIONS 갱신 및 다음 의미 검색 범위 제안.

커밋은 schema/동기화, 검색 API/평가, UI/확인 문서 단위가 적절하다.
첫 migration/동기화 검증 전 기존 대용량 import를 사용자 계정에 다시 돌리지 않는다.
실제 계정 backfill은 disposable migrated DB 검증 후 로컬 인증으로 실행한다.

## 9. 검증과 사용자 확인

테스트: 결정론/offset/중복/코드/다국어/큰 입력, Codex phases·order mapping,
manual/ChatGPT/Markdown/Codex/GitHub/current 없는 복구/retained/replay/restore,
FK purge, owner/filter-before-limit, source 삭제/AI 차단, lock/content 동시 변경,
불완전 index 표시, group/date/pagination, paragraph gold 경계 및 순위.
전체 backend, frontend tests/lint/build, migration upgrade, generated types,
실제 HTTP와 합성 Chromium 검증을 수행하고 실행 결과/실패를 구분한다.

구현 종료 시 여기서 직접 안내할 사용자 절차:

1. DB/migration/backfill의 실제 실행 여부와 필요 명령, 서버 실행 상태를 명시.
2. `/search`에서 Passages를 선택해 준비된 질문을 검색하고 문단과 원본 위치 확인.
3. disposable 노트 수정/삭제 후 이전 문단이 현재 결과에서 사라지는지 확인.
4. 영문 keyword·영문 question·한국어 question 결과를 분리해서 보여줌.
5. 실제 pilot 개선 전후 표와 실패 문항을 함께 제시. 사용자가 새 근거를 직접
   찾아오도록 요구하지 않는다. 개인 원문을 agent/reviewer에게 추가 제공하는
   경우 기존 명시적 허용 범위를 재확인한다.

## 10. 기술 근거와 검토 기록

PostgreSQL query 변환·관련성 함수는 [17 문서](https://www.postgresql.org/docs/17/textsearch-controls.html),
FTS 인덱스 선택은 [GIN 문서](https://www.postgresql.org/docs/17/textsearch-indexes.html)를 따른다.
기존 source_history의 owner lock/버전 선택, ai_policy의 전송 재검증 경계,
evaluation의 immutable revisions/failed denominators를 재사용한다.
일회성 agent 원문 읽기 허용은 앱의 embedding/answer 전송 허용으로 사용하지 않는다.

Antigravity compact 계획 검토 1회 완료. 첫 실행은 10분 시간 초과로 의견을 받지
못했고, 계획 파일만 읽는 재시도로 검토를 완료했다. 개인 자료는 제공하지 않았다.
지적 3건 모두 수용, 반려/사용자 판단 필요 0건:

- high: 그룹화·Entry 상한·total·페이지 처리의 DB 수행 순서를 명시.
- medium: 여러 문단으로 gold를 덮을 때의 rank/top-K/MRR 기준을 명시.
- medium: 구 문단 즉시 정리와 stale 링크 404 응답을 일치시킴.

추가 자체 확인으로 검색 timeout·응답/alias 상한과 평가의 alias 검증 경계를 명시했다.
검토 당시에는 계획만 수정했다. 후속 구현과 실제 검증 상태는 CURRENT.md와
PASSAGE_SEARCH.md에 기록한다. 사용자는 검색·원문 읽기·복귀와 테스트 노트의
생성·수정·삭제에 따른 검색 갱신을 확인했다.

구현 과정에서 기존 owner lock과 호환되는 API shared read lock, 전체 조회의 5초 deadline,
Codex 개발·검증 원문 열람 허용을 반영했다. 앱 AI 정책과 reviewer 접근은 유지한다.
