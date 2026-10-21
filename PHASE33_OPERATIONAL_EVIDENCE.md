# Phase3.3 보호·운영 증거

2026-10-21. 이후 소유자가 나머지 UX를 확인해 C2를 수용했다(종료 체크리스트4.3절).
아래 합성 브라우저 기록 자체는 에이전트 관찰이며 사용자 관찰로 바꾸지 않는다.
기준 커밋 `d20a04f`의 제품 코드는 backend886개가 통과한 `40567d8`과
동일하다. 그 이후 변경은 상태 문서뿐이다. 이 문서는 C4의 증거 연결이며 C2 수용,
C3 실측 승인, C4 전체 완료 또는 Phase3.3 종료를 뜻하지 않는다.

## 보호 동작과 회귀 연결

아래 테스트는 별도 언급이 없으면 [대화 회귀](tests/test_answer_conversations.py)에 있다.
직전 전체backend886/대화18개 통과 결과를 재사용한다. 이번에는 테스트를 재실행하지 않았다.

| 확인 대상 | 구현/기존 검증 | 확인 범위와 제한 |
| --- | --- | --- |
| 소유권 | `test_foreign_owner_ids_and_body_limit`, `test_stage_and_base_ids_cannot_cross_conversations` | 계정·대화 간 ID 혼용 차단. UI 캐시 격리는 [frontend 회귀](frontend/src/pages/conversations.test.tsx)의 계정 변경 사례와 기존 합성 브라우저 결과를 연결 |
| 전송 전 출처 검사 | `test_source_revocation_blocks_planner_without_loading_body`, `test_clarification_chain_preserves_pending_and_permission_change_blocks_next_call` | 권한 철회 후 새 문맥 생성/전송 차단. [metadata gate](app/services/conversation_context.py)는 소유자·현재 버전·정책·projection을 검사한 뒤 원문을 읽음 |
| 원문 삭제 | `test_source_delete_redacts_transitive_text_but_preserves_billing` | 종속 답변/파생 해석 redaction, 기존 회계 보존. 갱신/제외는 삭제와 달리 이력 표시를 허용하고 재전송을 차단하므로 모두 같은 숨김 처리라고 주장하지 않음 |
| Stop·삭제 경합 | `test_stop_and_delete_finish_during_provider_and_late_output_is_discarded`, `test_source_writer_waits_for_provider_guard_without_blocking_stop` | 공급자 응답 대기 중에도 Stop/삭제 완료, 늦은 응답으로 상태/대화를 복원하지 않음. 프론트의 Stop snapshot 회귀도 기존205개 통과에 포함 |
| 중복 실행·복원 | `test_duplicate_stage_during_provider_has_one_paid_call`, `test_persistent_followup_relogin_close_replay_and_delete`, `test_fresh_api_processes_restore_history_and_never_resume_unfinished_work` | 동일 단계 중복 유료 호출 방지, 이력 조회/새 프로세스 복원으로 단계 자동 재개 없음 |
| 실패 회계 | `test_dispatch_failure_is_uncertain_and_never_retries`, `test_parse_failure_is_spent_without_saved_body` | 전송 후 모호한 실패는 uncertain, 사용량 확인 뒤 파싱 실패는 spent로 보존. 재시도/성공 응답 합성 없음 |
| 공유 예산·실행 범위 | [실행기 회귀](tests/test_followup_runner.py)의 `test_separate_billing_engine_uses_shared_budget`, `test_guard_stops_before_reservation_and_transport`, [Semantic 회귀](tests/test_semantic_product.py)의 `test_exhausted_month_budget_blocks_the_transport` | 격리 원문 검증도 승인된 실행 시 중앙 예산 사용, stale/재실행/예산 초과 전 차단. 이전 유료 승인은 모두 종료됨 |
| 큰 이력·문맥 | `test_large_history_pages_and_source_redaction_are_bounded`, `test_dialogue_capacity_keeps_five_complete_sources_and_pins_priced_profile` | 합성1000턴 페이지/삭제 및5개 온전한 원문·문맥 profile 검사. 실제 긴 문맥 모델 준수/일반 지연 성능의 증거는 아님 |

대화/이전 AI 응답은 해석용 비신뢰 데이터이며 사실의 근거는 현재 선택 원문이다.
[planner 지침](app/services/followup_transport.py)과 [answer 지침](app/services/answer_transport.py)에
이 경계가 있다. [품질 회귀](tests/test_followup_answer_quality.py)는 계약 전달/합성 저장을
검사한다. 이는 실제 모델의 prompt injection 저항이나 모든 사실의 의미적 지지를 증명하지 않는다.

## 현재 상한과 오류 표시

| 항목 | 현재 코드 값/동작 | 근거 |
| --- | --- | --- |
| 질문/이력/요청 | 질문256자·2048bytes, 이력16KiB, planner wire24KiB/출력1024tokens, answer wire64KiB/출력4096tokens | [입력 schema](app/schemas/answer_conversation.py), [planner](app/services/followup_transport.py), [answer](app/services/answer_transport.py). Wire 크기는 JSON 전체 기준이며 예약 입력은 wire+1024의 보수적 상한 |
| 근거 선택 | 그룹 대표 후보 최대20, 최종 원문 최대5개·각2000자. 크기 초과 시 선택 누락/이전 선택적 이력 생략을 Context sent에 기록 | [선택/문맥 조립](app/services/conversation_stages.py). 필수 문맥이 안 들어가면 오류/근거 부족, 원문을 임의 축약하지 않음 |
| 대화 예약 | planner 최대3072 + query 입력2048bytes envelope41 + answer 최대8704 =11817 microUSD(USD0.011817) | [기존 로컬 가격/예약](app/services/ai_usage.py). 실제 전송 payload에 맞춰 예약하며 최대3 AI 호출. 현재 공급자 가격을 새로 조회한 값이나 예상 실청구액은 아님 |
| 월 한도/동시성 | 설정상 AI 월 상한 최대USD1, billing scope당 공급자 call slot1, 단계별 call limit1 | [설정](app/config.py), [회계](app/services/ai_usage.py). 여러 단계 합계 예약/기존 uncertain도 예산에 반영. 호스팅 포함 월USD20 출시 목표와 별개 |
| 시간 | 질문 action deadline120초, 단계 lease120초, 실제 공급자 timeout은 planner30초/query10초/answer45초와 남은 action 시간 중 작은 값 | [단계 실행](app/services/conversation_stages.py), [프론트](frontend/src/pages/ConversationPage.tsx)의120초 중단. DB lock2초/statement5초는 owner guard 경로에 적용. 강제 프로세스 종료/모든 DB·HTTP 작업의120초 완료를 보장하지 않음 |
| 페이지 | 목록/턴 페이지50개, 의존 anchor 검사 최대500개 | [대화 조회](app/services/answer_conversations.py), [gate](app/services/conversation_context.py). 전체 이력을 매 요청에 모두 보내지 않음 |
| 오류/재시도 | timeout, 예산 소진, 출처/문맥 변경, index 불가를 별도 코드로 보존/반환. 근거 부족은 no_hits/byte_limit, 답변 호출 없음 | [API](app/api/answer_conversations.py), [UI](frontend/src/pages/ConversationPage.tsx), [클라이언트](frontend/src/api/answerConversations.ts). UI는 코드와 저장 상태 새로고침·기과금 가능성·자동 재시도 없음을 표시. 모든 코드에 친절한 한국어 설명이 있는 것은 아님 |

기존 legacy 일반 답변의14KiB 제한은 유지된다. C1의 기존 일반2건이 최신 지침에서
그 제한에 걸렸으므로 저장 대화64KiB의 통과와 혼동하지 않는다. 새 문맥 상향은 하지 않았다.

## 실측·환경 증거와 남은 범위

| 증거 | 확보한 결과 | 적용 한계 |
| --- | --- | --- |
| [기존 실제 합성 후속 실행](FOLLOWUP_VALIDATION.md) | 8질문/18호출, USD0.001643, 질문별 공급자 시간 합2.18–6.45초, 신규 uncertain0 | 실제 공급자를 썼지만 원문은 합성. 지침 변경 전이며 의미품질6통과/2부분 |
| [후속 품질 재검증](FOLLOWUP_QUALITY_RECHECK.md) | 3질문/7호출, USD0.000693, 질문별 공급자 시간 합 T1=7.41초/T5=10.03초/T8=4.88초, 신규 uncertain0 | 2통과/1부분. v5 실제 모델 준수와 개인 기록 자동 검색은 미검증 |
| 실제 앱 재시작 | migration `h60f5a47e286` 적용 후 같은 개인 DB/Uvicorn2개에서 임시 미완료 질문 전체 응답 동일, 과금행 무변경, 임시 대화 삭제 | 완성 답변/인용은 기존 pytest 프로세스 회귀로 확인. 실제 개인 DB에서 완성 답변을 생성한 것은 아님 |
| 합성 브라우저 | 기존 Stop/삭제/계정/모바일, 추가 인용 왕복(호출0)·특정 답변 후속·독립 문맥의 이력0 | 에이전트 관찰. 직접 확인한 주요 흐름 이외의 소유자 수용은 대기 |

private 원본 위치는 [종료 체크리스트4.2절](PHASE33_COMPLETION_PLAN.md#42-c2-후속-환경브라우저-검증-2026-10-21)과
위 실행 문서에 있다. 이번 연결의 파일 hash/테스트 심볼/예약 계산/실측 metadata 확인은
`.local/verification/phase33-operational-map-20261021-v1/verification.json`에 보존한다.
새 DB 조회·개인 원문 열람·AI 호출 없이 기존 audit의 body-free 수치만 읽었다.

C4는 **증거 연결 완료, 전체 완료 보류**다. 현재 코드에서 개인 기록 자동 검색/여러 턴의
전체 API·화면 응답 시간과 실제 의미품질은 남은 C3 범위와 함께 판단해야 한다.
이 소표본으로 p95/최대 문맥 성능을 주장하지 않는다. 기존 미확정3건/USD0.006801의
보수적 예산 반영과 최종 처리/수용은 C5에 남기며 임의 정산하지 않는다.
C2 나머지 수용 후 필요한 실제 통합 검사만 유한 범위로 제시하고, 그 범위 승인 전에는
전송하지 않는다. C4 정리를 이유로 C3 승인을 만들거나 C5/C6을 완료 처리하지 않는다.
