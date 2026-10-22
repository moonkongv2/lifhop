# 문서 지도

현재 상태는 [CURRENT](../CURRENT.md), 제품 완료 기준은 [ROADMAP](../ROADMAP.md),
지속 결정은 [DECISIONS](../DECISIONS.md), 작업 규칙은 [AGENTS](../AGENTS.md)를 따른다.
프로젝트 소개는 [README](../README.md)에 있다. 리뷰 루프를 요청했을 때만
[CODEX_REVIEW_LOOP](../CODEX_REVIEW_LOOP.md)를 적용한다.

## 현재 작업과 읽는 순서

1. [GitHub S1–S3 가이드](guides/PHASE41_COLLECTION.md), [Codex S4 가이드](guides/CODEX_AGENT.md), [S5 통합 검증](guides/PHASE41_ACCEPTANCE.md)과 [수집 계획](plans/PHASE41_COLLECTION_PLAN.md): 통합 합성 검증 후 직접 확인·실제 소스/A7 수용 보류.
2. [효율·정리 계획](plans/EFFICIENCY_CLEANUP_PLAN.md): A 정리 진행 기록과 아직 시작하지 않은 B–E.
3. [D01–D09 이월 기준](evaluation/phase33/PHASE33_CONDITIONAL_EXIT_PLAN.md)과 [운영 증거](evaluation/phase33/PHASE33_OPERATIONAL_EVIDENCE.md): 조건부 종료 후에도 남은 과제.
4. [문서 배치 계획과 이전명 표](plans/DOCUMENTATION_LAYOUT_PLAN.md): 루트 52개 중 6개 유지, 46개 이동.

명시적인 `cd`가 없으면 문서의 실행 명령은 저장소 루트 기준이다.
`.local/`은 개인 자료·평가 산출물 위치이며 이 지도에 자료 내용을 복제하지 않는다.
폴더 분류는 사용자 검증 완료나 과거 유료 실행 승인 갱신을 의미하지 않는다.
GitHub 기본 문서 패턴으로 이 저장소를 수집하면 이동한 46개가 추가 후보가 된다.
실제 수집이나 구독·AI 권한 변경은 수행하지 않았다. 필요하면 소스 선택 범위를 별도로 검토한다.

## 사용·실행 가이드

일반 답변 흐름은 UNIFIED_ANSWER를 먼저 읽는다. ANSWER_SLICE는 이전 selected-passage 흐름도 포함한다.

- [ACQUISITION.md](guides/ACQUISITION.md)
- [CODEX_BACKFILL.md](guides/CODEX_BACKFILL.md)
- [CODEX_AGENT.md](guides/CODEX_AGENT.md)
- [GITHUB_BACKFILL.md](guides/GITHUB_BACKFILL.md)
- [GITHUB_DISCUSSIONS.md](guides/GITHUB_DISCUSSIONS.md)
- [HISTORY.md](guides/HISTORY.md)
- [EVALUATION.md](guides/EVALUATION.md)
- [PASSAGE_SEARCH.md](guides/PASSAGE_SEARCH.md)
- [SEMANTIC_PRODUCT.md](guides/SEMANTIC_PRODUCT.md)
- [ANSWER_SLICE.md](guides/ANSWER_SLICE.md)
- [UNIFIED_ANSWER.md](guides/UNIFIED_ANSWER.md)
- [RETROSPECTIVES.md](guides/RETROSPECTIVES.md)
- [HISTORICAL_QUESTIONS.md](guides/HISTORICAL_QUESTIONS.md)
- [PHASE41_COLLECTION.md](guides/PHASE41_COLLECTION.md)
- [PHASE41_ACCEPTANCE.md](guides/PHASE41_ACCEPTANCE.md)

## 설계·정책

AI_SOURCE_COVERAGE에는 현재 설계 경계와 과거 평가 이력이 함께 있다.

- [CAPTURE.md](design/CAPTURE.md)
- [AI_SOURCE_COVERAGE.md](design/AI_SOURCE_COVERAGE.md)
- [OUTPUT_CONTRACT_REVIEW.md](design/OUTPUT_CONTRACT_REVIEW.md)

## 진행 계획

- [PHASE41_COLLECTION_PLAN.md](plans/PHASE41_COLLECTION_PLAN.md)
- [EFFICIENCY_CLEANUP_PLAN.md](plans/EFFICIENCY_CLEANUP_PLAN.md)

## 구현 참고 계획

참고 분류에도 미완료 acceptance가 남아 있으므로 각 문서의 제한과 검증 대기를 유지한다.

- [CODEX_BACKFILL_PLAN.md](plans/reference/CODEX_BACKFILL_PLAN.md)
- [CODEX_SESSION_VIEW_PLAN.md](plans/reference/CODEX_SESSION_VIEW_PLAN.md)
- [CONVERSATIONAL_FOLLOWUP_PLAN.md](plans/reference/CONVERSATIONAL_FOLLOWUP_PLAN.md)
- [GITHUB_BACKFILL_PLAN.md](plans/reference/GITHUB_BACKFILL_PLAN.md)
- [GITHUB_DISCUSSIONS_PLAN.md](plans/reference/GITHUB_DISCUSSIONS_PLAN.md)
- [GITHUB_REPOSITORY_VIEW_PLAN.md](plans/reference/GITHUB_REPOSITORY_VIEW_PLAN.md)
- [SEARCH_UI_PLAN.md](plans/reference/SEARCH_UI_PLAN.md)
- [EVALUATION_PLAN.md](plans/reference/EVALUATION_PLAN.md)
- [PASSAGE_SEARCH_PLAN.md](plans/reference/PASSAGE_SEARCH_PLAN.md)
- [SEMANTIC_PRODUCT_PLAN.md](plans/reference/SEMANTIC_PRODUCT_PLAN.md)
- [EVIDENCE_SELECTION_PLAN.md](plans/reference/EVIDENCE_SELECTION_PLAN.md)
- [ANSWER_RELIABILITY_PLAN.md](plans/reference/ANSWER_RELIABILITY_PLAN.md)
- [ANSWER_EVIDENCE_CONTRACT_PLAN.md](plans/reference/ANSWER_EVIDENCE_CONTRACT_PLAN.md)
- [ANSWER_EVIDENCE_POLICY_PLAN.md](plans/reference/ANSWER_EVIDENCE_POLICY_PLAN.md)

## Phase 3.2 검색 실험 증거

- [SEMANTIC_SEARCH.md](evaluation/phase32/SEMANTIC_SEARCH.md)
- [SEMANTIC_SEARCH_PLAN.md](evaluation/phase32/SEMANTIC_SEARCH_PLAN.md)
- [SEMANTIC_EXPERIMENT_PLAN.md](evaluation/phase32/SEMANTIC_EXPERIMENT_PLAN.md)
- [SEMANTIC_FUSION_PLAN.md](evaluation/phase32/SEMANTIC_FUSION_PLAN.md)
- [SEMANTIC_RERANK_PLAN.md](evaluation/phase32/SEMANTIC_RERANK_PLAN.md)

## Phase 3.3 답변 평가·이월 증거

- [FOLLOWUP_VALIDATION.md](evaluation/phase33/FOLLOWUP_VALIDATION.md)
- [FOLLOWUP_QUALITY_RECHECK.md](evaluation/phase33/FOLLOWUP_QUALITY_RECHECK.md)
- [CONVERSATION_RECOVERY_EVALUATION.md](evaluation/phase33/CONVERSATION_RECOVERY_EVALUATION.md)
- [QUOTE_RECHECK.md](evaluation/phase33/QUOTE_RECHECK.md)
- [PHASE33_C3_SCOPE.md](evaluation/phase33/PHASE33_C3_SCOPE.md)
- [PHASE33_COMPLETION_PLAN.md](evaluation/phase33/PHASE33_COMPLETION_PLAN.md)
- [PHASE33_CONDITIONAL_EXIT_PLAN.md](evaluation/phase33/PHASE33_CONDITIONAL_EXIT_PLAN.md)
- [PHASE33_OPERATIONAL_EVIDENCE.md](evaluation/phase33/PHASE33_OPERATIONAL_EVIDENCE.md)

## 과거 상태와 실행 기록

- [CURRENT_HISTORY_20261021.md](history/CURRENT_HISTORY_20261021.md)

[역사 자료 안내 및 원본 해시](history/README.md). 종료된 실험의 실패와 승인 범위도 보존한다.
