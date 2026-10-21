# v6 고정 문맥 인용 재검증

2026-10-21. **실행기·dry-run 검증 완료, 실제 전송 승인 대기.** v6 지침은 `69cb7ea`에 커밋했다.

기존 C3에서 사용한 첫 질문·선택 발췌문·빈 이력을 그대로 사용해 새 답변을 만든다.
이는 답변 생성/인용의 제한된 진단이다. 검색·선택 품질, 저장 대화·후속 회수, 전체
C3 통과를 검증하지 않는다. 기존 R1/R2 대화를 이어 쓰거나 실패 답변을 고쳐 저장하지 않는다.

| 순서 | 확인 범위 | 최대 호출 | 예약 상한 USD |
| --- | --- | --- | --- |
| S1 | 기존 합성 사례: 명시된 한계와 scoped gap, fact/인용 지지 | answer1 | 0.002877 |
| R1 | 기존 개인 사례의 정책 설명: 각 주장에 직접 지지하는 인용, 없는 구현 커밋을 만들지 않음 | answer1 | 0.003650 |
| R2 | 기존 개인 사례의 채택/이유: Markdown 등 원문 그대로의 인용, 요청하지 않은 검증 요구 배제 | answer1 | 0.004527 |
| 합계 | 순서 고정, 재시도0 | **3** | **0.011054** |

가격은 현재 코드에 고정된 로컬 단가이며 실시간 공급자 가격 조회가 아니다. 실제 payload
바이트 수+1,024를 입력 토큰의 보수 상한으로 쓰고 출력4,096까지 예약한다. 원문·입력
필드·64KiB 상한·model/가격/설정 hash·코드 hash가 동결돼 변경 시 새 protocol이 필요하다.
각 전송 timeout45초, 실행 시작180초 뒤에는 다음 사례를 시작하지 않는다.

개인 원문은 R1/R2에서 각각 기존 선택5개만 새 답변 생성에 보낸다. 이전 생성 답변은
전송하지 않는다. 권한·현재 버전·원문 범위/hash를 metadata gate로 확인한 후 본문을
읽고 실제 발췌문이 frozen payload와 같은지 대조한다. 권한 lock 대기 후 최신 상태를
보도록 READ COMMITTED를 사용하며 전송 동안 shared owner lock을 유지한다.
전체 허용 corpus52기록/1097벡터와 기존 원장의 변경도 확인한다.

실제 실행은 기존 중앙 billing scope/월 예산/원장/call slot을 사용한다. S1은 protocol별
합성 owner, R1/R2는 기존 소유자에 body-free 회계만 남긴다. 개인 대화·원문·벡터·정책은
쓰지 않는다. 요청/응답/검토는 ignored `.local/evaluation/`에0600으로 보존한다.
정상 사용량은 출력 인용 검증 전에 spent로 정산하고, 전송 후 사용량 불명은 uncertain,
전송 전 확정 차단은 released로 남긴다. 출력/권한/예산/사용량 실패 시 남은 사례를 중단한다.
동일 protocol은 canonical 시작 marker로 소비되므로 출력 경로를 바꿔 재실행할 수 없다.

## 승인 대상과 재현

승인 대상 private protocol:
`.local/evaluation/phase33/quote-recheck-20261021-v2/protocol.json`

Digest: `56b3b9fbcfa0f8af62b556cea73ba3e1e550bd00345e5dd0d2ef9c4ba67d81e9`.
이전 C3 승인은 종료됐고, 준비 v1도 최종 코드 보완으로 대체됐다. 둘 다 재사용하지 않는다.

```sh
.venv/bin/pytest -q tests/test_quote_recheck.py
.venv/bin/python -m scripts.run_quote_recheck --dry-run \
  --protocol .local/evaluation/phase33/quote-recheck-20261021-v2/protocol.json \
  --out .local/evaluation/phase33/quote-recheck-user-dry-1
```

로컬 `_test` DB와 새 출력 경로가 필요하다. dry-run은 원문을 현재 권한으로 read-only
대조하지만 실제 AI/개인 DB 쓰기는0이다. HTTP/AWS와 기본 앱 DB 연결을 막고 가짜
응답·임시 원장으로3회 예약/정산/parser를 확인한다. report의 completed/attempts3/
outstanding0/provider_calls_upper_bound0/isolated_schema_removed=true/answer_mode=off를
확인한다. synthetic supported는 의미품질 통과가 아니며 판정은 not-reviewed다.

최종 dry-run은3회/합성spent3행(18 micro USD의 가짜 정산), outstanding0, 실제 AI/
개인 DB쓰기0, 임시 schema 삭제로 완료됐다. 독립 대조에서도 기존 개인 원장515행의
전체 필드·52기록/1097벡터가 그대로였다. 새16개/최종 전체backend954개(77.37초),
py_compile/diff/audit 통과. 초기 fixture import/모델 접근 오류와 S1의 빈 dialogue 필드
보존 오류는 보완 후 해소했다. 프론트·제품 API·의존성·DB 스키마는 미변경이다.
최종 결과는 같은 protocol 디렉터리의 `dry-run/`, `audit.json`에 보존했다.

실제 실행은 위 digest에 대한 별도 승인 후 `--execute --approve-digest <digest>`로
같은 protocol을 사용한다. 기본 answer mode는 off로 유지한다. 브라우저는 필요 없다.

## 실제 응답 검토 기준

생성 모델의 상태와 독립적으로 원문/인용별 지지·질문 범위·명시 한계·귀속을 검토한다.
정확한 quote 검증만으로 모든 절의 의미 지지를 판정하지 않는다. R1은 frozen 문맥에
필수 구현 커밋이 빠져 있으므로, 생성 지침 검토를 통과해도 원래 E1 통합 검색 실패를
통과로 바꿀 수 없다. R2도 새 출력만 별도 검토하고 기존 failed-output-validation은 보존한다.
새 응답이 안전한 partial이더라도 저장 대화의 실제 후속 회수는 별도 단계 실행기와
protocol/승인이 필요하다. C3–C6 및 Phase3.3은 계속 미완료다.
