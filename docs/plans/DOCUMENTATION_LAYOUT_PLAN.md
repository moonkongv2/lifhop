# 루트 Markdown 문서 배치 계획

작성일: 2026-10-21. 상태: **M1–M3 분류·이동 및 정적 검증 완료**.

[효율·정리 계획](EFFICIENCY_CLEANUP_PLAN.md)의 작업 A에 대한 후속 제안이다.
사용자의 분류 실행 요청에 따라 46개 문서를 이동하고 참조와 문서 지도를 갱신했다. 본문 통합·삭제는 수행하지 않았다.
A의 실제 브라우저 확인과 B–E 미착수 상태, S1 사용자 검증 대기는 그대로다.

## 1. 기준과 권장안

기준 HEAD는 `b80fa10428ad74d6bdbabaa3c896c66c72425cdb`, 브랜치는 main이다.
작업 A 이후 작업 트리의 루트 Markdown은 **52개**다. 미추적 S1/유지보수 문서도 포함했다.
기존 미커밋 변경은 보존한다. `.local/`·개인 자료는 열지 않았다.

**루트는 6개의 필수 진입 문서로 줄이고, 나머지 46개는 용도별로 배치한다.**
첫 이동에서는 basename을 유지한다. 폴더 이동과 파일명·heading·본문 재작성은 분리한다.
문서 제목에 PLAN이 있다는 이유만으로 진행 중 계획으로 분류하지 않는다.

```text
README.md / AGENTS.md / CURRENT.md / ROADMAP.md / DECISIONS.md / CODEX_REVIEW_LOOP.md
docs/
  README.md                 # 문서 지도: 현재 작업 → 사용법 → 설계 → 과거 증거
  guides/                   # 실행·사용·검증 가이드
  design/                   # 전략·계약·정책 설명
  plans/                    # 현재 작업 계획과 이 배치 계획
    reference/              # 구현 참고 계획; 남은 acceptance 여부를 별도 표시
  evaluation/
    phase32/                # 종료된 검색 실험
    phase33/                # 답변 평가·조건부 종료·미해결 이월 증거
  history/                  # 상태 snapshot·과거 테스트 출력
frontend/README.md           # 프런트 실행 안내는 소스 옆에 유지
```

AGENTS가 사전 독서로 지정한 README/ROADMAP/CURRENT/DECISIONS와 AGENTS 자체는 루트에
유지한다. CODEX_REVIEW_LOOP는 AGENTS의 고정 경로를 보존하기 위해 루트에 둔다.
이번 작업은 리뷰 루프가 아니므로 그 문서 내용을 읽거나 규칙을 적용하지 않았다.
DECISIONS의 ADR 분할은 별도 과제다. 파일 위치만 바꾸려고 필수 진입점을 늘리지 않는다.

## 2. 전체 파일 배치표

아래 표는 현재 52개 파일을 중복·누락 없이 분류한다. 실제 이동 시 basename은 그대로다.
`reference`는 참고 설계 분류이며 사용자 확인 완료·품질 통과를 뜻하지 않는다.

| 현재 루트 파일 | 목표 디렉터리 | 성격 |
| --- | --- | --- |
| `README.md` | `./` | 필수 진입점 유지 |
| `AGENTS.md` | `./` | 필수 진입점 유지 |
| `CURRENT.md` | `./` | 필수 진입점 유지 |
| `ROADMAP.md` | `./` | 필수 진입점 유지 |
| `DECISIONS.md` | `./` | 필수 진입점 유지 |
| `CODEX_REVIEW_LOOP.md` | `./` | 필수 진입점 유지 |
| `ACQUISITION.md` | `docs/guides/` | 사용·실행 가이드 |
| `CODEX_BACKFILL.md` | `docs/guides/` | 사용·실행 가이드 |
| `GITHUB_BACKFILL.md` | `docs/guides/` | 사용·실행 가이드 |
| `GITHUB_DISCUSSIONS.md` | `docs/guides/` | 사용·실행 가이드 |
| `HISTORY.md` | `docs/guides/` | 사용·실행 가이드 |
| `EVALUATION.md` | `docs/guides/` | 사용·실행 가이드 |
| `PASSAGE_SEARCH.md` | `docs/guides/` | 사용·실행 가이드 |
| `SEMANTIC_PRODUCT.md` | `docs/guides/` | 사용·실행 가이드 |
| `ANSWER_SLICE.md` | `docs/guides/` | 사용·실행 가이드 |
| `UNIFIED_ANSWER.md` | `docs/guides/` | 사용·실행 가이드 |
| `RETROSPECTIVES.md` | `docs/guides/` | 사용·실행 가이드 |
| `HISTORICAL_QUESTIONS.md` | `docs/guides/` | 사용·실행 가이드 |
| `PHASE41_COLLECTION.md` | `docs/guides/` | 사용·실행 가이드 |
| `CAPTURE.md` | `docs/design/` | 설계·정책·검토 |
| `AI_SOURCE_COVERAGE.md` | `docs/design/` | 설계·정책·검토 |
| `OUTPUT_CONTRACT_REVIEW.md` | `docs/design/` | 설계·정책·검토 |
| `PHASE41_COLLECTION_PLAN.md` | `docs/plans/` | 현재 진행 계획 |
| `EFFICIENCY_CLEANUP_PLAN.md` | `docs/plans/` | 현재 진행 계획 |
| `CODEX_BACKFILL_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `CODEX_SESSION_VIEW_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `CONVERSATIONAL_FOLLOWUP_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `GITHUB_BACKFILL_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `GITHUB_DISCUSSIONS_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `GITHUB_REPOSITORY_VIEW_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `SEARCH_UI_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `EVALUATION_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `PASSAGE_SEARCH_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `SEMANTIC_PRODUCT_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `EVIDENCE_SELECTION_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `ANSWER_RELIABILITY_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `ANSWER_EVIDENCE_CONTRACT_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `ANSWER_EVIDENCE_POLICY_PLAN.md` | `docs/plans/reference/` | 구현 참고 계획; 미완료 검증은 유지 |
| `SEMANTIC_SEARCH.md` | `docs/evaluation/phase32/` | 종료된 검색 실험·실패 증거 |
| `SEMANTIC_SEARCH_PLAN.md` | `docs/evaluation/phase32/` | 종료된 검색 실험·실패 증거 |
| `SEMANTIC_EXPERIMENT_PLAN.md` | `docs/evaluation/phase32/` | 종료된 검색 실험·실패 증거 |
| `SEMANTIC_FUSION_PLAN.md` | `docs/evaluation/phase32/` | 종료된 검색 실험·실패 증거 |
| `SEMANTIC_RERANK_PLAN.md` | `docs/evaluation/phase32/` | 종료된 검색 실험·실패 증거 |
| `FOLLOWUP_VALIDATION.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `FOLLOWUP_QUALITY_RECHECK.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `CONVERSATION_RECOVERY_EVALUATION.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `QUOTE_RECHECK.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `PHASE33_C3_SCOPE.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `PHASE33_COMPLETION_PLAN.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `PHASE33_CONDITIONAL_EXIT_PLAN.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `PHASE33_OPERATIONAL_EVIDENCE.md` | `docs/evaluation/phase33/` | 답변 평가·조건부 종료·이월 증거 |
| `CURRENT_HISTORY_20261021.md` | `docs/history/` | 보존 snapshot; 별도 이전 절차 적용 |

## 3. 분류에서 주의할 실제 사례

- `SEMANTIC_SEARCH.md`는 제품 Semantic 사용 설명이 아니라 종료된 B1 실험 기록이다.
  실제 운영 가이드는 `SEMANTIC_PRODUCT.md`이므로 서로 다른 폴더에 둔다.
- `PHASE33_CONDITIONAL_EXIT_PLAN.md`는 이름이 PLAN이어도 수용된 종료·D01–D09 이월
  기준이다. 평가 폴더로 옮겨도 CURRENT와 docs 지도에서 현재 유효한 이월 문서로 연결한다.
- `CONVERSATIONAL_FOLLOWUP_PLAN.md`, `SEMANTIC_PRODUCT_PLAN.md` 등은 구현 참고가
  필요하다. reference로 옮기면서 남은 사용자/실측 검증을 완료 처리하지 않는다.
- `ANSWER_SLICE.md`는 legacy selected-passage 안내와 실행 이력이 혼재한다.
  우선 guides에 두고 현재 일반 흐름은 UNIFIED_ANSWER라고 안내한다. 본문의
  “browser memory only”를 저장 대화 전체의 현재 동작으로 소개하지 않는다.
- `AI_SOURCE_COVERAGE.md`는 설계 경계와 평가 이력을 함께 담는다. 첫 이동에서는 유지하고
  현재 허용 범위와 과거 실측의 구분만 지도에 표시한다. 세부 분할은 후속 검토다.
- `CAPTURE.md`는 전략·연구 이력, `ACQUISITION.md`는 실행 가이드이므로 분리한다.
- `PHASE33_COMPLETION_PLAN.md`는 1,572줄로 체크리스트와 실행 이력이 섞여 있다.
  이동을 먼저 완료한 뒤 활성 이월 표와 역사 증거를 분리할지 검토한다.
  CURRENT처럼 무조건 요약하거나 실패·승인·비용 내용을 삭제하지 않는다.
- 파일별 참조 검색에서 0건인 일부 계획도 설계 근거로 남긴다. 참조 수는 삭제 기준이 아니다.

## 4. 참조 수정과 snapshot 보존

현재 추적 파일과 미추적 작업 파일에서 문서 이름 참조를 조사했다. Markdown 외 참조는
다음처럼 의미를 확인한 뒤 처리한다. 전체 문자열 치환은 금지한다.

| 실제 위치 | 참조 의미 | 이동 시 처리 |
| --- | --- | --- |
| `scripts/seed_history_demo.py` | HISTORY 안내 문서 참조 | 실제 문서 위치를 가리키는 안내만 갱신 |
| `alembic/versions/f48d3e25c064_passage_embeddings.py` | extension 부재 오류의 SEMANTIC_PRODUCT 안내 | migration SQL/revision은 그대로; 오류 안내의 문서 경로만 필요 시 수정 |
| `app/collectors/github.py`, `frontend/src/components/GitHubCollection.tsx` | README/ROADMAP/DECISIONS를 외부 저장소 수집 대상으로 선택 | 문서 이동과 무관하므로 수정하지 않음 |
| GitHub/acquisition fixtures·tests | 외부 repository의 README 파일 이름 | fixture 의미를 보존; 로컬 문서 경로로 바꾸지 않음 |
| README·CURRENT·frontend README·각 계획/가이드 | 상대 링크, backtick 경로, 실행 설명 | 이동 mapping에 따라 목적지 기준으로 재계산 |

이동한 문서 내 `app/...`, `scripts/...`, `.venv/...` 명령은 repository root에서 실행한다는
설명을 유지한다. 문서 디렉터리에 맞춰 shell 명령의 작업 경로를 임의 변경하지 않는다.
`.local/...` 경로는 개인 산출물 위치이며 문서 경로가 아니다. 열거나 옮기지 않는다.

**수집 범위 영향도 확인한다.** GitHub 수집기의 기본 allowlist에는 `docs/**/*.md`가 있다.
이 저장소를 수집 대상으로 사용한다면, 이전에 root에서 선택되지 않던 계획·평가 문서가
docs 이동 뒤 새 수집 후보가 될 수 있다. 이는 경로만 바꿔도 발생하는 제품 영향이다.
실제 수집은 실행하지 않고, 합성 경로 목록으로 이동 전후 pattern match 차이를 확인한다.
기존 승인 범위가 자동 확장됐다고 해석하지 않으며, 필요한 exclusion/문서 선택 조정은
별도 소스 설정 변경으로 검토한다. 저장된 subscription이나 AI 정책을 자동 수정하지 않는다.
이미 수집된 문서 경로가 바뀌면 다른 path의 snapshot으로 보일 수 있다는 제약도 인계한다.

### 변경 불가 snapshot의 이전

작업 A에서 `CURRENT_HISTORY_20261021.md`의 snapshot 본문은 원문 hash로 검증했다.
다른 46개 문서 이동 후에는 그 안의 루트 상대 링크도 깨질 수 있으므로 다음 절차를 쓴다.

1. 이동 직전 snapshot 파일 전체를 `docs/history/CURRENT_20261021.original.txt`로
   바이트 그대로 보존하고 SHA-256 및 원래 경로를 역사 안내에 기록한다.
2. 열람용 `docs/history/CURRENT_HISTORY_20261021.md`는 링크 경로만 새 배치에 맞춘다.
   날짜·판정·금액·승인 범위·문구는 변경하지 않는다. 원본 txt를 함께 연결한다.
3. 원본 hash 동일성과 열람본의 변경이 링크 경로에만 한정됨을 검사한다.
   이전의 “원문 동일” 주장은 원본 txt/snapshot 본문에만 적용함을 명시한다.
4. CURRENT와 기존 docs/history 안내를 새 열람본으로 연결한다. 같은 snapshot을 루트에도
   복제해 두지 않는다. 원본 txt의 옛 상대 경로는 당시 root 기준이라고 설명한다.

기존 `docs/history/legacy-test-result.txt`는 그대로 유지한다. 평가 결과·승인 기록도
내용을 바꾸지 않고 경로만 수정한다. root에 46개 redirect 문서를 남기는 방식은 사용하지 않는다.
외부 bookmark는 옛 commit의 Git 링크와 docs 지도의 이전명→새 위치 mapping으로 찾게 한다.
외부 소비자/CI가 root 경로에 의존한다면 실제 의존성부터 확인하고 해당 이동만 보류한다.

## 5. 실행 순서와 완료 기준

### M1. 기준 동결과 문서 지도

- [x] 실행 시점 파일 목록/상태/HEAD/hash와 링크·문자열 참조 목록을 다시 확보한다.
- [x] `docs/README.md`에 현재 작업, 가이드, 설계, reference 계획, 평가/이력의 지도를 만든다.
- [x] README는 필수 안내와 docs 지도 위주로 축약한다. CURRENT는 현재 계획과 D01–D09,
  S1 검증 안내 등 직접 필요한 링크를 유지한다.
- [x] root 6개 유지 및 52개 분류의 누락·중복·목적지 충돌이 없음을 검사한다.

### M2. 기능 묶음별 이동

- [x] 가이드·설계 → 현재/참고 계획 → 평가/이력 순으로 이동과 inbound/outbound 링크 수정을
  한 변경 단위 안에서 완료한다. 링크가 깨진 중간 상태를 커밋하지 않는다.
- [x] 기존 추적 파일은 Git rename으로 보이도록 변경을 작게 유지한다. 미추적 파일은
  실제 파일 이동 후 최종 경로로 추가한다. S1 코드·생성 schema는 이 이동에 포함하지 않는다.
- [x] heading과 basename은 유지한다. 링크 수정과 무관한 문체·상태 변경은 별도 diff로 분리한다.
- [x] snapshot은 위 보존 절차를 수행한다. root Markdown은 정확히 6개가 된다.

### M3. 검증과 인계

- [x] 전체 로컬 Markdown 링크·anchor·상대 이미지·reference-style 링크를 검사한다.
  기존 깨진 링크와 이번 신규 오류를 구분하며 신규 오류는 0건이어야 한다.
- [x] 코드·CI·스크립트·AGENTS와 문서의 backtick 경로까지 옛 root 경로를 재검색한다.
  실제 외부 저장소 파일명, 역사적 경로, 이전명 mapping은 허용 목록으로 설명한다.
- [x] 보존 원본 hash·내용 diff·Git status로 소실·중복·기존 사용자 변경 덮어쓰기가 없음을 확인한다.
- [x] README → docs 지도 → S1 사용 가이드, CURRENT → 현재 계획,
  CURRENT → D01–D09 → 실측 증거, 가이드 → root 실행 명령을 수동으로 따라가 본다.
- [x] 문서 경로만 변경하면 앱 테스트/DB/유료 실행 없이 링크·diff 검사로 검증한다.
  스크립트의 사용자 안내 문자열을 바꾸면 해당 구문/출력만 좁게 확인한다.
  문서 수정 확인을 위해 실제 seed·migration·collection 명령을 실행하지 않는다.

각 묶음은 검증 후 독립 커밋을 권장한다. 예:
`docs: organize guides and design references`,
`docs: organize plans and evaluation evidence`.
실제 이동 전 기존 S1와 공유하는 문서 변경을 검토하여 사용자 작업과 섞이지 않게 한다.
분류 변경은 아직 커밋하지 않았다. 기존 S1 변경과 분리하여 검토 후 커밋한다.

## 6. 이후 유지 규칙

- 새 문서는 기본적으로 docs의 해당 용도 폴더에 만든다. root 파일은 늘리지 않는다.
- 진행 계획은 docs/plans, 구현 참고로 전환한 계획은 docs/plans/reference에 두되
  상태·확인 대기·현재 가이드 링크를 명시한다. 완료 여부는 폴더명이 아닌 내용으로 판단한다.
- 가이드에는 실행 방법·현재 제약을, 평가에는 조건·결과·실패·승인 종료를 둔다.
  새 결과를 CURRENT에 장문 누적하지 않고 최신 요약과 증거 링크만 반영한다.
- DECISIONS는 지속 결정만 추가하고 실험 raw/history를 복제하지 않는다.
- 문서 이동은 내용 통합/삭제와 분리한다. 이번 계획은 문서 삭제를 제안하지 않는다.
- 이 문서도 이미 docs/plans에 작성한다. 기존 효율 계획의 B–E와 S1 acceptance를
  대신하지 않으며, 문서 이동을 성능 개선 완료로 표시하지 않는다.

## 계획 작성 검증

52개 원본 이름과 표의 이름을 집합 비교하여 누락·중복이 없음을 확인했다.
파일 내용은 제목·상태·관련 범위 위주로 분류했으며 모든 과거 실행 결과를 재검증한 것은 아니다.
개인 자료·유료 결과·CODEX_REVIEW_LOOP 본문은 열지 않았다.
M1–M3 수행 결과는 아래에 기록한다.

## 분류 실행 검증 (2026-10-21)

- 52개 목적지의 존재·유일성, 46개 이전 루트 경로의 부재, 루트 Markdown 6개를 확인했다.
- 로컬 Markdown 경로·anchor·이미지·reference-style 링크 정적 검사: 이전 0건, 이후 0건 오류.
  README → 문서 지도 → S1, CURRENT → 수집 계획 및 D01–D09 → 운영 증거 경로도 확인했다.
  외부 URL의 접근 가능성과 실제 브라우저 렌더링은 확인하지 않았다.
- snapshot 원본 SHA-256 일치. 열람본 본문은 링크 변환 결과와 일치하며 모든 이동 문서의
  fenced 명령 원문은 보존했다. 별도 상태를 갱신한 효율 계획과 snapshot 안내 외 44개
  이동 문서는 사전 계산한 링크 변환 결과와 정확히 일치한다.
- 작업 시작 시점 파일 해시와 비교해 기존 비문서 변경을 보존했다. 예외는 seed와 기존
  migration의 안내 경로 문자열 2개뿐이며, 역치환 해시 동일성과 Python AST 구문 검사를 통과했다.
  AGENTS와 CODEX_REVIEW_LOOP도 시작 시점과 동일하다.
- 코드·스크립트의 이동 대상 문서명 참조는 위 2개 안내 경로만 남으며 새 경로로 수정했다.
  외부 저장소의 README 이름, 배치표의 이전명, 보존 원본의 옛 경로는 유지한다.
- 수집기의 `matches` 함수만 AST로 추출해 표준 라이브러리로 합성 경로를 비교했다.
  기존 52개 문서 기준 기본 선택 후보는 3개 → 49개(+46개)다. 실제 수집·구독 변경은 하지 않았다.
- `git diff --check` 통과. 앱 테스트·DB·migration 실행·AI 호출은 이번 문서 분류 검증에 포함하지 않았다.
- 파일은 작업 트리에 이동했고 staging/commit은 하지 않았다. 미추적 문서와 기존 S1 변경을
  함께 검토하되 커밋 단위는 분리한다. 사용자 확인: 루트 README의 문서 지도를 열어 S1 안내와
  D01–D09 이월 문서를 확인한다.
