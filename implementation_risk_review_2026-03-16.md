# 기능 구현 리스크 보완 완료 메모 (2026-03-16)

## 상태

- 2026-03-16 기준 주요 구현 리스크 보완 항목을 코드에 반영 완료.
- 관련 문서(`README.md`, `claude.md`, `gemini.md`, `update_history.md`)와 배포 스펙(`naverland-scrapper.spec`)도 현재 동작 기준으로 재정렬 완료.

## 반영된 핵심 변경

### 1. Startup / Preflight

- `preflight`가 `data/settings.json`을 직접 읽어 `effective crawl_engine`를 계산한다.
- 기본값은 `playwright`이며, settings 파일이 없거나 깨져도 안전하게 fallback 된다.
- `NAVERLAND_SKIP_PLAYWRIGHT_BROWSER_CHECK`는 browser check 자체를 skip 한다.
- `NAVERLAND_REQUIRE_PLAYWRIGHT_BROWSER`는 기존처럼 강제 에러를 유지한다.
- Chromium 미설치일 때:
  - `effective crawl_engine=playwright`면 시작 차단
  - `effective crawl_engine=selenium`이면 warning만 남기고 통과

### 2. Crawl Runtime / Failure Semantics

- `CrawlerThread`와 Playwright geo runtime에 incomplete 상태 추적 필드를 추가했다.
  - `geo_incomplete`
  - `geo_incomplete_count`
  - `geo_incomplete_reasons`
- `geo_sweep` discovery 단계는 `asset_type x trade_type` 단위로 예외를 격리한다.
- `_switch_to_listing_markers()` 실패는 `marker_switch_fail` incomplete 사유로 승격된다.
- marker drain timeout은 `marker_drain_timeout` incomplete 사유로 승격된다.
- geo scan 실패는 `geo_scan_failure` incomplete 사유로 기록된다.

### 3. Conservative Geo Safety Mode

- `geo_incomplete_safety_mode`를 새 settings 항목으로 추가했고 기본값은 `true`다.
- safety mode가 켜진 상태에서 geo run이 incomplete로 판정되면:
  - discovered complex DB auto-register skip
  - `crawl_history` 저장 skip
  - disappeared marking skip
- safety mode가 꺼져 있으면:
  - persistence는 허용
  - 저장되는 history row는 `run_status=incomplete`

### 4. Disappeared Marking Guardrail

- 성공적으로 검증된 pair/target이 1개도 없으면 disappeared marking을 호출하지 않도록 강화했다.
- complex/geo 공통으로 적용된다.

### 5. History / Data Contract

- `crawl_history`에 `run_status TEXT DEFAULT 'success'` 컬럼을 추가하는 additive migration을 반영했다.
- `ComplexDatabase.add_crawl_history(..., run_status="success")`
- `CrawlerThread.record_crawl_history(..., run_status="success")`
- `ComplexDatabase.get_crawl_history()`가 `run_status`를 반환한다.
- History tab은 `mode` 다음에 `status` 컬럼을 추가해 9열로 표시한다.

### 6. Marker Payload Normalization

- `normalize_marker_payload()`가 `complex_id`와 `marker_id`를 분리한다.
- crawl target 식별자는 `complexNo` / `houseNo`를 우선한다.
- 지도 metadata 식별자는 `markerId`를 별도 보존한다.

## .spec / 문서 / gitignore 점검 결과

### `naverland-scrapper.spec`

- hidden import, runtime hook, Chromium bundle 규칙은 현재 구조에서 추가 수정이 필요하지 않다.
- 다만 slim build + `effective crawl_engine=playwright` 조합에서는 local Playwright Chromium 또는 번들 Chromium이 필요하다는 정책을 주석에 반영했다.

### Markdown 문서

- `README.md`
  - preflight browser check의 실제 조건
  - geo incomplete safety mode
  - history `run_status`
  - slim build / Chromium requirement
- `claude.md`, `gemini.md`
  - AI context용 최신 runtime contract
  - geo incomplete persistence 정책
  - `run_status` / marker normalization
- `update_history.md`
  - 2026-03-16 기준 반영 내역과 검증 결과 추가

### `.gitignore`

- build/log/data/backup/Playwright 산출물 무시 규칙은 현재 기준으로 충분하다.
- 이번 범위에서는 추가 ignore 규칙이 필요하지 않았다.

## 검증

- `pytest -q`
- 결과: `149 passed`

## 현재 기준 운영 요약

- 기본 slim 배포는 유지한다.
- `playwright`를 실제로 쓸 런타임에서는 Chromium 준비 여부를 preflight가 더 엄격하게 본다.
- geo incomplete run은 기본적으로 보수적으로 취급하고, 사용자 설정으로만 persistence를 허용한다.
