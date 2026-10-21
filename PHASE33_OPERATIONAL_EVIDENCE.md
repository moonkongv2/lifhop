# Phase3.3 보호·운영 증거

2026-10-21 CE1/CE2 갱신. 기능 기준은 `17ad489`, 마지막 전체backend954개(77.37초)
통과이며 이후 HEAD `796c1f9`까지 app/scripts/tests/frontend/migrations 변경이 없다.
이번 작업도 문서만 변경하며 기존954개 결과를 재사용한다. 과거 기준 `d20a04f` 이후
제품 서비스 변경은 answer_claims.py의 v6 지침/필드 설명이고 평가 도구/회귀가 추가됐다.
소유권·출처 gate·삭제·과금·저장 대화 경로는 그대로다. 증거를 최신 코드에 연결한
것이며 전체 의미품질/성능 통과를 뜻하지 않는다. 이후 소유자가 D01–D09 이월을
수용해 Phase3.3을 조건부 종료했다. 현재는 Phase4.1 계획이며 정기 수집은 미구현이다.
소유자는 주요/나머지 UX로 C2를 수용했다(종료 체크리스트4.3절). 아래 에이전트의
합성 브라우저 관찰 자체를 소유자의 관찰로 바꾸지 않는다.

## 보호 동작과 회귀 연결

아래 테스트는 별도 언급이 없으면 [대화 회귀](tests/test_answer_conversations.py)에 있다.
해당 대화18개는 마지막 전체backend954개에 포함된다. 프론트205/lint/build는
[이전 UI checkpoint](FOLLOWUP_VALIDATION.md)의 결과이며 `d20a04f..HEAD`의 frontend
diff가 비어 있어 재사용한다. 이번 앱 테스트/lint/build·브라우저 검증은 재실행하지 않았다.
이는 합성 회귀와 기존 소유자 수용의 연결이며 현재 개인 환경 전체의 무결함 증명이 아니다.

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
| 최신 실행기 보호 | [v6 실행기 회귀](tests/test_quote_recheck.py)의 `test_policy_change_committed_while_guard_waits_is_observed`, `test_canonical_live_marker_blocks_replay_to_another_output`, `test_invalid_quote_keeps_raw_and_spent_usage`, `test_invalid_usage_is_retained_as_uncertain_with_raw_capture`, `test_unsent_source_failure_releases_reservation` | 16개 신규 회귀도954개에 포함. 권한 lock 대기 후 최신 상태, 유료 재실행 차단, spent/uncertain/released 구분. 이 검증을 제품 전체의 의미 지지 판정으로 확대하지 않음 |

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

### 사용자에게 보이는 실패와 비용 (CE2)

| 상황 | 현재 동작·사용자 확인 방법 | 관련 이월 |
| --- | --- | --- |
| 인용/출력 검증 거부 | 제품 회귀에서 `failed`/`ANSWER_OUTPUT_INVALID`, 답변 미저장. 화면은 error_code와 No automatic retry를 표시한다. 이미 응답한 사용량은spent. 최근 v6 진단은 제품 UI 호출이 아닌 직접 생성 도구이므로 UI를 새로 검증한 것으로 취급하지 않음 | D01/D09 |
| 출처/문맥 변경 | `CONVERSATION_CONTEXT_UNAVAILABLE` 등으로 재전송 차단. 기존 이력에는 Source updated/excluded/deleted와 독립 문맥 안내가 표시됨. 전송 전 확정 차단의 해당 예약은released, 이전 단계 비용은 남을 수 있음 | D05/D09 |
| 예산 초과·index 불가·근거 없음 | 각각 예산 오류/index 오류 또는 no_hits/byte_limit 구분. 근거 없음은 answer 호출을 하지 않지만 앞선 query 비용까지0이라는 의미는 아님 | D05/D09 |
| 전송 중 장애·중단 | 사용량 불명은uncertain, Stop은 이미 전송한 요청 비용을 되돌리지 않음. 이력에서 usage 상태/미완료 안내를 확인하고 Refresh saved state로 조회. 조회는 유료 작업을 재개하지 않음 | D06/D08/D09 |

현재 오류 설명은 코드/영어 메시지 중심이다. 이는 D09의 알려진 사용성 한계로
남기고 정상 답변이 없는 비용 발생 가능성을 소유자 조건부 수용 범위에 포함한다.
지원 상태 supported는 원문 인용의 의미 지지/완전성까지 독립 검토됐다는 보증이 아니다.

기존 legacy 일반 답변의14KiB 제한은 유지된다. C1의 기존 일반2건이 최신 지침에서
그 제한에 걸렸으므로 저장 대화64KiB의 통과와 혼동하지 않는다. 새 문맥 상향은 하지 않았다.

## 실측·환경 증거와 남은 범위

| 증거 | 확보한 결과 | 적용 한계 |
| --- | --- | --- |
| [기존 실제 합성 후속 실행](FOLLOWUP_VALIDATION.md) | 8질문/18호출, USD0.001643, 질문별 공급자 시간 합2.18–6.45초, 신규 uncertain0 | 실제 공급자를 썼지만 원문은 합성. 지침 변경 전이며 의미품질6통과/2부분 |
| [후속 품질 재검증](FOLLOWUP_QUALITY_RECHECK.md) | 3질문/7호출, USD0.000693, 질문별 공급자 시간 합 T1=7.41초/T5=10.03초/T8=4.88초, 신규 uncertain0 | 당시2통과/1부분. 최신v6나 실제 개인 후속 회수의 증거는 아님 |
| [C3 개인 통합 실행](PHASE33_C3_SCOPE.md) | 5호출(answer3/query2), USD0.001473, R2 인용 거부로 중단·승인 종료. 개인 대화2개 생성, R1 partial/R2 failed의 과금 없는 GET 복원 확인 | R3–R6 미전송. 직접 사용자가 서버 재시작 후 완성 답변/인용을 확인한 증거와 다름 |
| [v6 고정 문맥 실측](QUOTE_RECHECK.md) | 3answer호출, USD0.001491(예약USD0.011054), 신규 uncertain0, R2 claim_evidence로 승인 종료. 응답 확보4.24–4.81초 | 예약/source gate 포함 시간이며 순수 공급자 지연 아님. R2 전체 action 시간 미계측. S1 실패/R1 부분 개선/R2 거부, 검색·저장 대화·개인 후속은 검증하지 않음 |
| 실제 앱 재시작 | migration `h60f5a47e286` 후 같은 개인 DB/Uvicorn2개에서 임시 미완료 질문 복원, 과금행 무변경. 완성 답변/인용 복원은 pytest 별도 프로세스로 확인 | 이후 C3에서 실제 R1 답변을 생성·GET으로 읽었지만 개인 DB 서버 재시작 후 완성 답변/인용의 직접 확인은 여전히 D06 |
| 합성 브라우저 | 기존 Stop/삭제/계정/모바일, 원문 왕복(호출0)·특정 답변 후속·독립 문맥 이력0. 주요/나머지 C2는 소유자 수용 | 에이전트 관찰/소유자 수용의 범위는 다름. 실제 개인 후속 품질은 D04 |

private 원본 위치는 [종료 체크리스트4.2절](PHASE33_COMPLETION_PLAN.md#42-c2-후속-환경브라우저-검증-2026-10-21)과
위 실행 문서에 있다. 과거 연결은 `.local/verification/phase33-operational-map-20261021-v1/`,
이번 CE1/CE2의 파일 hash/테스트 심볼/예약 계산/실측 metadata 확인은
`.local/verification/phase33-conditional-evidence-20261021-v1/verification.json`에 보존한다.
이번에는 기존 보고/audit의 집계 metadata만 대조했고, 새 DB 조회·개인 원문/생성 응답의
내용 검토·AI 호출은 없다. 22개 참조 테스트 심볼과 코드/프론트 불변, 로컬 예약 계산,
종료된 protocol/원장 집계·UI 메시지·문서 링크·기존 체크/이력 보존 검사를 통과했다.

## C/E 결과와 이월 연결 (CE2)

| 항목 | 확보한 결과 / 남은 범위 | 처리·이월 |
| --- | --- | --- |
| C0–C2 | 문서/사례 매핑과 소유자 주요·나머지 UI 수용 완료 | 기존 체크 유지. UI 수용으로 실제 모델 품질을 대체하지 않음 |
| C3 / E1 | 개인 통합 실행5호출에서 R2로 중단. R1은 정책 회수/커밋 누락. v6는 이전 미지지 절 미재현/7개 인용 정확, 커밋 누락 유지 | 기존 실패 보존. D02/D04/D05 |
| E2 / 추가 인용 회귀 | 채택·이유 근거는 선택됐지만 R2 인용 불일치로 답변 거부. v6에서도41자 인용 변형. 원래 추가 인용 개인 R4는 미전송 | D01/D03/D05 |
| E3 / 생활 seed | 기존 고정 문맥에서 생활 진행 누락. 원래 R3 미전송. 합성 S1을 개인 생활 사례 통과로 바꾸지 않음 | D03/D05/D07 |
| E4/E5 | 기간/과거의 기존 고정 문맥 통과를 해당 범위에만 재사용. 현재 자동 검색·권한·버전/복원 전체는 미검증 | D05/D06 |
| E6 / S1 | 기존 운영 한계 사례의 유용한partial 통과는 보존. S1의 명시 제한/scoped gap 누락·supported 분류는 여전히 실패 | D03/D05 |
| C4 | 최신 보호/회계 회귀 및 제한 실측의 비용/오류를 연결함. 실제 긴 이력·API/화면 전체 시간과 개인 재시작 확인은 미검증 | 보호 증거 연결=CE1 완료, 운영 한계=D06/D09. C4 전체 통과 아님 |
| C5/C6 | CE1/CE2 정리 뒤 소유자가 D01–D09/제한을 수용하고 상태 문서 반영/커밋을 지시함 | CE3/CE4 완료. C5/C6는 조건부 범위로 완료, 기존 C3/C4 결과와 품질 실패는 보존 |
| 평가셋·RPM seed | 20건 draft(12건 Candidate), 별도10건 reviewed이며 전체 품질 통과 아님. RPM 미검토/생활E3 연결 | D07 유지. 원본 revision/평가 결과는 미변경 |
| 기존 uncertain | 예전3건의 보수 예약USD0.006801은 유지. 최근 C3/v6의 신규 uncertain0. v6는 기존515행 전체 필드 보존/새spent3행만 추가 | D08. 확인 증거 없이 정산/삭제하지 않음 |

현재 남은 통합 범위와 이월 ID의 기준은 [조건부 종료안](PHASE33_CONDITIONAL_EXIT_PLAN.md)이다.
CE1–CE4는 완료이며 C3/C4는 미충족·이월, C5/C6는 소유자가 수용한 조건부 범위로
완료했다. 현재는 Phase4.1 개발계획 준비 단계다. 특정 회귀·제한된 실측에서 보고된 보호 위반은
없지만 포괄적 보안 감사나 모든 의미 지지/완전성의 보장은 아니다. 이 소표본으로
p95/최대 문맥 성능을 주장하지 않으며 현재 닫힌 유료 승인을 재사용하지 않는다.
