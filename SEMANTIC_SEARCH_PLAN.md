# Phase 3.2B — 의미 검색의 효과 검증과 제한된 적용

작성: 2026-10-08. 상태 갱신: 2026-10-09. B1 구현·합성 검증·승인된 첫 실제 비교 완료.
첫 비교와 단계별 순위 진단을 완료했으나 한국어 2문항을 회복하지 못해 B2 진행 기준 미충족.
다음 제안은 같은 정답·모델·문서 범위에서 더 작은 주제별 문단을 비교하는 실험이다.
B2는 B1 결과 확인 후 조건부 진행. 3.2A 사용자 확인 1–5 완료.

## 1. 목표와 완료 범위

한국어 질문으로 관련 영문 원문 문단을 찾을 수 있는지 검증한다. 같은 승인
질문·근거·검색 대상에서 단어 검색, 벡터 검색, 두 검색을 합친 결과를 비교한다.
결과는 기존 View passage에서 원문 위치와 버전을 확인한다. 답변 생성은 3.3이다.

현재 실제 pilot은 같은 영문 README에 기반한 승인 3문항이다. 자연어 질문의
완전한 근거 발견은 기존 문단 검색 1/3이며 한국어 2문항은 실패했다. 보조
키워드 점수와 자연어 질문 점수는 분리한다. 원본 pilot과 과거 보고서는 유지한다.
3문항의 개선만으로 전체 자료·일상·복수 출처의 품질이 검증됐다고 설명하지 않는다.

### 두 확인 지점

| 단계 | 구현 결과 | 다음 단계 조건 |
| --- | --- | --- |
| B1 실험 | 인증된 로컬 CLI, 제한된 임베딩 전송, 메모리 내 정확한 벡터 비교, 비용/품질 보고 | 사용자 결과 확인, 권한/비용 검증 통과, 아래 품질 기준 충족 |
| B2 제품 적용 | pgvector 영속 저장, 갱신/작업 처리, Semantic/Hybrid 브라우저 검색 | 기능·권한·수정/삭제 검증 및 사용자 화면 확인 |

이번 계획은 B1과 조건부 B2를 포함한다. B1 결과를 먼저 보여주고 확인을 받은 뒤
B2로 진행한다. B1이 실패하면 3.2A를 유지하고 실패 원인·다음 실험안을 보고한다.
모델 변경, 평가 정답 변경, 전체 자료 전송으로 실패를 숨기지 않는다.

## 2. 선택할 기술과 실행 환경

- 첫 후보: OpenAI `text-embedding-3-small`, 기본 1536차원, cosine 거리.
  모델·차원·입력 구성 버전을 고정하고 다른 설정의 벡터를 섞지 않는다.
- B1은 최대 5,000개 문단을 메모리에만 보관하고 정확한 거리 계산으로 비교한다.
  표준 라이브러리 `array('f')`로 벡터를 압축 보관한다. 5,000×1536개 float32의
  벡터 자체는 약 30.7MB이며 입력·응답·채점 메모리는 별도로 제한한다.
  원문/벡터 파일을 별도로 내보내지 않는다. 중간 종료 후 완료 문단을 다시 보내는
  비용을 예상/기록한다. 실행 중 메모리 상한 256MiB를 넘으면 명시적으로 중단한다.
- B2는 기존 PostgreSQL 17에 pgvector를 추가해 `vector(1536)`에 저장한다.
  첫 구현은 정확한 검색이며 HNSW/IVFFlat은 측정된 성능 요구가 있을 때 검토한다.
- API 호출은 `httpx`를 런타임 의존성으로 이동해 작은 전용 transport에서 수행한다.
  현재 개발 의존성으로 사용 중이다. OpenAI SDK와 범용 LLM 프레임워크는 추가하지 않는다.
  B2에서 SQLAlchemy 벡터 타입/거리 연산을 위해 `pgvector` Python 패키지를 추가한다.
- 토큰 예약은 UTF-8 바이트 길이를 보수적인 상한으로 사용한다. `cl100k_base`의
  byte-level 토큰화에 대한 상한을 합성 다국어/특수문자 검증으로 확인하고, 이 전제가
  다른 모델에 적용되지 않으면 새 tokenizer/config 없이는 그 모델을 활성화하지 않는다.
- 원격 vector store, 새 AWS 서비스, Redis, 자동 수집, reranking, 제목 요약은 범위 밖이다.

공식 자료 확인일: 2026-10-08. `small` 표준 입력 가격은 100만 토큰당 USD 0.02이며,
기본 차원은 1536이다. API 입력당 최대 8192토큰, 요청 전체 최대 300,000토큰이
문서화되어 있다. 앱은 그보다 작은 제한을 사용한다. 가격과 계정별 접근/한도는
실제 전송 직전 재확인한다. 벤치마크 설명은 이 프로젝트의 품질 보장이 아니다.

### PostgreSQL 변경 절차 (B2)

현재 compose는 `postgres:17`이다. 먼저 분리된 PostgreSQL 17 테스트 인스턴스에서
확장 설치, 전체 migration, dump/restore를 확인한다. 같은 major의 pgvector 이미지
버전/digest와 데이터 경로를 확인해 고정한다. 개발 DB는 백업 후 같은 volume을
보존하며 교체하고, 볼륨 삭제/major 업그레이드를 하지 않는다.

Alembic은 확장 존재/권한을 preflight하고 테이블을 만든다. 확장 설치 권한이
없으면 명확한 오류와 별도 관리자 설치 절차를 제공한다. disposable-schema 테스트는
확장을 테스트 DB의 공용 스키마에서 한 번 설치하고 schema search_path를 보완한다.
downgrade는 이번 테이블만 제거하며 다른 자료가 쓸 수 있는 확장을 삭제하지 않는다.
구조 변경과 새 의존성의 이유는 실제 도입 시 DECISIONS에 남긴다.

## 3. 권한과 전송 대상

### 세 가지 허용을 구분

1. 현재 Codex의 개발·검증용 자료 읽기: 기존 허용 범위를 유지한다.
2. 앱의 외부 AI 전송: 기존 SourcePolicy와 Entry의 `external_ai_allowed`가 모두
   true인 해당 소유자의 현재 자료만 허용한다. 정책 미존재는 deny로 처리한다.
3. 유료 실험 실행: 대상 manifest·보수적 비용·전송 문구를 보여준 뒤 명시적
   실행으로 시작한다. 계획 작성/일반 개발 지시는 실제 유료 호출로 해석하지 않는다.

B1의 dry-run은 비밀번호를 터미널에서 입력받고 DB/owner를 바인딩한다. 선택한
provider/scope와 명시적 Entry allowlist를 사용해 gold를 포함한 자료와 distractor를
구성한다. 기본 실험 범위는 현재 pilot의 GitHub 저장소이고, 최종 전송 대상은
현재 AI 허용 기록으로 제한한다. 임의의 개인 기록을 허용 상태로 바꾸지 않는다.
허용 기록이 없으면 후보 수·차단 사유만 보여주고 유료 호출 없이 종료한다.
필요한 실제 권한 변경은 기존 Sources/record 설정을 사용하며 암묵적으로 수행하지 않는다.

기본 입력은 `field=content`, `work_only=false`인 3.2A 문단의 정확한 text다.
초기 B1은 NOTE/DOCUMENT/CONVERSATION만 선택해 GitHub commit diff/LOG를 제외한다.
제목, annotation, 원본 ZIP/JSONL, payload, reasoning, 전체 command/diff 로그는 보내지 않는다.
현재 버전·문단/원문 hash·offset·projection version을 전송 직전에 재검증한다.
부분 인덱스는 유효한 문단만 사용하고 누락 상태를 보고한다. source-deleted는 제외한다.
같은 owner/model/config의 동일 text는 중복 계산할 수 있지만 매 의존성의 현재 권한을
독립적으로 확인한다. 소유자 간 벡터 공유는 하지 않는다.

### 기존 AI 경계의 필요한 보완

`ai_policy.send_external_ai()`는 현재 전체 version title/content를 transport로 넘긴다.
임베딩 구현이 이 호출을 그대로 쓰면 문단 한도 밖 자료가 전송될 수 있다.
같은 모듈에 목적이 embedding으로 고정된 문단 전용 context/gate를 추가한다.
기존 호출의 동작은 보존하고, 새 transport는 검증된 문단 text 목록만 받는다.

DB read-committed transaction에서 기존 owner advisory lock을 잡고 최신 상태를
읽으며, 전송이 끝날 때까지 lock을 유지한다. 전송과 권한 철회의 순서는 이 lock으로
정한다. 먼저 시작한 전송은 최대 요청 제한 시간 안에 끝나고 이후 deny가 적용된다.
동일 owner의 여러 전송과 쓰기는 같은 lock 순서를 따른다. 요청 최대 10초 동안
동일 owner의 쓰기가 대기할 수 있다. provider 전송 동시성은 1개 상한으로 제한하고
DB pool 획득에도 고정 timeout을 적용한다. DB pool 자체를 1개로 축소하지 않는다.
권한 변경의 lock timeout은 재시도 가능한 busy 상태로 표시한다. 전송 전/후의 작업
선점·예약·발행은 짧은 별도 transaction으로 처리하지만, 최종 권한 확인부터 HTTP
완료까지의 전송 구간은 잠금을 해제하지 않는다. 테스트는 ① 전송 중 변경이 대기하고
전송 종료 후 적용되는 순서와 ② 전송 완료·잠금 해제 후 발행 전에 변경되어 결과를
폐기하는 순서를 분리한다. 변경 가능한 상태를 오래된 repeatable-read
평가 snapshot에서 재검증하지 않는다.

검색 질문의 임베딩은 source-version 목록이 없는 별도 query gate다. 질문 자체도
외부로 전송된다는 안내와 사용자 동의가 필요하다. 로그인만으로 허용하지 않는다.
POST body로 query를 받으며 source 본문을 query API에 덧붙이지 않는다.
API key는 서버 환경 변수/secret에만 둔다. origin은 `https://api.openai.com`으로 고정하고
redirect와 암묵적 환경 proxy를 비활성화한다. 키·본문·질문·벡터·원격 오류 원문은
로그/공개 보고서/검토 도구로 보내지 않는다. reviewer에는 이 계획만 제공한다.

## 4. 비용과 요청 제한

아래 금액은 구현 기본 제안이며 실제 유료 호출의 승인으로 사용하지 않는다.

| 항목 | 초기 제한 |
| --- | --- |
| B1 실행 전체 | USD 0.25, 문서와 질문 및 모든 시도 포함; 전체 300초 제한 |
| 임베딩 월 한도 | USD 1.00, 같은 앱 API 프로젝트의 모든 owner 합산 |
| 문서 batch | 최대 16개 입력, UTF-8 바이트 상한 합계 16,000 |
| 단일 입력 | 8,000 바이트 상한; 초과는 전송하지 않고 gap 표시 |
| 질문 | 기존 256자 제한 + 2,048바이트 상한 |
| provider 호출 | connect 2초, 전체 wall-clock 10초, 원격 응답 최대 2MiB |
| 동시 호출 | 앱 API 프로젝트에 1개; 대기는 제한 후 busy 응답 |
| 자동 HTTP 재시도 | 0; timeout/429는 별도 재실행 판단 |

USD 20 전체 예산과 ROADMAP의 AI 제안 봉투 USD 3 안에서 임베딩 USD 1을 배정한다.
호스팅/답변 생성 예산은 따로 남겨야 하며 이 설정이 실제 전체 비용 검증을 대신하지 않는다.
예: 입력 100만 토큰이면 현재 가격 기준 USD 0.02이며 질문/재시도 비용이 추가된다.

`AiUsageAttempt` 테이블을 B1부터 migration으로 추가한다. billing scope, UTC month,
owner, run/job ID, purpose/model/config, 입력 상한, 예약 금액, 실제 usage, 상태,
고정 error code를 보관한다. 금액은 정수 micro-USD로 올림해 계산한다.
레코드가 없는 월초에도 동작하는 billing scope별 고정 namespace의 transaction
advisory lock을 사용한다. scope 식별자는 고정 digest로 만들며 Python의 가변 hash를
쓰지 않는다. 월 단위로 lock을 분리하지 않고 해당 scope의 모든 월 예약/정산을
직렬화해 carry-over exposure까지 함께 보호한다. 집계 `SUM ... FOR UPDATE`나 기존
attempt 행의 존재에 의존하지 않는다. spent+reserved+uncertain을 확인하고 예약을
별도 transaction에서 commit한 뒤에만 원격 전송한다. worker와 API가 모두 같은
ledger를 사용한다. 월 한도가 0이거나 provider가 비활성이면 외부 호출 0건이다.

성공 응답은 입력 개수/index·모델·차원·유한 숫자·nonzero vector·usage 상한을 검증한다.
확실한 미전송 실패만 예약을 반환한다. 전송 시작 후 timeout/프로세스 종료/잘못된
응답은 uncertain으로 최대 예약을 유지한다. 성공했지만 publication이 실패한 경우도
비용을 지우지 않는다. 다음 달로 넘어가도 미확정 예약은 별도 outstanding exposure로
새 월 한도에서 차감해 자동 리셋으로 무료 취급하지 않는다. 실행 상한도 별도로 검사한다.
원격 결제 시스템의 모든 과금을 앱이 정확히 통제한다고 약속하지 않는다.

미확정 비용은 인증된 reconciliation CLI에서 확인한다. billing scope의 기존 시도와
전송 종료 여부를 확인한 뒤, provider 사용량 근거로 spent 정산하거나 보수적으로
예약 최대액을 spent로 확정할 수 있다. 사용량 불명 상태를 단순 TTL로 지우지 않는다.
정산 금액은 원래 예약 UTC month와 run에 귀속하고, 확정 후 다음 달의 outstanding
exposure에서 빠진다. 미전송/미청구가 확인된 경우만 예약 반환을 허용한다.
수동 정산도 같은 advisory lock 아래 변경 사유·시각을 기록하며 원문/키를 기록하지 않는다.
uncertain 조회/최대액 정산/다중 프로세스 월초 예약/월 경계 정산을 테스트한다.

## 5. B1 — 비교 실험

### CLI 흐름 (신규 제안)

`scripts/check_semantic_retrieval.py --email ... --set ... --dry-run`:
인증 → immutable pilot revision 확인 → 현재 허용 corpus 선정 → metadata-only manifest,
예상 입력 상한/금액, 제외/누락 상태 출력. 키가 없어도 dry-run은 동작한다.

`--run --manifest ... --max-cost-usd 0.25`:
로컬 인증/확인 → corpus/policy/model/config 재검증 → 문단 batch 전송 → query 전송 →
lexical/vector/hybrid 비교 → 원문 없는 private 보고서 저장. 변경된 manifest는 그대로
실행하지 않고 dry-run 갱신을 요구한다. 허용된 기록만 골라 전송한다고 명시한다.

질문은 승인된 natural question만 기본 사용한다. 보조 keyword 평가는 독립 실행하며
질문과 정답/claim을 provider에 함께 보내지 않는다. 정답 근거는 로컬 채점에만 쓴다.

### 공정한 비교와 채점

- 허용 corpus로 새 lexical baseline을 측정해 같은 corpus의 vector/hybrid와 비교한다.
  전체 local corpus의 기존 1/3 결과는 별도 참고값이다. 같은 결과처럼 직접 비교하지 않는다.
- 승인된 gold 외에 최소 20개 distinct non-gold 문단 group을 포함한 distractor와
  제외 수를 manifest에 기록한다. corpus가 이 조건을 충족하지 못하면 탐색 확인으로
  표시하고 B2 통과 근거로 사용하지 않는다. gold만
  임베딩한 실험은 탐색 확인이며 모델 선택의 통과 근거로 사용하지 않는다.
- 원래 gold가 정책/현재 버전/입력 제한 때문에 빠진 case는 excluded/invalid로
  드러내고 분모·실패 사유를 유지한다. AI 허용 case 점수와 전체 case 접근 가능성을 분리한다.
- 같은 corpus/version/policy/config snapshot에서 3방법을 채점한다. 전송 이후 snapshot을
  새로 열어 manifest 동일성을 확인한다. 실행 중 자료가 변하면 비용만 보존하고 품질
  비교를 invalidated로 처리한다. gold가 query/ranking을 바꾸지 않게 한다.
- 동일 GitHub 문단은 3.2A의 검증된 group identity로 묶는다. 완전한 같은 버전/field
  gold 구간을 top-K에서 덮어야 성공이며 카드의 alias preview 상한과 채점은 독립이다.
- 보고서: recall@5/10/20, all-groups@20, MRR@20, 언어별 case 결과, 지연 시간,
  입력량·예약/실제/미확정 비용, corpus coverage, 모델/config digest. 기존 body-free 형식을 유지한다.

### 사전 고정한 B2 진행 기준

기능/권한/삭제/예산 위반 0건을 먼저 요구한다. pilot 3문항이 동일 허용 corpus에서
유효하게 측정되는 경우, 실패했던 한국어 2문항 중 적어도 1개를 complete gold top20으로
회복하고, 기존 영어 성공 case를 유지해야 한다. synthetic test는 tooling 검증만 한다.
pilot gold가 허용되지 않으면 실제 품질 판단을 완료했다고 표시하지 않는다.
기준 통과 후에도 광범위한 recall 0.80/all-groups 0.70 목표는 다양한 승인 평가 세트에서
별도로 검증한다. 모델을 바꿀 때는 예산/새 manifest와 별도 실험이 필요하다.

## 6. B2 — 저장과 재개 가능한 작업

`PassageEmbedding`: passage FK/CASCADE, model/dimensions/input config, text hash,
vector(1536), created_at. unique(passage_id, model, config). 원문을 복제하지 않는다.
동일 본문 여러 snapshot의 비용 중복을 줄이려면 현재 허용된 같은 owner의 ready
벡터를 복사한다. 각 복사본은 독립 passage FK를 가져 revoke/delete를 독립 처리한다.

`EmbeddingJob`: owner, passage/version/hash/projection/model/config, captured policy revision,
pending/running/ready/blocked/stale/failed/uncertain, lease/attempt ID, 오류 code.
job은 원문 대신 식별자만 가진다. passage가 사라져도 실행 시도/비용 기록은 유지하고
job은 stale 처리한다. owner별 상태 GET과 인증된 재색인 POST를 제공한다.
초기 운영은 로컬 PostgreSQL durable queue와 별도 `app.workers.embedding_worker`다.
기존 import worker를 독립 유지하고 AWS/SQS 구현은 도입하지 않는다.

- create/update/reimport/version select: 기존 문단 갱신 transaction에서 구 벡터 제거,
  현재 유효·허용 문단의 job 등록. write 요청에서는 provider를 호출하지 않는다.
- lifhop delete: 벡터 cascade, 미완료 job stale. retained source version을 재검색하지 않는다.
- source/Entry deny, confirmed source deletion: 같은 owner lock/transaction에서 관련
  벡터 제거·pending job 차단. 조회도 최신 정책을 조인해 정리 지연에 의존하지 않는다.
- allow/reimport/restore: 현재 유효한 문단만 새 작업을 만든다. 이전 실행 결과를 자동
  재공개하지 않는다. source allow가 Entry deny를 덮어쓰지 않는다.
- consumer: owner-before-job lock, 최신 내용/권한 재검증, durable 비용 예약과
  전송 의도 기록, 문단 gate 전송, 응답 검증, publish 직전 revision/hash/current 재검증.
  stale 결과는 버리고 비용 기록을 남긴다. 전송/commit 사이 interruption을 테스트한다.
- 오래된 running lease를 발견해도 전송 여부가 불확실하면 자동 재전송하지 않는다.
  미전송이 입증된 작업만 재개하며 uncertain은 사용자 재시도까지 대기한다.
- backfill CLI는 owner 인증, cursor/batch, dry-run 예상비용, 재실행 중복 억제를 제공한다.
  월/실행 한도 도달 시 pause하고 local lexical search를 계속 제공한다.

조회는 model/config/current hash와 최신 SourcePolicy+Entry AI 허용을 모두 검사한다.
global policy revision은 in-flight 작업 fence이며 unrelated 변경만으로 모든 ready
벡터를 무효화하는 조회 조건으로 사용하지 않는다. revoke→allow 사이 늦은 작업은
revision으로 막는다. vector는 민감한 파생 자료로 취급한다.

## 7. B2 — 검색 API와 화면

기존 Exact phrase/Passages GET은 유지한다. 새 `POST /passages/retrieve`는
`retriever=semantic|hybrid`, query, 기존 filters, limit/offset과
`confirm_external_ai: bool = false`를 명시적 schema로 받는다. backend query gate는
필드가 true가 아니면 403으로 거부하고 provider 호출/비용 예약을 하지 않는다.
브라우저에서는 Semantic/Hybrid 선택 시 질문 전송 안내와 session 범위 명시적 동의를
받는다. 동의 필드는 POST에만 전달하며 URL/returnTo/cache key에서 동의를 복원하지
않는다. session 동의는 로그아웃/계정 변경 때 해제한다. 첫 진입·빈 질문·URL
새로고침은 유료 검색을 자동 실행하지 않는다. B1도 dry-run manifest에 질문 전송을
명시하고 run 확인을 받는다. 동의 없는 임의 API 클라이언트를 직접 테스트한다.

Semantic은 현재 허용된 ready 벡터의 exact cosine rank, Hybrid는 같은 필터의 local
lexical 후보 100개와 semantic 후보 100개를 RRF(k=60, 동률 고정 순서)로 합친다.
각 lane은 정확한 group을 먼저 묶고 Entry당 대표 2개를 적용한 뒤 후보 한도를 적용한다.
hybrid 결과에서 AI-denied 기록은 lexical lane으로만 나타날 수 있다. 전송 여부와
local/semantic 경로를 metadata로 구분하며 그 본문을 query API에 보내지 않는다.

최신 owner/source/date/type/현재 버전/정책 조건을 vector limit 전에 적용한다.
전체 corpus의 벡터를 애플리케이션 메모리로 가져와 owner를 사후 필터링하지 않는다.
RRF 뒤에도 group/Entry quota를 재적용하고 최대 20개씩 보여준다. 전체 검색의 total을
약속하지 않고 bounded candidate total/상한 표시를 사용한다. B1도 같은 candidate
알고리즘을 사용해 B2 점수와 비교 가능하게 한다.

문단 reader는 기존 화면을 재사용한다. retained locations는 검색 lane/filter를
유지하고 semantic alias에 lexical query 일치 조건을 잘못 요구하지 않는다.
semantic alias는 현재 AI 허용 상태를, local alias는 local 조건을 따르며 lane의 union
group에 속한 위치만 표시한다. aliases 조회는 query를 재임베딩하지 않는다.

ready 벡터가 0개면 query를 외부로 보내지 않는다. Semantic은 indexing/unavailable
상태를, Hybrid는 명시적 local-only 상태를 보여준다. query embedding은 실행마다
예약/기록한다. 초기 구현에서는 query vector를 영속
저장하지 않으며 pagination 재요청도 소액 호출이 될 수 있음을 안내한다. return은
TanStack cache를 사용하고 cache가 없으면 Search 버튼을 누르도록 한다.
query embedding 이후 DB read는 3.2A의 shared lock/5초 deadline을 재사용한다.
전체 endpoint 시한 15초, 응답 1MiB, timeout/busy/budget/indexing/provider-disabled를
구분한다. hybrid 원격 실패 시 local 결과만 반환하면 degraded 표시를 필수로 하고
평가에서는 hybrid 성공으로 집계하지 않는다. similarity는 정답 확률로 표시하지 않는다.

## 8. 구현 순서·검증·커밋

1. **B1 경계/비용**: 설정 off 기본, 문단/query gate, usage migration/예약, transport.
   mocked provider로 권한·동시 예약·월 경계·취소·timeout·malformed 응답 검증.
2. **B1 비교 CLI**: dry-run/manifest, 메모리 벡터, 동일 corpus lexical/vector/hybrid,
   body-free 보고서. 기존 339 backend/110 frontend 기준 회귀 확인.
3. **B1 실제 실행**: 합성 검증 후 허용 대상/질문/예상 비용/API key 준비 여부를
   구체적으로 안내하고 제한된 실제 호출. 결과·실패·비용을 보여주고 B2 진행 확인.
4. **B2 DB/worker**: pgvector migration·isolated restore, durable jobs·publication fence,
   삭제/권한 변경·worker crash/중복/재개·입력 제한·모델 변경 검증.
5. **B2 API/UI**: filters/group/quotas, owner isolation, 원문/return/aliases, 설정 off와
   denied-only/partial corpus, busy/timeout/budget, 390/768/1440px 검증.
6. **B2 평가/사용자 확인**: 같은 frozen revision에서 실제 비교, 남은 다국어/다양한
   출처 평가 한계 보고, CURRENT/DECISIONS 갱신. 완료 전에 diff/전체 tests/lint/build 확인.

독립 커밋은 B1 경계/비용 → B1 평가 실험 → B2 DB/작업 → B2 API/UI 순으로 제안한다.
계획은 별도 docs 커밋이 가능하다. 이번 요청에서는 계획만 작성하며 커밋하지 않는다.

검증 필수 실패 사례: owner 교차 요청, missing/deny policy, scope/Entry deny,
전송 직전 revoke, 전송 중 edit/delete, revoke→allow stale completion, 원문 밖 입력,
단어가 겹치지 않는 semantic aliases, 그룹별 일부 snapshot deny, old/current config,
query consent 없음, 다중 프로세스 예산 초과, uncertain 비용/중복 송신, 월 경계,
provider redirect/오류 본문 유출, NaN/zero vector, invalid usage, API off 외부 호출 0건.
자동 테스트는 external transport를 기본 차단하고 fake fixture만 사용한다.

## 9. 완료 시 사용자가 확인할 내용

B1에서는 서버/worker 추가 실행 없이 로컬 인증 후 제한된 CLI를 사용한다.
최종 브리핑에서 실제 실행 명령, allow 범위, 질문 전송 여부, 가격/상한과 결과 표를
여기에 직접 안내한다. 원문 근거를 다시 찾아오도록 요구하지 않는다.

B2에서는 migration과 worker 필요 여부/실행 명령을 직접 안내한 뒤:

1. `/search` → Hybrid → 질문 전송 동의 → 준비된 한국어 질문 검색.
2. 결과 View passage에서 영문 원문 근거 확인, 검색 화면으로 복귀.
3. AI 허용 테스트 노트 생성/수정 → indexing 표시 후 새 내용이 검색됨.
4. 삭제 또는 AI 허용 철회 → semantic 결과에서 즉시 제외됨.
5. AI-denied 기록은 Passages로 계속 검색·읽을 수 있고 provider 전송은 0건.
6. 사용량/예산 소진·provider 비활성 상태와 local 검색의 계속 동작 확인.

## 10. 근거와 검토 기록

- [OpenAI small 모델/가격](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- [OpenAI embeddings guide/차원](https://developers.openai.com/api/docs/guides/embeddings)
- [OpenAI embeddings API/입력 제한](https://developers.openai.com/api/reference/resources/embeddings/methods/create)
- [pgvector 공식 README/거리·정확 검색·PostgreSQL 이미지](https://github.com/pgvector/pgvector)

기존 코드 연결점: `ai_policy.py`, `source_history.py`, `api/entries.py`, `api/sources.py`,
`passage_index.py`, `passage_search.py`, `passage_budget.py`, `evaluation/*`와 Search UI.
Antigravity compact 계획 검토 1회 완료. 개인 corpus/질문/정답은 reviewer에게
제공하지 않았다. 지적 3건, 수용 2건, 제안 반려 1건, 사용자 판단 필요 0건:

- high 수용: API schema의 전송 동의 필드와 backend gate/직접 API 테스트를 명시했다.
- high 수용: 월초 레코드 유무와 무관한 budget advisory lock, 월 경계 exposure,
  미확정 비용의 인증된 조회/정산 절차를 명시했다.
- high 제안 반려: HTTP 중 owner lock 해제는 확인→전송 사이 revoke 경합을 허용해
  기존 AI 경계의 계약을 약화한다. 잠금을 유지하고 최대 대기/사용자 busy 표시와
  전송 중 직렬화 테스트, 전송 후 발행 전 변경 테스트를 구분했다.

추가 자체 확인으로 벡터 메모리 구성, provider origin/redirect, 실제 실험의 최소
distractor 수, ready 벡터가 없는 경우의 호출 0건을 명시했다. 검토에서는 계획만
수정했으며 코드·DB·권한·외부 AI 실행은 변경하지 않았다.
