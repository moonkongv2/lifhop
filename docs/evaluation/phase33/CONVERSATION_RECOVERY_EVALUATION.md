# 제한된 후속 질문을 통한 회수 평가

현재 단계: [조건부 종료 수용](PHASE33_CONDITIONAL_EXIT_PLAN.md)으로 Phase3.3은
종료됐고 Phase4.1 계획을 준비한다. 실제 개인 후속 검증은 D04로 이월했으며 아래
기존 실패/미검증과 실행 승인 범위는 변경하지 않는다.

2026-10-21. 평가 상태·합성 검증 구현 완료, 실제 회수 실측은 미승인이다.
소유자는 첫 응답 평가를 유지하면서 후속 질문으로 원하는 답에 도달하는 평가를 추가했다.

## 판정과 중단 기준

첫 질문·루브릭·근거·판정을 보존하고 대화 회수 결과를 별도 기록한다. 불완전해도
근거에 충실한 답변에는 최대2회 후속을 허용한다. 없는 결과를 만들거나 첫 실패를
후속 성공으로 덮어쓰지 않는다.

| 관찰 | 첫 응답 판정 | 대화/회수 판정 |
| --- | --- | --- |
| 첫 답변에서 필요한 내용 회수 | 통과 | 대화 통과 / 회수 불필요, 후속0회 |
| 첫 답변 누락, 후속1~2회 안에 회수 | 기존 부분 충족/실패 그대로 | 회수 통과 |
| 후속2회 뒤에도 핵심 누락 | 기존 판정 그대로 | 회수 실패, 추가 전송 중단 |
| 인용/형식 실패 또는 안전 위반 | 실패 보존 | 차단, 후속으로 우회하지 않음 |
| 원문 대조 검토 대기 | 기존 판정 보존 | 미검토, 다음 질문 전송 불가 |

생성 모델의 `supported` 자기 보고와 원문 대조 판정을 분리한다. 사용자나 검토
에이전트가 질문의 필수 사실/근거/미확인 범위/귀속·인용별 지지를 확인한 결과만
`source-review`로 기록한다. 생성 응답에는 이 판정 객체를 받지 않는다. 합성 oracle은
synthetic 모드에서만 허용하고 실제 의미품질 근거로 사용하지 않는다.

후속 질문과 예상 분기는 사전 동결한다. 정답 문장·커밋 hash·원문 위치/ID·파일명을
알려주지 않는다. 알려진 정답 hint 검사는 보조 장치이며, 자연스러운 질문인지도
검토한다. 모든 의미적 유도를 자동 탐지한다고 주장하지 않는다. 원문 정책/버전,
입출력·문맥 상한 및 새 질문별 동의를 유지한다. 성공하면 남은 질문은 보내지 않는다.
재설명은 reuse, 새 구현 사실 찾기는 search가 필요하다. 예상과 다른 분기/되묻기는
임의로 응답을 만들어 추가하지 않고 중단/미검증으로 남긴다. R2 인용 거부는 우회하지 않는다.

## 기존 R1 검토 결과 — 후속 대상에서 차단

2026-10-21 원본 capture를 무과금으로 재검토했다. R1의 보관함 차감·사용한 보상
보존은 붙인 인용이 지지하지만, 같은 문장의 **해당 식사 보상 칸 제거**는 그렇지 않다.
인용은 보상 칸을 찾을 수 있다고 설명할 뿐 제거 동작을 직접 지지하지 않는다.
선택됐지만 인용되지 않은 다른 발췌문에 제거 설명이 있어도 반환 인용을 보완한 것으로
간주하지 않는다. 이는 그 정책 자체가 거짓이라는 판정이 아니라 인용 지지 실패다.

첫 `failed-retrieval`과 원본은 유지하고 추가 근거 검토를 별도 보존했다. 기존 R1은
`blocked`, 후속0회다. R2도 원문 불일치 `claim_evidence`를 재현해 `blocked`다.
이 둘을 후속 질문으로 통과시키지 않는다. 실제 AI/개인 DB 조회·쓰기/추가 과금은0이다.

[사전 검토 도구](../../../scripts/review_conversation_recovery.py)는 저장된 request/response의
canonical JSON SHA-256을 검토에 묶고 제품 parser를 그대로 재실행한다. 형식/인용 통과
시 모든 fact/known의 위치·문장을 검토와 대조하며 누락·중복·변조를 거절한다.
unsupported가 있으면 낙관적인 종합 판정도 차단하고 원래 판정은 따로 남긴다.
의미 지지는 검토자가 판단하며 자동으로 입증하지 않는다. 이 도구는 DB/전송 기능이나
실행 승인 권한이 없다. 현재 권한·버전 검증과 개인 기록용 단계 실행 adapter는 여전히
구현 전이므로, eligible 보고서만으로 실제 전송할 수 없다.

private 결과: `.local/evaluation/phase33/recovery-eligibility-20261021-v1/`의
R1/R2-review·report와 original-capture-digests. 원본 capture/원장/종료 marker는 수정하지 않았다.

새 회귀10개 포함 전체backend925개(73.09초), 관련39개, py_compile/diff와 원본 불변
audit를 통과했다. 관련 재실행 중 sandbox의 로컬 DB 연결 제한으로39개 setup error가
발생했으며 테스트 DB 접근 권한을 적용한 재실행은 통과했다. 제품 assertion 실패는 없었다.
검토자는 R1-report의 `blocked`/`safe=false`, R2-report의 `claim_evidence`/
`output_valid=false`, 둘의 `followups_used=0`/`authorization=none`을 확인하면 된다.
브라우저 검증은 필요 없고 프론트 검사도 재실행하지 않았다.

후속 보완/검증 상태는 아래 v6 항목을 따른다. 기존 실패 답변은 고쳐 저장하지 않는다.

## v6 인용 생성 지침 보완 — 실제 모델 개선은 미검증

사전 검토 도구를 `27b5575`로 커밋한 뒤 `answer_claims.py`의 지침과 필드 설명을
`part-results-v6`로 갱신했다. 120자까지 채우는 대신 가급적80자 이내의 짧은 연속 구간을
복사하도록 안내한다. 80자는 권장값이며 기존120자 hard limit은 그대로다. Markdown/
backtick/공백/문장부호/원어를 JSON 복호화 후에도 보존하며 의역·정규화·번역·중간
생략으로 인용을 만들지 않는다. 주장별 직접 지지가 필요한 절은 나누고, 찾기/조회
가능하다는 설명을 변경/삭제 사실의 근거로 쓰지 않도록 명시했다. 같은 발췌문 안의
다른 내용이나 이전 답변으로 인용 지지를 대신할 수 없다. 일반 합성 예시만 사용했다.

wire 필드·parser·입출력/문맥 상한·가격·검색/선택·소유자/권한 gate는 바꾸지 않았다.
지침/필드 설명 변경으로 answer/dialogue 설정 hash는 바뀐다. 구승인을 재사용하지 않는다.
대표 S1/R1/R2 요청을 offline으로 재구성했으며 질문/발췌문/이력은 그대로다. 요청은
각각7,258/14,995/23,765바이트로 적용 상한 이내다(세 요청 모두 빈 이력의 대화64KiB).
대표 요청은 이전보다727바이트 늘었으며 상한에 가까운 입력의 여유는 그만큼 줄어든다.
초기 지침은1,437바이트 늘어 큰 원문 선택 회귀2개가 실패했다. 중복 설명을 압축해
기존1900자 다중 바이트 원문을 통째로 선택하는 동작과 commit 선택의 byte gate를 복구했다.
해당 기존 테스트를 수정하거나 요청 상한을 늘리지 않았다.
추가 모델 호출/재시도나 인용 자동 보정은 없고 실제 지연·비용 변화는 측정하지 않았다.

합성 회귀는 정확한 Markdown/개행/다중 공백/Unicode/한글 인용을 수용하고, 정규화/
번역/중간 생략 인용을 거부하며, 긴 원문의 짧은 구간·분리된 주장과120자 경계를 확인한다.
기존 R2 raw는 여전히 `claim_evidence`로 거부되며 기존 R1의 의미 지지 실패도 보존한다.
기존 합성 대화 dry-run도 첫 partial → search 후속 → 회수 → 후속2 미전송/첫 턴 불변을
통과했다. 실제AI/개인DB조회·쓰기0, 합성5호출, 임시 schema 삭제 완료다.
private 요청 재구성/기존 응답 replay/dry-run은
`.local/evaluation/phase33/quote-fidelity-20261021-v2/`에 보존했다(v1은 초기안 이력).

브라우저 없이 다음 명령으로 원문 보존/거부와 큰 원문 선택48개를 확인할 수 있다.
로컬 `_test` DB가 필요하며 외부 AI는 호출하지 않는다.

```sh
.venv/bin/pytest -q tests/test_answer_quote_fidelity.py tests/test_answer_evidence.py
.venv/bin/python -m scripts.check_conversation_recovery --dry-run \
  --out .local/evaluation/phase33/quote-fidelity-user-1
```

dry-run report는 first_response partial, 회수 passed, 후속1회/두 번째 미전송,
first_turn_unchanged=true, provider_calls=0, semantic_quality=not-evaluated가 기대값이다.
최종 전체backend938개(74.11초), 관련48개, py_compile/diff 및 offline audit를 통과했다.
초기 전체 실행의2실패/936통과는 지침 압축 후 해소했다. 프론트는 미변경으로 미실행.

이는 생성 지침과 보호의 검증이며 실제 모델의 정확한 복사·의미 지지 개선을 입증하지
않는다. [OpenAI 공식 문서](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes)도
구조화 출력에 내용 오류가 남을 수 있음을 명시한다. 다음은 새 첫 응답 후보 확보용
유한 재검증 protocol/무과금 dry-run 준비다. 실제 전송은 별도 승인을 받고, 새 응답이
원문 검토를 통과한 뒤에만 개인 기록용 후속 단계 실행기를 준비한다. R1/R2 차단과
C3–C6 미완료는 유지한다.

이후 수신처 명시 승인으로 고정 문맥3회 재검증을 실행했고 USD0.001491로 종료했다.
R1은 기존 미지지 절을 쓰지 않았으나 S1 누락/분류와 R2의41자 Markdown 인용 거부가
남았다. [실제 결과](QUOTE_RECHECK.md#실제-실행-결과--승인-종료)를 따른다. 기존 저장
대화 차단을 해제하거나 후속 실측을 승인한 것은 아니다. 다음은 원문 인용 후보 ID
선택 방식의 장단점 검토이며 추가 유료 호출은 없다.

## 보존한 최초 적용안 — 기존 R1 (현재 실행 금지)

종료된 C3 R1의 `failed-retrieval`은 유지한다. 커밋을 지어내지 않고 partial로 답한
사실도 보존한다. 원본/원장/종료 marker는 바꾸거나 이전 승인을 재사용하지 않는다.
기존 검토의 인용 지지 주의 항목도 재확인한다. 원문과 다른 단정/근거 위반이 확인되면
회수 대상으로 넘기지 않고 차단한다. 현재 R1이 안전 gate까지 통과했다고 새로 선언하지 않는다.

1. 기존 첫 질문/답변·인용·회계·판정 hash를 새 평가에 연결한다. 첫 답변을 재생성하지
   않고 현재 대화 revision/history hash·원문 권한·버전을 확인한다.
2. 후속1: **“그 변경을 구현한 커밋도 찾아줘.”** 이전 문맥을 해석하고 새 검색을 한다.
3. 원문 대조 검토 뒤 필요한 경우만 후속2:
   **“앞서 정한 정책과 직접 연결되는 구현 기록이 있는지 근거를 보여줘.”**
4. 반환 인용이 같은 변경의 구현 커밋과 정책 연결을 지지하는지 확인한다. 배포 성공을
   추론하지 않는다. 최대2회 뒤 종료하며 추가 턴/시간/비용과 첫 성적을 함께 보고한다.

두 후속을 모두 search로 준비하면 최대 추가6호출(planner2/query2/answer2), 기존
로컬 가격/상한의 예약USD0.023634다. 첫 질문부터 시작하는 별도 사례는 최대8호출/
USD0.032379다. 실행 승인이나 실제 예약이 아니며 실행 protocol 동결 때 재계산한다.

현재는 개인 기록용 단계 실행 adapter를 구현하지 않았다. 안전한 후보 확보 후 준비에는 대화/
마지막 턴·revision·history hash·원문 allowlist·질문/분기·현재 코드/가격·중앙 예산을
묶는 새 protocol과 단계별 재실행 방지가 필요하다. 제품 응답에서 인용/형식 gate를
확인하고, 각 후속의 원문 검토 전 다음 전송을 막아야 한다. 원래13호출 승인의 남은
8호출은 사용할 수 없다. 새 무과금 검증과 별도 유한 승인 전 실제 전송은 없다.

## 이번 구현·무과금 검증

[평가 상태](../../../app/evaluation/conversation_recovery.py)는 첫 판정 보존·검토 순서·최대2회·
조기 종료·invalid/unsafe 차단·호출/비용 envelope를 다룬다.
[합성 도구](../../../scripts/check_conversation_recovery.py)는 `--dry-run`만 지원한다.
제품의 검색/답변 계약·순위·의존성·스키마·API는 수정하지 않았다.

합성 메모6개와 가짜 query vector로 첫 답변의 구현 기록 누락 → 후속 새 검색 →
구현 기록/인용 회수 → 두 번째 후속 미전송을 확인했다. 실제 제품 API/문맥/선택/
예약/정산/저장을 거쳤으며 첫 턴/판정은 그대로 남았다. fixture 정답은 합성 검토기에만
쓰며 질문이나 강제 선택 근거로 넣지 않는다. 실제 모델·검색 정확도와 GitHub adapter를
검증한 것은 아니다. 자료는 synthetic manual NOTE다.

외부 HTTP/AWS와 기본 앱 DB 연결을 차단하고 loopback `_test` 임시 schema만 썼다.
실제 AI/개인 DB 조회·쓰기0, 합성5호출/spent5행, schema 정리 완료다.
관련29개/전체backend915개(74.17초), py_compile/diff 검사 통과. 프론트 미변경으로
frontend 검사는 재실행하지 않았다. 결과는 private
`.local/evaluation/phase33/conversation-recovery-dry-20261021-v2/report.json`이다.

```sh
.venv/bin/pytest -q tests/test_conversation_recovery.py tests/test_c3_validation.py
.venv/bin/python -m scripts.check_conversation_recovery --dry-run \
  --out .local/evaluation/phase33/conversation-recovery-dry-user-1
```

저장소 루트, 기존 로컬 `_test` DB와 새 출력 경로가 필요하다. report의 첫 응답 partial,
회수 passed, 후속 사용1/한도2, 두 번째 미전송, `semantic_quality=not-evaluated`를
확인한다. 한 사례의 회수 성공으로 평가셋 전체나 Phase3.3 완료를 선언하지 않는다.
