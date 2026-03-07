# Functional Implementation Deep-Dive Audit (2026-03-07)

## 범위
- 기준 문서: `README.md`, `claude.md`
- 점검 대상: `src/`, `tests/`, `.github/workflows/ci.yml`
- 관점: 기능 구현 리스크(잠재 버그), 문서 대비 정합성, 추가 구현 필요 항목

## 요약
- P0(우선 수정): 1건
- P1(단기 보완): 4건
- P2(중기 개선): 2건
- 상태 업데이트(2026-03-07): **P0~P2 제안 7건 모두 반영 완료**

## 구현 반영 결과 (2026-03-07)

1. Fallback 중복 수집 방지(P0)
- `CrawlerThread`에 pair 시퀀스/처리 집합(`_pair_sequence`, `_processed_pairs`, `_remaining_pairs`)을 도입.
- Playwright 실패 후 Selenium fallback은 미처리 pair만 수행하도록 `_fallback_allowed_pairs`를 적용.
- `_push_item`에 `(complex_id, article_id, trade_type)` dedupe를 추가(`article_id`가 없으면 skip).

2. Negative cache 안전화(P1-2)
- Playwright 수집 반환값을 `raw_items + response_seen + drain_timed_out` 구조로 확장.
- negative cache 저장은 `response_seen=True` 및 `drain_timed_out=False`일 때만 수행.
- 캐시 payload에 `reason=confirmed_empty` 메타 저장, drain timeout 시 저장 생략.

3. Playwright 메모리 워치독(P1-3)
- psutil 가능 시 500MB 기준 메모리 체크를 Playwright 경로에 추가.
- 임계치 초과 시 browser/context/mobile page pool recycle 수행.
- 통계 키 `playwright_recycle_count`, `playwright_last_recycle_reason`를 로그/stats emit에 반영.

4. DB 스키마/마이그레이션(P1-4)
- `complexes`를 `(asset_type, complex_id)` 복합 unique로 전환.
- 자동 마이그레이션에서 legacy row를 `asset_type='APT'`로 승격.
- `add_complex(..., asset_type='APT')` 계약 반영 및 관련 조회 payload에 `asset_type` 포함.

5. DB 삭제 UX + 선택 purge(P1-5)
- DB 탭 단건/다건 삭제에 확인 모달 추가.
- `관련 이력까지 삭제` 체크박스(기본 off) 추가.
- `purge_related=True` 시 `article_history`, `crawl_history`, `price_snapshots`, `alert_settings`, `article_favorites`, `article_alert_log` 삭제.

6. Playwright lightweight retry(P2-6)
- `goto`, 핵심 load wait, 모바일 상세 fetch 구간에 비동기 lightweight retry 래퍼 적용.
- 재시도 소진 시 기존 예외 흐름을 유지하면서 retry exhaustion 로그를 남김.

7. CI 보완(P2-7)
- push 시 테스트 미실행 정책 유지.
- `workflow_dispatch` + nightly `schedule`(UTC 18:00) 추가.
- 테스트 실행 조건을 `pull_request | workflow_dispatch | schedule`로 확장.

---

## P0

### 1) Playwright 실패 시 Selenium fallback이 "남은 작업"이 아니라 "전체 작업"을 다시 도는 구조
- 근거 코드
  - `src/core/engines/playwright_engine.py:224` ~ `src/core/engines/playwright_engine.py:228`
  - `src/core/crawler.py:307` ~ `src/core/crawler.py:318`
  - `src/core/crawler.py:324` (아이템 푸시 시 중복 방지 없음)
- 문제
  - Playwright 중간 실패 시 fallback이 실패 지점부터의 잔여 작업만 수행하지 않고, 전체 타겟/거래유형을 다시 순회할 수 있습니다.
  - 이미 수집한 조합을 재수집하면 결과 중복, 통계 왜곡, 수집 시간 증가가 발생할 수 있습니다.
- 영향
  - 장시간/대량 수집에서 결과 신뢰도 및 실행 시간 저하.
- 권장 수정
  1. `CrawlerThread`에 `processed_pairs`를 유지하고 fallback에는 "미처리 pair"만 전달.
  2. 또는 fallback 진입 시 현재 인덱스 기반으로 남은 큐만 재구성.
  3. 방어적으로 `_push_item`에 `(complex_id, article_id, trade_type)` 기준 중복 방지 옵션 추가.
- 권장 테스트
  - "2번째 타겟에서 Playwright 실패"를 강제하고 fallback 이후 총 처리 pair 수가 중복 없이 기대치와 동일한지 검증.

---

## P1

### 2) 느린 응답/차단 상황에서 0건이 negative cache로 저장되어 일시적 누락이 확대될 수 있음
- 근거 코드
  - `src/core/engines/playwright_engine.py:577` (고정 대기)
  - `src/core/engines/playwright_engine.py:583` ~ `src/core/engines/playwright_engine.py:586` (drain)
  - `src/core/engines/playwright_engine.py:487` ~ `src/core/engines/playwright_engine.py:489` (0건 negative cache 저장)
- 문제
  - 응답 지연/방어 페이지에서 실제 데이터가 늦게 오거나 누락되면 0건이 캐시되어 일정 시간(기본 5분) 재조회가 막힙니다.
- 영향
  - "매물이 없었다"는 오판이 사용자에게 노출될 가능성.
- 권장 수정
  1. "응답을 실제로 받았는데 리스트가 비어있음"일 때만 negative cache 저장.
  2. drain timeout 발생 시는 negative cache 저장 금지(또는 짧은 TTL 30~60초로 축소).
  3. negative cache 엔트리에 `reason`(`confirmed_empty` / `timeout`) 메타데이터 추가.
- 권장 테스트
  - 응답을 timeout 직후에 도착하도록 모킹하여 negative cache 미저장(또는 단축 TTL) 확인.

### 3) 기본 엔진이 Playwright인데 메모리 가드(임계치 초과 시 재시작)가 Selenium 경로에만 존재
- 근거 코드
  - `src/core/crawler.py:35` (메모리 임계치 상수)
  - `src/core/crawler.py:696` ~ `src/core/crawler.py:707` (Selenium 경로의 메모리 체크)
  - Playwright 엔진(`src/core/engines/playwright_engine.py`)에는 동등한 워치독 로직 없음
- 문제
  - 문서/컨텍스트(장기 실행 안정성) 대비 Playwright 장기 실행 시 메모리 누적 대응이 약합니다.
- 영향
  - 장시간 실행 시 속도 저하, 실패율 상승, 종료 지연 가능.
- 권장 수정
  1. N개 타겟마다 RSS 체크(예: `psutil`) 후 임계치 초과 시 context/page pool 재생성.
  2. 재생성 횟수/사유를 stats에 노출하여 운영 가시성 확보.
- 권장 테스트
  - 메모리 체크 함수를 모킹해 임계치 초과 상황에서 context recycle이 호출되는지 검증.

### 4) 단지 고유키가 `complex_id` 단일 기준이라 APT/VL ID 충돌 시 데이터 구분이 깨질 가능성
- 근거 코드
  - `src/core/database.py:353` (`complex_id TEXT NOT NULL UNIQUE`)
  - `src/core/crawler.py:223` (발견 단지 dedupe는 `asset_type:complex_id` 기준)
  - `src/core/crawler.py:229` (DB 저장은 `name, complex_id`만 사용)
- 문제
  - 런타임 dedupe는 자산유형까지 고려하지만 DB 스키마는 미고려라, ID 공간이 겹치는 경우 서로를 "기존"으로 오인할 수 있습니다.
- 영향
  - 단지 목록/그룹/재수집 대상의 정합성 저하 가능.
- 권장 수정
  1. `complexes` 테이블에 `asset_type` 컬럼 추가.
  2. Unique 키를 `(asset_type, complex_id)`로 전환(마이그레이션 포함).
  3. `add_complex`, 그룹 매핑, UI 표시도 asset_type 기반으로 확장.
- 권장 테스트
  - 동일 `complex_id`에 APT/VL를 각각 삽입했을 때 2건 모두 저장되는지 확인.

### 5) DB 탭의 삭제 동작이 확인 대화상자 없이 즉시 수행됨
- 근거 코드
  - `src/ui/widgets/database_tab.py:105` ~ `src/ui/widgets/database_tab.py:117`
- 문제
  - 단건/다건 삭제가 바로 실행되어 오작동/오클릭 시 복구가 어렵습니다.
- 영향
  - 사용자 데이터 손실 리스크.
- 권장 수정
  1. 삭제 전 확인 모달(삭제 건수/대상명 표시) 추가.
  2. 선택적으로 "이력까지 삭제" 토글 분리(기본 off).
- 권장 테스트
  - 확인 취소 시 delete 미호출, 확인 시만 delete 호출 검증.

---

## P2

### 6) Playwright 경로의 네트워크 재시도 정책이 RetryHandler 기준과 부분적으로 불일치
- 근거 코드
  - `src/core/engines/playwright_engine.py:556` ~ `src/core/engines/playwright_engine.py:577`
  - `src/core/engines/playwright_engine.py:598` ~ `src/core/engines/playwright_engine.py:606`
- 문제
  - `goto`, 상세 fetch 실패가 로컬 재시도 없이 누락/상위 예외로 처리됩니다.
- 영향
  - 일시 네트워크 흔들림에서 과도한 실패/누락 가능.
- 권장 수정
  - Playwright 전용 lightweight retry(2~3회, 짧은 backoff) 래퍼를 핵심 I/O에 적용.

### 7) 현재 CI 설정은 push에서 테스트를 건너뛰므로 direct push 회귀 탐지력이 낮아짐
- 근거 코드
  - `.github/workflows/ci.yml:41`
- 문제
  - 요청사항에 맞춰 push 테스트를 비활성화했지만, main 직접 push 시 회귀가 늦게 발견될 수 있습니다.
- 권장 보완
  1. `workflow_dispatch` 수동 테스트 워크플로 추가.
  2. nightly(예: UTC 18:00) 정기 풀 테스트 추가.
  3. 최소 smoke(`preflight`, 핵심 5~10개 테스트)만 push에서 유지하는 절충안 검토.

---

## 권장 실행 순서
1. **P0-1 fallback 중복 수집 방지** 먼저 처리 (정확성/시간 모두 영향).
2. **P1-2 negative cache 안전장치** 적용 (silent miss 방지).
3. **P1-3 Playwright 메모리 워치독** 추가 (장기 실행 안정성).
4. **P1-4 스키마 정합(자산유형 포함 고유키)**은 마이그레이션 계획과 함께 별도 배치.
5. 삭제 UX(P1-5), 재시도 정책(P2-6), CI 보완(P2-7) 순으로 후속 처리.

## 빠른 체크리스트
- [x] fallback 시 remaining pair만 처리
- [x] drain timeout 상황에서 negative cache 저장 금지
- [x] Playwright 메모리 워치독 + 통계 노출
- [x] complexes 고유키를 `(asset_type, complex_id)`로 확장
- [x] DB 삭제 확인 모달 도입
- [x] push 테스트 비활성화에 대한 보완 워크플로 추가
