# Phase 2.3 — Codex CLI 과거 기록 수집 구현 계획

작성일: 2026-10-03
상태: Antigravity 2회 검토 후 A–D 구현 및 로컬 검증 완료. 사용자 미리보기 확인 완료,
구현 커밋 승인. 개인 기록 적용/실제 기록 화면 검증 대기.
기준 커밋: `19e395a`. 실제 개인 기록의 저장·업로드는 아직 수행하지 않았다.

## 1. 목표와 완료 조건

Mac에 남아 있는 선택한 Codex 과거 기록을 lifhop에서 검색하고 확인한다.

- 과거 질문과 답변, 실행된 명령과 기록된 결과, 기록된 코드 diff를 찾는다.
- 각 기록에 원래 thread/turn/item ID, 출처 시각, 관측 시각, 누락 이유가 남는다.
- 읽기·변환·전송 중 종료해도 이미 저장된 결과는 유지되고 재개할 수 있다.
- 같은 입력을 반복해도 Entry·Version·메시지가 중복되지 않는다.
- lifhop 삭제, 수집 중지, AI 제외, 개인 주석을 재수집이 무효화하지 않는다.
- 원본 Codex 기록은 수정하지 않고, 제외한 본문은 서버로 보내지 않는다.

이번 범위는 수동 과거 수집과 재개, 결과 확인이다. GitHub는 2.4,
주기적 수집·브라우저 collect-now 연동은 Phase 4에서 구현한다.
새 AWS 서비스·외부 AI 호출·새 큐를 도입하지 않는다.

## 2. 확인한 기존 구조

| 기존 파일 | 재사용할 기능 / 필요한 보완 |
| --- | --- |
| `app/acquisition/codex.py` | 목록 조사, 임시 복사본, 읽기 전용 app-server RPC. 현재 두 파일·한 샘플 위주이며 페이지를 전부 메모리에 모은다. |
| `app/acquisition/common.py` | 비공개 로컬 보고서와 HTML escaping. 8,000자 미리보기 제한·단순 비밀정보 치환만으로 실제 수집을 처리하지 않는다. |
| `app/api/captures.py` | `POST /captures/snapshots`와 공통 저장 계약. 새 수집 API도 같은 저장 서비스를 사용한다. |
| `app/importers/canonical.py` | `DevSessionPayload`, 역할·명령 결과·diff 모델. 순서·출처·누락 정보를 추가한다. |
| `app/services/external_entries.py` | 안정된 ID로 upsert, 버전 보존, 최신성·완전성 검사. |
| `app/services/source_history.py` | 소유자 잠금, 수집 정책, 삭제 차단, AI 기본 거부. |
| `frontend/src/pages/SourcesPage.tsx` | 정책·삭제 관리. 수집 실행 결과와 신선도 표시를 추가한다. |
| `frontend/src/components/EntryHistory.tsx` | 주석·버전·구조화 증거 표시. Codex의 누락 안내를 읽기 쉽게 표시한다. |

설치 CLI는 `codex-cli 0.158.0`을 확인했다. 기존 검증도 이 버전에 한정된다.
실제 구현 시작 시 설치 버전과 생성 스키마를 다시 확인한다.
공식 app-server의 `thread/read`, `thread/turns/list`, `thread/items/list`는
저장 기록을 읽는 인터페이스다. 뒤의 두 방식은 experimental이므로
지원 여부를 확인하고, 지원하지 않는 포맷은 실패 이유를 남긴다.
참고: [공식 app-server 문서](https://learn.chatgpt.com/docs/app-server).

## 3. 사용자가 수행할 흐름

아래 명령 인터페이스는 구현되었다. 실제 사용·제외 설정·재개 안내는
`CODEX_BACKFILL.md`를 참고한다.

```bash
# 최초 한 번: 랜덤 device UUID와 기본 제외 설정을 생성한다.
.venv/bin/python -m app.collectors.codex init-config \
  --config .local/codex-collector.json

# 1. 읽기·필터링·변환과 로컬 미리보기. API/DB 접속 없음.
.venv/bin/python -m app.collectors.codex preview \
  --include-cwd /path/to/project --config .local/codex-collector.json

# 2. 생성된 HTML/manifest의 대상·본문·누락·제외 설정 확인.
# 필요한 경우 config를 고치고 preview를 다시 실행한다.

# 3. 확인한 미리보기의 고정된 데이터만 저장. 비밀번호는 숨김 입력.
.venv/bin/python -m app.collectors.codex apply \
  --run-dir .local/collections/codex/RUN_ID \
  --api-url http://localhost:8000 --email a@test.com

# 4. 같은 명령으로 중단된 실행을 재개한다.
```

- 프로젝트 범위를 여러 번 지정하거나 `--all-accessible`을 명시한다.
  기본값으로 현재 프로젝트만 선택하거나 전체 기록을 자동 업로드하지 않는다.
- 활성/보관 디렉터리를 모두 조사한다. 제외 thread·cwd·기간·item 유형을 지원한다.
- preview 결과는 선택 목록, 읽기 성공/실패, 업로드 예정 turn 수,
  실제 저장할 본문, 생략·치환·제한 이유를 보여준다.
- apply는 원본을 다시 읽지 않는다. 검토한 로컬 manifest와 sanitized payload를
  해시로 고정하고 변경되었으면 새 preview를 요구한다.
- 브라우저 Sources에서 결과를 확인하고 Search의 Source=Codex로 찾는다.
- Mac에서 CLI는 수동 실행 중에만 동작한다. 실행하지 않으면 새 기록을 발견하지 않는다.

## 4. 저장 단위와 식별자

**한 turn을 한 Entry로 저장한다.** 한 번의 사용자 요청과 그에 따른 메시지·명령·변경을
함께 읽을 수 있고, 긴 thread 전체를 매번 재전송하거나 덮어쓰는 비용을 줄인다.

- `provider=codex`, `type=PROJECT_EVENT`, `payload.kind=dev_session`.
- `source_scope=mac:<device UUID>`: 로컬 설정에 한 번 생성하고 계속 재사용한다.
  `init-config`가 UUIDv4를 `.local/codex-collector.json`에 0600으로 생성한다.
  기존 파일은 덮어쓰지 않으며 preview/apply가 UUID를 자동 재생성하지 않는다.
  누락·잘못된 UUID 또는 manifest와 다른 config UUID는 실행을 거부한다.
  Mac 이전/재설치 시 config를 함께 복원한다. config를 잃었으면 인증된 Sources의
  기존 scope를 명시 선택해 복구하며, 새 UUID로 기존 기록을 재수집하지 않도록 안내한다.
- `external_id=<device UUID>:<thread ID>:<turn ID>`.
  ID 길이·형식을 검증하며 초과 시 `<device UUID>:sha256:<thread/turn 쌍의 해시>`로
  줄여 기기 접두사를 유지하고 원래 ID를 evidence에 보존한다.
  새 수집 item schema에서 scope UUID와 external_id의 device 접두사가 일치하는지 검증한다.
  기존 `/captures/snapshots`의 Codex/default payload 계약은 유지한다.
- resumed 세션은 같은 thread/turn ID를 재사용한다. fork는 별도 thread ID로 저장하고
  `forked_from_id`를 알 수 있으면 남긴다. 다른 thread의 동일 문장은 별개의 출처이며
  텍스트 유사도만으로 합치지 않는다.
- 사용자 메시지 `message_id`와 명령·diff `item_id`를 그대로 유지한다.
  한 item에 여러 파일 변경이 있으면 item ID와 경로를 함께 식별한다.
- `DevSessionPayload`에 선택적 thread/turn 메타데이터, 순서 참조 목록,
  누락 코드·개수·truncation, 읽기 방식과 필터 버전을 추가한다.
  기존 payload는 기본값으로 호환한다. 변동하는 실행 ID/관측 시각은 payload 해시에 넣지 않는다.
- 제목은 비밀정보 처리한 첫 사용자 질문 또는 안전한 fallback으로 만들고 255자 이내로 제한한다.
- `event_at`은 알려진 turn 시작 시각이다. 모르면 null이며 thread 생성 시각을 대신 넣지 않는다.
- `source_updated_at`은 검증 가능한 원본 turn 수정/완료 시각을 사용한다.
  turn에 시각이 없으면 null이다. 수집 시각이나 파일 mtime을 원본 수정 시각으로 위장하지 않는다.
- 전체 페이지를 읽고 필수 항목을 보존한 입력은 complete, 읽기·출력 제한 등
  빠진 부분이 있으면 partial, 근거를 판단할 수 없으면 unknown으로 표시한다.
  complete는 선택한 수집 범위의 읽기 완료이며 과거 전체가 원래부터 완전했다는 뜻이 아니다.
- 시각이 불명확한 changed turn은 기존 최신성 규칙대로 버전을 보존하고 review_required로 표시한다.

## 5. 원본 읽기와 자원 제한

1. 원본은 `sessions`, `archived_sessions`의 metadata와 필요한 history DB만 읽는다.
   심볼릭 링크와 경로 탈출을 거부하고 원본 파일을 쓰기 모드로 열지 않는다.
2. 선택 rollout을 순차적으로 임시 디렉터리에 복사하고 전후 SHA-256/크기를 비교한다.
   변경 중이면 bounded 재시도 후 deferred 처리한다. 다른 세션 수집은 계속한다.
3. paginated history DB는 read-only SQLite backup으로 복사한다.
   rollout과 DB가 원자적으로 복사되지 않는 한계를 명시하고 불일치를 감지한 세션은
   complete로 인정하지 않는다. 실행 중 세션은 과거 backfill에서 기본 deferred 처리한다.
   검증된 포맷에 한정된 verification reader가 rollout의 thread/turn/item ID 집합,
   순서와 turn별 item 수를 추출하고, 복사한 projection DB의 대응 식별자/수 및
   app-server 반환 결과와 대조한다. 텍스트는 이 reader로 수집하지 않는다.
   예를 들어 원본에 4 item, DB/API에 3 item이면 `SNAPSHOT_DIVERGENCE`로 partial이다.
   원본 포맷에 비교할 ID/수가 없거나 DB 검증 스키마가 지원되지 않으면
   `SNAPSHOT_CONSISTENCY_UNKNOWN`으로 complete를 주장하지 않는다.
   DB/rollout 검증 reader는 CLI/기록 포맷별 테스트와 실제 샘플로 검증하며,
   official API가 못 읽는 내용을 자체 파서로 채워 넣는 대체 수집 경로로 사용하지 않는다.
4. app-server는 복사본 `CODEX_HOME`에서만 시작한다. 원본 auth/config/state DB는 복사하지 않는다.
   자식 환경은 최소 allowlist로 구성해 AWS/OpenAI/DB/GitHub 토큰을 넘기지 않는다.
   analytics/telemetry를 끄고 initialize 및 읽기 RPC만 허용한다.
   기존 `ReadOnlyAppServer`의 `os.environ.copy()`를 명시 allowlist 생성으로 교체한다.
   PATH/HOME/TMPDIR/LANG/LC_ALL 중 필요한 값과 임시 CODEX_HOME만 전달하고,
   acquisition probe에도 같은 격리를 적용해 기존 읽기 검증을 유지한다.
5. paginated 세션은 turn/page iterator로 읽는다. 큰 turn은 지원되는 경우
   `thread/items/list`로 나눈다. legacy `includeTurns`가 한도를 넘거나 실제 내용이
   반환되지 않으면 명시적 gap으로 처리한다. 미검증 JSONL 파서로 조용히 전환하지 않는다.
6. active/archived 양쪽 inventory와 실제 읽기 결과를 대조한다.
   같은 thread ID가 여러 원본에 있고 내용이 다르면 충돌로 표시하고 임의 선택하지 않는다.

초기 제안 한도: rollout 파일 64 MiB, DB 복사 256 MiB, RPC 응답 16 MiB,
개별 텍스트 64 KiB, 정제된 turn 1 MiB, preview 전체 512 MiB,
임시 복사본 2 GiB, RPC 20초, 실행 30분, thread당 1,000페이지.
UTF-8 바이트 단위로 측정하며 실제 inventory/검증으로 조정한다.
필드 초과는 명시적 truncation, RPC·총량·시간 초과는 gap/deferred로 표시한다.
한도를 맞추기 위해 내용을 몰래 버리거나 전체 기록을 메모리에 모으지 않는다.
실패 시 app-server 종료와 임시 원본 복사본 정리를 보장한다.

## 6. 업로드 전 제외와 개인 데이터 보호

- config는 include cwd/기간/thread, exclude cwd/thread, 출력·diff 제한,
  프로젝트 경로 표시 정책을 포함한다. 제외는 선택보다 우선한다.
- 인증파일·`.env`·개인 키·환경 덤프·바이너리/이미지·reasoning·미지원 tool payload는 제외한다.
  captured command를 실행하거나 diff 경로의 실제 파일을 열지 않는다.
- 메시지·명령·출력·diff·제목·경로를 모두 정제한다. 알려진 credential 패턴은 치환하고,
  환경/인증파일 덤프를 읽는 명령과 출력은 보수적으로 제외한다.
- 경로는 프로젝트 상대 경로/사용자 지정 별칭으로 표현한다. 원본 절대 경로와 cwd는
  기본적으로 로컬 manifest에만 남기고 서버 locator에는 안전한 Codex ID 표현을 사용한다.
- 불완전한 secret 탐지를 전제로 실제 전송 예정 본문을 로컬에서 확인하게 한다.
  원본 raw JSONL/SQLite, 미리보기 원본이나 제외된 본문은 S3·서버·리뷰어에 보내지 않는다.
- 서버에는 sanitized canonical payload를 PostgreSQL EntryVersion으로 보관한다.
  정확한 원본 다운로드 링크를 만들지 않으며 `sanitized_capture`로 표시한다.
- 로컬 결과는 `.local/collections/` 아래 0700 디렉터리·0600 파일에 두고 Git에서 제외한다.
  임시 원본은 즉시 정리하고 정제 결과도 `cleanup` 명령으로 삭제할 수 있게 한다.
- CLI 로그인 비밀번호는 getpass, 토큰은 실행 메모리에만 둔다.
  localhost HTTP 또는 인증서 검증이 켜진 HTTPS만 허용하고 redirect를 거부한다.
- 업로드 전 서버의 수집 정책·삭제 차단을 조회하고, 서버도 소유자 잠금 안에서
  저장 직전에 검사한다. 조회 후 이미 출발한 요청을 되돌릴 수 없는 한계는 명시한다.
  collection 중지는 저장도 차단하고 AI 권한은 기존대로 기본 false다.

## 7. 내구성 있는 수집 실행과 API

ZIP ImportJob은 artifact가 필수이며 별도 worker 실행을 전제한다.
이번에는 Mac이 읽은 sanitized turn을 직접 전송하므로 ImportJob/큐를 억지로 확장하지 않는다.
공통 upsert를 재사용하는 작은 CollectionRun/CollectionRunItem 모델과 migration을 추가한다.

| 모델 | 저장할 최소 정보 |
| --- | --- |
| CollectionRun | user_id, provider, scope, client_run_uuid, manifest_digest, parser/filter version, 상태, 시작/최근 접속/종료 시각, 본문 없는 coverage 요약 |
| CollectionRunItem | run_id, external_id, sanitized payload digest, 결과(new/unchanged/updated/retained/blocked/failed), 안전한 error code. 본문·Entry ID의 영구 복제는 저장하지 않는다. |

- `(user_id, client_run_uuid)`와 `(run_id, external_id)`를 unique로 둔다.
  서버에서 owner/provider/scope를 확인한다. 같은 run ID로 다른 manifest를 보내면 409다.
- `POST /collection-runs`: run 생성/동일 manifest 재연결. 새 source policy를
  최초 정제 본문 전송 전에 등록하며 기존 수집 중지/AI 설정은 유지한다.
- `GET /collection-runs/{id}` 및 `GET /collection-runs?provider=codex`:
  소유자 범위의 실행 결과·진행·coverage·최근 접속을 조회한다. 결과 item은 페이지화한다.
- `GET /collection-runs/{id}/preflight?external_id=...`: 해당 source 정책·삭제 차단 확인.
  blocked ID나 query는 비공개 로그 본문에 남기지 않는다.
- `POST /collection-runs/{id}/outcomes`: 전송 전에 차단/실패한 항목은 identity와
  allowlist된 reason code만 보고한다. 정제 본문을 보낼 필요가 없으며 skipped/failed를
  durable 결과에 포함해 finish 시 아직 처리하지 않은 항목과 구별한다.
  동일 identity의 재보고는 idempotent다. 잘못된 payload를 결과 없이 누락하지 않는다.
  본문 없는 보고가 이미 성공한 ingest receipt를 덮어쓰지 못하게 한다.
  failed 항목의 재시도만 허용하고, 성공 항목은 같은 digest의 replay ACK로 처리한다.
- `POST /collection-runs/{id}/items`: 한 turn 입력. API는 2 MiB 이하 본문 제한,
  Pydantic 구조/항목 개수/필드 길이 검증, provider/scope 일치 검사를 한다.
  JSON 파싱 전에 본문 크기를 제한하고 client 한도만 신뢰하지 않는다.
- Entry/Version 변경과 item 결과를 같은 PostgreSQL transaction에서 commit한다.
  durable commit 후 ACK하며 run/item 잠금 순서는 기존 owner 정책 잠금 다음으로 통일한다.
- 공통 upsert에 `upsert_external_entry_with_outcome`을 추가해 Entry와 typed outcome을
  반환한다. 기존 `upsert_external_entry`는 이를 호출해 Entry만 반환하므로 기존
  Markdown/ZIP/Capture 호출 계약을 유지한다. 결과는 실제 upsert 분기에서 정한다:
  new=새 Entry, unchanged=기존 버전 replay, updated=새 버전의 current 승격,
  retained=새 후보 보존·current 유지. endpoint의 사후 추측으로 판정하지 않는다.
  정책/삭제 차단은 별도의 blocked 코드이며 신규와 갱신을 집계에서 구분한다.
- 저장 후 응답이 유실되면 동일 run/identity/digest를 다시 보내 안전하게 ACK를 받는다.
  같은 run에서 다른 payload digest가 오면 409로 새 preview를 요구한다.
- 성공 ACK를 받은 뒤 로컬 checkpoint를 임시 파일+atomic replace로 갱신한다.
  체크포인트는 API origin, 인증된 owner ID, device/scope, manifest/parser/filter digest에 묶는다.
  이를 위해 작은 인증된 `GET /auth/me`를 추가한다. 계정이 바뀌면 기존 checkpoint 재사용을 거부한다.
- 기존 삭제 후 cached ACK가 content를 복원하지 못하도록 ACK 재전송 때도 suppression을 검사한다.
  CollectionRunItem에는 정제 본문을 저장하지 않는다. 재수집에서 tombstone을 우회하지 않는다.
  삭제 단위는 기존 UI와 같은 개별 turn Entry다. 삭제된 turn은 같은 thread의 다른 turn과
  별개로 차단된다. thread 일괄 삭제 UI는 이번 계획에 포함하지 않는다.
- `POST /collection-runs/{id}/finish`: 서버의 durable item 수와 client inventory 요약을 대조한다.
  모든 선택 항목의 결과가 있어야 completed이며 gaps/failed/deferred가 있으면 partial이다.
  선택 대상 0개는 별도 empty 결과, 성공 0개와 오류만 있는 경우 failed로 표시한다.
- 네트워크 오류/429/503은 최대 3회 backoff·Retry-After 후 중단 가능 상태로 남긴다.
  401은 재로그인을 안내하고 checkpoint 유지, 403/409 정책·삭제 차단은 내용 재시도하지 않는다.
  unsupported format/invalid item은 안전한 코드로 보고하고 다른 항목을 진행한다.
- 마지막 ACK 이후의 active run이 오래됐으면 disconnected로 표시한다.
  서버가 Mac 상태를 추정해 성공 처리하지 않으며 재연결 시 같은 run을 계속한다.

## 8. 브라우저 결과와 읽기 화면

- Sources의 Codex scope에 최근 실행, 마지막 수집 시각/연결 시각,
  discovered/selected/read/ingested/unchanged/blocked/failed/deferred 수와 gap 코드를 표시한다.
- 마지막 실행 성공과 소스 전체 최신 여부를 분리한다. `Collector not running` 또는
  마지막 접속 시각을 보여주고, 잠든 Mac의 새 기록을 서버가 발견했다고 표현하지 않는다.
- Search Source=Codex와 Type=Project event는 기존 필터를 사용한다.
- DevSession normalizer는 JSON 문자열 전체 대신 순서대로 읽을 수 있는 텍스트를 만든다.
  user/assistant, command/result/exit, diff/path, omissions를 명확히 구분한다.
- 상세에서 command output, diff는 실행하지 않는 텍스트로 표시한다.
  구조화 증거는 기존 history 패널로 제공하고 누락·보관·fork 정보도 확인할 수 있게 한다.
- 사용자 주석, 버전 선택, English UI와 검색 복귀 경로를 유지한다.
  변경 schema는 OpenAPI/생성 TypeScript 타입에 반영한다.

## 9. 구현 순서와 커밋 경계

| 순서 | 작업 | 검증과 제안 커밋 |
| --- | --- | --- |
| A | turn 단위 canonical/evidence, 읽기 쉬운 normalizer, 테스트 fixtures | 호환성·역할·순서·결과·diff·unknown 검증. `feat: normalize Codex turns with ordered evidence` |
| B | Mac inventory/snapshot iterator, 선택·정제·고정된 preview bundle | 원본 불변·실행 RPC 금지·제외·한도·활성/보관·미지원 버전 검증. `feat: preview selected Codex history safely` |
| C | CollectionRun migration/API, owner 일치, commit+ACK, CLI apply/checkpoint | 실제 격리 PostgreSQL, 응답 유실·kill·삭제/중지 race·재개·replay 검증. `feat: ingest Codex backfill with durable checkpoints` |
| D | Sources 결과·detail 증거·사용자 가이드·실제 샘플 확인 | frontend tests/lint/build, 로컬 HTTP/CLI, owner 브라우저 확인. `feat: show Codex backfill coverage and evidence` |

각 커밋은 해당 검증 후 사용자 승인 시 생성한다. Phase 2.3 내부에서 순차 구현하며,
다음 product slice는 이 흐름을 사용자가 확인한 뒤 진행한다.

### 변경 파일의 예상 범위

- 수정: `app/importers/canonical.py`, `normalizer.py`,
  `app/services/external_entries.py`, `app/acquisition/codex.py`.
- 추가: `app/collectors/codex.py`와 필요 시 정제/HTTP/checkpoint 보조 모듈.
  책임 분리를 위한 최소 파일만 만들고 가상의 범용 collector framework를 만들지 않는다.
- 추가: `app/models/collection_run.py`, `app/schemas/collection_run.py`,
  `app/services/collection_runs.py`, `app/api/collection_runs.py`, Alembic migration.
  기존 model export와 `app/main.py` router 등록, `app/api/auth.py`의 `/me`를 보완한다.
- 수정: `app/upload_limits.py`의 해당 JSON route 제한, 필요한 설정 항목.
  기존 multipart/다른 API 한도에는 영향을 주지 않는다.
- 수정: Sources/EntryHistory와 필요한 DevSession reader, frontend API/생성 타입 및 테스트.
- 추가 테스트: `tests/test_codex_collector.py`, `tests/test_collection_runs.py`.
  기존 acquisition/normalizer/source-history regression 테스트도 함께 보완한다.
- 문서: 구현 후 `CURRENT.md`, `ACQUISITION.md`, 사용자 가이드와
  `DECISIONS.md`에 turn 단위·sanitized 저장·durable receipt 결정을 기록한다.

## 10. 검증 계획

### 자동화

- 기존 acquisition/canonical/source-history tests를 유지하고 새 collector/API tests를 추가한다.
- 분리된 실제 PostgreSQL에 migration upgrade와 ownership을 검증한다.
- active·archived·resumed·forked, 동일 ID 충돌, CLI/DB 포맷 불일치, 빈 legacy 응답,
  cursor 반복/한도, unavailable output/exit, binary/대용량/diff 없음을 테스트한다.
- 합성 민감값을 메시지·명령·출력·diff·제목·경로에 넣고 로컬 upload bundle와
  HTTP request에 원문이 없는지 확인한다. 제외 원본은 remote log/telemetry에도 없어야 한다.
- 자식 프로세스 env의 key 집합이 선언한 allowlist에만 속하는지 검사한다.
  합성 OPENAI_API_KEY/AWS_SECRET_ACCESS_KEY/GITHUB_TOKEN/DATABASE_URL와 임의의
  민감 환경값을 부모에 넣어도 app-server로 전달되지 않아야 한다.
- config 최초 생성·기존 파일 거부·UUID 누락/손상·manifest/config UUID 불일치·scope 복원을
  검증한다. 새 API의 scope/identity 불일치는 거부하며 기존 canonical 계약은 회귀 검증한다.
- commit 이전 kill, commit 이후 ACK 유실, local checkpoint 갱신 이전 kill,
  concurrent apply, policy 중지/삭제 후 재시도, 다른 owner/API의 checkpoint를 검증한다.
- 같은 manifest 두 번: Entry 수/Version 수/내용 불변. changed/older/partial/unknown 시각은
  버전 보존·freshness 규칙·주석/AI 거부/삭제 차단을 검증한다.
- upsert의 신규 Entry·동일 replay·최신 complete 승격·검토 후보 보존을 각각 검사해
  new/unchanged/updated/retained와 실제 Entry/Version/current 상태가 일치하는지 확인한다.
- 두 소스가 모두 파싱되지만 rollout과 DB/API의 item ID/수/순서가 다른 합성 snapshot을
  partial로 검출한다. 검증 스키마/식별자 부재는 consistency unknown으로 남는다.
- 응답하지 않는 app-server를 합성 자식 프로세스로 실행해 RPC timeout 후 bounded
  TERM/KILL로 종료되는지, 임시 rollout/DB가 삭제되는지, TIMEOUT/deferred가 남는지 확인한다.
  다음 실행은 새 임시 디렉터리를 사용한다. subprocess 시작 실패/비정상 종료도 검사한다.
- 프런트엔드 결과/빈 상태/부분 실패/다른 owner 접근/로그아웃 및 기존 검색·note/import regression.
- frontend `npm test`, `npm run lint`, `npm run build`; 가능하면 backend 전체 suite.

예정 backend 검증 명령(새 test 파일은 구현 단계에서 추가):

```bash
docker compose -f compose.test.yaml up -d --wait
TEST_DATABASE_URL=postgresql+psycopg://lifhop:lifhop@127.0.0.1:55433/lifhop_test \
DATABASE_URL=postgresql+psycopg://lifhop:lifhop@127.0.0.1:55433/lifhop_test \
.venv/bin/pytest tests/test_codex_collector.py tests/test_collection_runs.py \
  tests/test_acquisition.py tests/test_entry_normalizer.py tests/test_source_history.py
# 같은 두 DB 환경변수로 .venv/bin/pytest 전체 실행
```

실제 테스트 설정은 `tests/conftest.py`의 disposable schema guard를 유지한다.
개발 DB를 test DB로 사용하지 않는다. OpenAPI 타입은 API 실행 후 frontend의
`npm run generate:api`로 갱신하고 lint/build로 검증한다.

### 실제 연결

- 작은 idle Codex 샘플에서 원본 해시·DB/rollout 불변, 읽기 결과/ID/시각을 대조한다.
- 실제 HTTP API와 격리 DB에 합성 bundle로 전체 흐름·중단/재개를 먼저 검증한다.
- 개인 샘플과 전체 선택 기록은 preview의 범위·본문 확인 후 개발 DB에 적용한다.
  개인 내용은 fixture/Git/리뷰 입력에 넣지 않고 tool 출력에는 집계만 남긴다.
- 전체 inventory를 성공/실패/제외/deferred 합계로 대조하고 실행 시간·RSS·임시 디스크·저장량을 측정한다.
  몇 개 샘플의 성공을 전체 과거 포맷 지원으로 표현하지 않는다.

### 사용자 확인

PostgreSQL/API/frontend를 기존 명령으로 실행한다. 이번 sanitized Codex 수집에는
SeaweedFS·ZIP worker가 필수는 아니다. preview/apply 실행 후:

1. `http://localhost:5173/sources`: 선택 범위·결과·누락·마지막 수집 시각 확인.
2. `/search` → Source=Codex: 알고 있는 과거 질문, 명령 결과, 코드 변경을 검색.
3. 상세에서 역할·순서·exit code·diff·source time·누락을 원본과 비교하고 주석 작성.
4. 같은 실행을 재개/반복해 개수와 버전이 늘지 않는지 확인.
5. 합성 기록을 lifhop에서 삭제 후 재실행: 복원되지 않는지 확인.

## 11. 구현 시작 시 확정할 사항과 한계

- 첫 실제 수집 프로젝트/thread 범위는 preview config로 정한다. 전체 접근 가능한
  과거 수집은 명시 선택이 필요하며 현재 개인 본문을 전송하지 않는다.
- 과거 CLI 13개 버전의 원본을 현재 app-server가 전부 읽는지는 미확인이다.
  지원 실패가 있으면 샘플/스키마 근거로 별도 adapter 보완 계획을 제시한다.
- active 세션·원본에서 사라진 기록·compaction 이전 내용·이미 잘린 명령 출력은
  복원하거나 완료로 위장하지 않는다. archived real sample도 별도 검증한다.
- turn별 Entry라 같은 thread가 여러 검색 결과로 나타난다. thread별 전용 탐색 화면은
  현재 요구를 확인한 뒤 결정하며 이번에는 출처 ID와 순서로 연결한다.
- 자동 비밀정보 탐지는 완전하지 않다. 미리보기·명시 제외와 정제된 자료만 전송하는
  경계를 유지한다. 서버 저장 허용과 외부 AI 허용은 별개다.
- 계획 검토 단계에서는 이 계획 파일만 수정한다. 구현·migration·개인 데이터 적용은 후속 작업이다.

## 12. 계획 검토 결과

### 구현 결과 (2026-10-03)

- 정규화·로컬 collector·CollectionRun/receipt API와 migration·Sources/근거 UI 구현.
- 격리 PostgreSQL 전체 237개, frontend 80개 테스트 통과. lint/build 통과.
  실제 localhost HTTP 합성 수집/재실행, commit 전 rollback, ACK 유실,
  삭제·정책·소유권, RPC timeout/자식 정리와 320~1440px 합성 화면 검증 포함.
- 개발 DB head `b23c7d91e042` 적용. 실제 원본에서 로컬 preview 33개 turn 준비:
  171개 발견, 13개 선택, 10개 읽기, 3개 실패. SOURCE_CONFLICT/EMPTY_HISTORY 안내.
- 개인 원본은 업로드하지 않았다. preview 검토 후 명시적 apply와 사용자 화면
  검증이 남았다. 구현 검토 loop/구현 커밋은 이번 요청 범위에 포함되지 않았다.
- 아래는 구현 전 계획 검토 기록이며, 당시의 예정/미실행 설명을 유지한다.

- `agy-plan-review-loop 2`: Antigravity로 두 차례 검토하고 지적 내용을 확인했다.
- 1차 3건 중 2건 반영: 자식 env allowlist 테스트, device UUID 생성·보존·복구와
  새 API identity 검증. thread 일괄 삭제 제안은 해당 UI/요구가 없어 범위 밖으로 판단했다.
- 2차 3건 모두 반영: 기존 upsert 호출 계약을 유지하는 typed outcome,
  snapshot의 의미상 불일치 검증, RPC timeout의 자식 종료·임시 파일 정리 테스트.
- 추가 정리: hash ID도 device 접두사 유지, 본문 없는 실패/차단 결과 보고,
  성공 receipt 불변, 구체적인 변경 파일과 예정 검증 명령.
- 계획·기존 서비스 계약·로드맵 범위를 대조했다. 구현 코드와 개인 데이터는 변경하지 않았다.
  계획 단계이므로 앱 테스트는 새로 실행하지 않았다. 이 계획은 아직 커밋하지 않았다.
