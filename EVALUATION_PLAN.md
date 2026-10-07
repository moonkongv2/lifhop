# Phase 3.1 — 비공개 평가 질문과 키워드 검색 기준선

작성: 2026-10-06. 검토: 2026-10-07.
상태: 평가 도구 구현·합성 검증 완료. 실제 세트 revision 2에 로컬 규칙 후보
20개 작성(근거 후보 13개·연결 실패 7개); 모두 draft이며 의미 검토·승인 대기.
실행 가이드: `EVALUATION.md`. 실제 평가 계정: `b@test.com`.
Antigravity 계획 검토 1회 완료 및 지적 3건 보완 반영.
첫 실행은 10분 제한으로 의견 없이 종료되어, 본문을 직접 전달한 재시도로 검토했다.

## 1. 목표와 사용자가 확인할 결과

실제 질문 약 20개와 검증한 근거 위치를 비공개 파일로 관리하고, 현재 검색이
그 근거를 얼마나 찾는지 반복 측정한다. 검색이 실패한 이유를 구분해 Phase 3.2의
색인 개선과 Phase 3.3의 출처 인용 답변에 사용할 기준을 만든다.

사용자 흐름:

1. 로컬 계정으로 평가 파일을 초기화한다.
2. 실제 질문을 다듬고, 기존 Search/기록 화면에서 근거를 직접 확인한다.
3. 해당 Entry 버전의 문장 위치를 연결하고 질문을 승인한다.
4. CLI로 기준선을 실행하고, 비공개 HTML 보고서에서 질문별 성공·실패를 확인한다.
5. 부족한 수집과 검색 실패를 구분하고 다음 검색 개선 대상으로 삼는다.

완료 기준은 도구가 동작하는 것과 실제 평가 세트가 준비되는 것을 구분한다.
합성 20문항이나 미승인 질문만으로 실제 평가 완료라고 표시하지 않는다.

## 2. 현재 구현과 경계

- `app/services/entry_search.py`: 제목/본문의 대소문자 무시 부분 문자열 검색.
  질문 전체를 하나의 문자열로 찾으며 단어 분리·의미 검색은 없다.
  정확한 제목, 제목 부분 일치, 나머지 순으로 정렬하고 등록일/ID로 동률을 해소한다.
- `GET /entries/search`: owner, source/type/source_state, 등록일·원본 날짜 범위,
  페이지, Codex commentary 포함 여부를 지원한다. 날짜 기준은 Asia/Seoul이다.
- 기본 Codex 검색은 `primary_content`를 사용한다. 작업 commentary는 선택적이다.
- `Entry.current_version_id`, `EntryVersion.content_hash/content/payload`로 현재·과거
  관측 버전을 연결할 수 있다. 일반 검색은 현재 Entry를 반환한다.
- `SourcePolicy`와 Entry의 external-AI 허용이 모두 참이어야 외부 AI에 사용할 수 있다.
  로컬 검색에는 AI 제외 기록도 나타난다. 정책 누락은 AI 불허로 취급한다.
- 실제 GitHub 415개 자료의 격리 검증은 완료됐지만 개인 계정 적용은 미확인이다.
  토론은 실제 선택 저장소에 0개이며 합성 화면은 사용자가 확인했다.

이번 범위: 로컬 평가 CLI, 엄격한 파일 계약, 근거 고정, 동일 검색 기준선,
보고서, 합성 회귀 테스트, 실제 질문 작성 가이드.

새 AI 호출, 임베딩, pgvector, passage 색인 테이블, 큐/worker, 스케줄,
웹 평가 편집 화면, 새 의존성·마이그레이션은 도입하지 않는다.
검색 랭킹 개선은 기준선 기록 이후 별도 범위로 판단한다.

## 3. 평가 세트 작성

### 질문 구성

목표 20개, 하나의 질문에 여러 태그를 붙일 수 있다.

| 주된 유형 | 목표 수 | 확인할 내용 |
| --- | ---: | --- |
| 과거 해결책·결정 이유 | 6 | 채택한 근거와 단순 제안을 구분 |
| 여행 등 일상 기록 | 4 | 프로젝트 소속 없이 검색 |
| 여러 출처의 연결 | 3 | ChatGPT/Codex/GitHub 중 실제 보유 근거 조합 |
| 기간별 변화·회고 | 3 | 원본 날짜, 변경된 결정, 과거 버전 |
| 근거 부족·정책·수집 누락 | 4 | 충분한 답변을 만들 수 없는 이유 |

필수 seed 질문:

- 우리가 이전에 진행했던 모터 RPM 제어 최적화 문제에서 제어 주기 설정을 어떤 기준으로 했었지?
- 2026년 4월 오키나와 여행 시 이용했던 렌터카 업체와 선정 이유?

두 질문은 정답이 있다는 가정이 아니다. 자료가 없으면 `coverage_gap` 또는
검토 범위 내 `insufficient_evidence`로 표시한다. 업체·수치·결정 이유를 지어내지 않는다.
한국어와 영어 각각 최소 3개, 일상 질문 최소 4개, 여러 출처 최소 3개,
변경된 결정/과거 버전 최소 2개, AI 제외 기록과 알려진 수집 누락 각각 최소 2개를
태그로 점검한다. 부족하면 실제 세트 완성 조건의 미충족으로 보고한다.

### 작성 책임

- 초기화는 두 seed와 나머지 작성용 빈 항목을 만든다. 빈 항목은 `draft`다.
- agent는 구현 승인 후 선택 계정의 자료를 읽어 질문·근거 후보를 제안할 수 있다.
  후보는 `draft`이고, 개인 자료를 원격 검토 도구에 제공하지 않는다.
- 사용자와 함께 실제 질문/근거를 확인하여 `reviewed`로 전환한다.
- 예상 답은 각 주장별 짧은 설명과 근거 묶음으로 작성한다. 채택/제안/거절,
  검토/실제 사용을 원문에서 확인한다. 자동 의미 검증을 주장하지 않는다.
- 예상 답변 문구를 실제 답변 시스템의 출력으로 취급하지 않는다.

## 4. 파일 계약과 버전 고정

`app/evaluation/`에 Pydantic 모델과 실행 로직을 둔다. 실제 파일은
`.local/evaluation/<set-id>/`에만 저장한다. Git에는 합성 fixture와 가이드만 넣는다.

### Dataset

- `schema_version`, `set_id`, `revision`, 생성/검토 시각, 인증한 `owner_id`.
- 대상 DB/스키마의 비밀 없는 식별 정보와 계정 연결 정보. DB URL·비밀번호는 저장하지 않는다.
- `cases`: 고유 case ID, question, language, tags, status(draft/reviewed),
  expected_outcome(supported/insufficient_evidence/coverage_gap/policy_excluded).
- 실제 사용자 질문은 최대 256자. 기본 검색 쿼리는 question 그 자체로 고정한다.
- 보조 `keyword_queries`: 사용자가 사전에 고른 문자열 최대 3개, 각 256자.
  실행 결과를 본 뒤 바꾸면 새 revision으로 기록한다.
- source/type/source_state/date_field/date_from/date_to/include_work_commentary는
  현재 검색 API와 같은 의미와 제한을 따른다. 범위 밖 날짜·역전 범위를 거절한다.
- `claims`: 주장 ID, 검토한 예상 사실/해석, 필수 evidence group ID 목록.
- `evidence_groups`: 하나의 근거 요구에 대한 대체 가능한 근거(anchor) 목록.
  cross-source 주장은 각 출처를 별도 필수 group으로 둔다.
- 근거 부족/누락 사례는 검토한 출처·기간·수집 gap/검토 메모를 남긴다.
  검색 결과 0개만으로 기록 전체에 정답이 없다고 확정하지 않는다.

### Anchor

`entry_id`, `version_id`, `content_hash`, provider/scope/external_id,
field(title/content), start/end, `passage_sha256`, selection(current/historical).

start/end는 고정된 EntryVersion 필드의 Python Unicode 문자 인덱스, end 제외이다.
정규화·줄바꿈 변경 전 문자열에 적용한다. 해당 문자열의 UTF-8 SHA-256을 보관한다.
원문 문장 자체는 dataset/보고서에 복사하지 않고 실행 중에만 해석한다.
locator, parser_version, completeness, event/source/observed 시각도 출처 확인에 사용한다.
긴 전체 기록이나 payload를 근거 하나로 지정하지 않고 한 문장/문단을 선택한다.

검증은 owner → Entry 소속 → version 소속 → 고정 hash → 범위 → passage hash 순이다.
다른 owner의 ID는 본문 없이 거절한다. 존재하지 않는/삭제된 기록은 `unavailable`,
current가 달라진 것은 `stale_current`, hash/범위 불일치는 `invalid_anchor`로 표시한다.
조용히 최신 버전으로 바꾸거나 해당 문항을 성공으로 처리하지 않는다.
`historical`의 고정 버전은 유지하지만 현재 검색으로 그 버전까지 찾았다고 주장하지 않는다.

초기화는 `revision-000001.json`을 생성한다. `edit`, `anchor`, `review`는 schema/owner를
검증하고 직전 revision의 digest를 연결한 다음 번호의 파일을 원자적으로 생성한다.
편집한 case는 다시 draft가 되며 이전 승인 상태를 그대로 물려받지 않는다.
revision 파일은 draft도 덮어쓰지 않는다. set 디렉터리는 검증된 가장 최신 revision을
선택하고, `--revision N`으로 특정 버전을 명시할 수 있다. digest는 자기 digest 필드를
제외한 canonical JSON에 대해 계산하며 생성 충돌은 재선택 없이 실패한다.
보고서는 dataset digest와 revision을 고정하고, 실행마다 새 디렉터리를 만든다.

## 5. 실행 경로와 일관성

### 로컬 DB를 읽는 CLI

`scripts/evaluate_retrieval.py`는 로컬 운영 도구다. 기존 settings의 PostgreSQL
연결을 사용하고, `--email`과 getpass 비밀번호를 기존 `app.security.verify_password`로
검증한다. 다른 owner를 지정하는 옵션은 제공하지 않는다. 개인 평가에 테스트 DB를
몰래 대체하지 않는다. 테스트는 기존 `lifhop_test`의 격리 스키마를 사용한다.

평가 실행은 PostgreSQL `REPEATABLE READ READ ONLY` transaction에서 인증·정책·
검색·근거 검증을 수행한다. SQLAlchemy autoflush를 끄고 DB 쓰기를 하지 않는다.
정책을 생성하는 `source_policy()`나 AI egress 함수를 부르지 않는다.
끝나면 rollback/close하고, 원본 DB·current 선택·주석·정책·수집 결과를 수정하지 않는다.
이 CLI는 배포용 원격 평가 API가 아니며 향후 호스팅 구조 변경 시 별도 판단한다.

### 실제 검색과 동일한 순위

현재 `search_entries()`의 조건/정렬을 작은 공통 query helper로 추출한다.
API와 평가가 같은 SQL 조건·정렬·Codex primary/commentary 표현식을 사용한다.
평가는 ID/current_version_id와 검증 메타데이터만 projection하여 전체 본문을
검색 결과마다 읽거나 직렬화하지 않는다. 별도의 검색 알고리즘을 작성하지 않는다.
API 동작·응답 구조·순위는 유지하고 동등성 테스트로 확인한다.

각 query는 offset 0, limit 20으로 실행하고 k=5/10/20을 함께 계산한다.
자연어 primary 결과와 keyword 보조 결과는 분리한다. 보조 결과를 union하여
primary 성적으로 기록하지 않는다. commentary=true 실험도 별도 실행으로 둔다.
keyword 모드에서는 사전에 고정한 각 keyword query를 독립적으로 실행하고
각각의 top-20/지표를 보존한다. 결과를 합치거나 가장 좋은 query만 고르지 않는다.
case 점수는 그 case의 keyword query 점수들의 산술평균, run 점수는 동일한 평가
대상 case 점수들의 산술평균이다. query 수가 많은 case에 더 큰 가중치를 주지 않는다.
keyword가 없는 case는 `no_keyword_query`로 표시하고, keyword 모드의 평가 대상 수와
미설정 수를 따로 보고한다. primary와 비교할 때 공통 case 집합의 점수도 함께 제공한다.

런 manifest에는 Git commit, dataset digest, query 설정, 검색 구현 버전,
transaction 관측 시각, owner policy_revision, corpus 식별 fingerprint,
기록/버전 수, 출처별 수집 coverage 상태와 처리 시간을 기록한다.
fingerprint는 owner의 Entry identity/current version/hash/source 상태·정책을
정렬해 streaming digest로 계산한다. 비밀·원문은 넣지 않는다.
데이터·정책·필터가 다른 런은 다른 corpus로 표시하여 순수 검색 개선 비교와 구분한다.

## 6. 지표와 합격 기준

### 자동 계산

- `EvidenceGroupRecall@5/10/20`: 필수 근거 group 중 결과 Entry로 찾은 비율.
  대체 anchor 중 하나가 있으면 group 하나를 찾은 것으로 계산한다.
- `AllGroupsHit@20`: 모든 필수 group을 찾은 supported 문항 비율.
- `MRR@20`: 첫 유효 근거 Entry의 reciprocal rank, 없으면 0.
- `CurrentVersionHit`: 고정 current anchor 버전이 현재 검색 결과와 일치하는지.
- `HistoricalEntryHit`: 과거 버전이 있는 Entry를 찾았는지. 별도 지표이며
  과거 문장 자체의 검색 성공이나 역사 질문의 답변 가능성을 뜻하지 않는다.
- case별 rank/entry/version ID, outcome, validation 상태, query 시간.
- 문항 상태별 분모와 태그/언어별 결과. draft와 근거 없는 negative 문항에는 recall을
  만들지 않는다. stale/invalid/unavailable은 따로 집계하고 clean 점수와 함께 보여
  분모에서 조용히 빠져 성공률이 올라가는 것을 막는다.

각 query의 GroupRecall@k는 찾은 필수 group 수 / 전체 필수 group 수이며,
AllGroupsHit@20은 모든 group을 찾았으면 1, 아니면 0이다. MRR은 첫 유효 근거의
1/rank이다. primary의 run 점수도 case별 점수의 산술평균으로 계산한다.
기본 recall은 현재 anchor를 가진 검토된 supported 사례를 기준으로 한다.
historical-only 문항은 별도 집계한다. cross-source는 필수 group을 모두 요구한다.
제목만 맞는 기록은 근거 hash/version 검증을 통과한 anchor일 때만 성공이다.

### 사람이 확인하는 항목

각 예상 주장의 근거 타당성, 제안과 채택의 구분, 근거 부족 판단과 알려진 coverage gap.
Phase 3.1에는 답변 생성이 없으므로 자동 claim grounding/abstention 점수를 만들지 않는다.
검토 결과는 `confirmed`/`needs_review`로 보존하고 Phase 3.3 답변 평가에 재사용한다.

### 비교 전 고정할 목표

- 실제 검토된 질문 약 20개와 필수 유형 충족. draft를 채워 넣어 완료하지 않는다.
- 유효 anchor 검증 100%, 소유권 누출·외부 AI 송신·삭제 기록 검색 결과 노출 0건.
- 제품 목표: current 근거 GroupRecall@20 ≥ 0.80, AllGroupsHit@20 ≥ 0.70.
  primary/keyword는 각각 보고한다. 이는 개선 목표이며 낮은 초기 기준선을 숨기거나
  Phase 3.1 도구 실패로 취급하지 않는다.
- historical/negative/policy-excluded 사례의 미지원·검토 필요 상태가 명시될 것.
- 검색 실패를 판별하고 보고서를 반복 생성할 수 있으면 도구 구현 완료다.
  실제 세트 승인은 별도 완료 조건이며 두 상태를 CURRENT.md에 구분한다.

## 7. AI 정책·누락·삭제의 평가 의미

- 로컬 키워드 검색은 AI 제외 기록도 찾는다. 이 결과는 정책 위반이 아니다.
- 유효 source policy와 Entry 허용, source-deleted 명시 포함 조건을 읽어
  `external_ai_eligible`을 별도로 표시한다. 허용 여부를 변경하지 않는다.
- AI 허용 근거만으로 모든 필수 group을 채우는지 계산하여 `policy_blocked`를 표시한다.
  Phase 3.3이 실제로 답변을 거절했다는 점수로 취급하지 않는다.
- 수집 중지와 AI 불허는 다른 상태다. 수집 중지도 이미 보유한 로컬 기록을 숨기지 않는다.
- source-deleted는 lifhop 삭제와 다르다. 현재 검색 설정대로 로컬 검색되며 명시 표시한다.
- lifhop에서 삭제된 Entry는 검색/근거에서 사용할 수 없다. 보고서에 원문·제목·
  예상 답·주석을 넣지 않고 case ID, 집계, 소유자 검증이 있는 기록 링크만 둔다.
  과거 보고서는 당시 측정치이고 현재 가용성을 보장하지 않는다. 삭제된 링크는 기존
  API에서 404로 끝나며 복사된 source body가 보고서에 남지 않는다.
- 실제 평가 파일에는 개인 질문/사람이 쓴 검토 메모가 있으므로 계속 비공개다.
  자동 원문 사본을 만들지 않으며 파일/백업 폐기는 가이드에 설명한다.

## 8. CLI와 확인 절차

계획한 명령(세부 옵션은 구현 가이드/--help와 함께 고정):

```sh
# 기본 DB를 읽기 전용으로 인증하고 비공개 초안 생성
.venv/bin/python scripts/evaluate_retrieval.py init --email YOUR_EMAIL

# question/tags/outcome/필터/keyword/claims/근거 group을 대화형 편집해 새 draft revision 생성
.venv/bin/python scripts/evaluate_retrieval.py edit --set .local/evaluation/SET_ID

# 선택 계정의 후보 검색: 쿼리는 대화형 입력, shell history에 개인 질문을 남기지 않음
.venv/bin/python scripts/evaluate_retrieval.py inspect --set .local/evaluation/SET_ID

# case/entry/version/필드/문장 범위를 대화형 선택하고 anchor를 검증해 새 revision 저장
.venv/bin/python scripts/evaluate_retrieval.py anchor --set .local/evaluation/SET_ID

# 문항 상태·필수 유형·근거 무결성 점검
.venv/bin/python scripts/evaluate_retrieval.py validate --set .local/evaluation/SET_ID

# case를 선택해 실제 근거의 의미와 예상 주장을 확인한 뒤 reviewed로 승인
.venv/bin/python scripts/evaluate_retrieval.py review --set .local/evaluation/SET_ID

# 자연어 질문의 기본 기준선. keyword 모드는 명시적 별도 실행
.venv/bin/python scripts/evaluate_retrieval.py run --set .local/evaluation/SET_ID
.venv/bin/python scripts/evaluate_retrieval.py run --set .local/evaluation/SET_ID --mode keywords
```

`edit`는 case ID를 선택하고 질문·태그·예상 결과·필터·보조 키워드·주장과 필수 group을
작성한다. 초안에는 미완성 항목을 허용하지만 run의 scored 대상이 될 수 없다.
`review`는 anchor 무결성, supported의 필수 claim/group, negative의 검토 범위/메모를
검증하고 사용자에게 의미 검토를 명시적으로 확인받는다. 새 revision에 reviewer owner ID와
승인 시각을 남긴다. 자동으로 reviewed를 부여하지 않는다. `validate`는 파일을 수정하지
않고 개별 case 유효성과 세트 구성의 충족/미충족을 보고한다.

각 DB 사용 명령은 로컬 비밀번호로 owner를 확인한다. 계정/대상 DB가 달라지면
기존 평가 파일 재사용을 거절하고 새 세트를 만들거나 명시적 근거 재검토를 요구한다.
암호/토큰을 옵션·파일·로그에 기록하지 않는다.

출력: 새 run의 `manifest.json`, `results.json`, `report.html`.
HTML은 외부 스크립트/폰트/분석 요청 없이 escape한 case ID와 점수·상태를 보여준다.
보고서 본문은 영어 UI, 계획/설명은 한국어. 평가 파일의 question은 입력 언어 그대로다.
질문/원문 확인은 private dataset과 기존 기록 화면에서 한다.

private 경로는 symlink·기존 파일 덮어쓰기를 거절하고 directory 0700/file 0600으로 저장한다.
dataset ≤ 2 MiB/100 cases, 보조 keyword queries ≤ 3개/case
(기본 질문을 포함해 두 모드 합계 ≤ 4개/case), 근거 ≤ 20개/case,
passage ≤ 8,000문자, 읽을 version 필드 ≤ 8 MiB, run ≤ 5분을 초기 한도로 둔다.
선택한 근거 필드가 한도를 넘으면 무음 절단하지 않고 budget 상태를 보고한다.
DB statement timeout과 예외를 body-free 코드로 기록하고 일부 실패 런은 Partial이다.

Backend 실행은 CLI에 필요하지 않다. HTML의 기존 Entry 링크를 확인하려면
backend/frontend를 실행하고 브라우저에서 해당 계정으로 로그인한다.
S3/worker/외부 AI/GitHub 호출은 필요 없다.

## 9. 구현 순서와 파일 범위

1. **계약/근거:** `app/evaluation/schemas.py`, `evidence.py`, 합성 계약 fixture.
   버전/owner/범위 검증, draft/검토 상태, revision/digest, 안전한 로컬 파일 처리.
2. **검색 기준선:** `app/services/entry_search.py` 최소 query 추출,
   `app/evaluation/retrieval.py`, `metrics.py`. 기존 API와 동일 조건·순위 검증.
3. **CLI/보고서:** `scripts/evaluate_retrieval.py`, `app/evaluation/report.py`.
   read-only 인증/snapshot, 초기화·edit·inspect·anchor·validate·review·run, private 보고서.
4. **실제 세트:** 계정 corpus/coverage를 확인하고 질문·근거 후보 작성,
   owner 검토 후 약 20개 고정, primary/keyword 두 기준선 실행.
5. **가이드/상태:** `EVALUATION.md`, README/CURRENT.
   구현 완료·실제 세트 승인·실패 지표·다음 개선을 구분한다.

문서·테스트를 포함해 계약/기준선/CLI·가이드 단위 커밋을 권장한다.
첫 실제 세트 검토 전에 구현 완료 데모를 보여주고 피드백을 반영한다.
개인 평가 파일이나 실제 결과를 커밋하지 않는다.

## 10. 검증

- 현재 검색 API와 공통 query의 IDs/순위/total 동등성: 한영, 숫자·단위·코드,
  `%`/`_`/역슬래시, 제목 일치, source/type/date, 날짜 경계, commentary 옵션.
- 근거: 다른 owner/Entry의 version, 오래된 current, historical, 수정 hash,
  Unicode/emoji/줄바꿈 offset, 없는 기록·삭제, 큰 필드/잘못된 날짜.
- 지표: 대체 근거, 다중 필수 group, cross-source, 중복 hit, 0 hit,
  rank 5/10/20 경계, MRR, draft/negative 분모, invalid/stale 상태.
  keyword 0/1/3개, query별 점수와 case/run 산술평균, 공통 case 비교,
  primary와 keyword 결과 분리, 기본 질문+보조 3개의 예산 경계를 검증한다.
- 작성/승인: 빈 draft 작성→anchor→review→run의 전 과정, 편집 시 draft 복귀,
  revision/digest 연결, 이전 승인 파일 불변, 미검토 case의 점수 제외를 확인한다.
- 정책: source/record 각각 deny, 정책 누락, source-deleted와 lifhop 삭제,
  로컬 검색 성공과 AI eligibility 차이. 네트워크 차단으로 AI/GitHub/AWS 호출 없음 확인.
- DB: 실제 PostgreSQL read-only snapshot, concurrent 수정과 일관성,
  정책 조회가 row를 생성하지 않음, DB 데이터·버전·정책·주석 불변.
- 출력: HTML injection, symlink/덮어쓰기/경로 escape, permissions,
  본문·제목·annotation·password/DB URL 미포함, timeout/Partial 재실행.
- 기존 backend 전체 테스트. 프런트엔드는 변경하지 않으며 링크만 기존 경로로 확인한다.
- 실제 약 20문항 결과를 개인 경로에서 검토하고, 낮은 점수/미수집/미지원 사례를
  그대로 기록한다. 합성 테스트 성공으로 실제 질문의 정답 품질을 대체하지 않는다.

## 11. 남는 한계와 후속 판단

현재 검색은 질문 전체 substring 방식이라 자연어 질문의 낮은 recall이 예상된다.
보조 키워드가 잘 찾더라도 자연어 질문이 잘 검색된다고 결론내리지 않는다.
과거 버전 passage의 직접 검색은 Phase 3.2에서 검토한다.
답변의 주장별 인용 정확도/불확실성/지연/AI 비용은 Phase 3.3에서 측정한다.
반복 수집과 AWS 배포는 Phase 4/5의 범위로 유지한다.

개인 GitHub 자료 미적용 등 corpus가 부족하면 평가를 `coverage_gap`으로 남긴다.
평가 때문에 기록을 자동 적용하거나 원본 서비스에 테스트 기록을 생성하지 않는다.
실제 질문 선택과 예상 근거의 의미 검토는 사용자 확인이 필요하다.

## 계획 검토 반영

Antigravity 1회 완료. 지적 3건 모두 수용했다.

1. High: 보조 키워드 여러 개의 집계가 미정 → 독립 실행, query별 지표,
   case/run 산술평균과 공통 case 비교를 고정했다.
2. High: draft 작성·승인 명령이 없음 → edit/review와 immutable revision 절차,
   수정 시 재검토 및 의미 검토 확인을 추가했다.
3. Medium: primary+보조 3개와 query 예산 3개의 충돌 → 보조 최대 3개,
   두 모드 합계 최대 4개로 정합성을 맞추고 경계 테스트를 추가했다.

검증: 기존 검색/정책/버전/인증 코드와 계획의 정합성 확인, 문서 whitespace와
Markdown code fence 검사. 구현 전이므로 애플리케이션 테스트는 실행하지 않았다.
