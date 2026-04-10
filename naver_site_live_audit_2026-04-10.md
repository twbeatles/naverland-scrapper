# 네이버 부동산 실사이트 점검 및 반영 결과 (2026-04-10)

## 요약

- 2026-04-10 기준 `new.land` complex/listing과 `single-markers` 경로는 계속 유효했습니다.
- 실제 고장은 상세 보강 파서와 단지명 direct lookup에 있었고, 이번 배치에서 코드 기준으로 복구를 완료했습니다.
- 문서, `.spec`, `.gitignore`도 현재 런타임 계약에 맞춰 재점검했습니다.

## 구현 반영

### 1. 상세 확장 수집 복구

- `src/core/services/detail_fetcher.py`
  - source 선택 기준을 body 길이 대신 `실제 필드 확보 점수`로 전환
  - `brokerageName -> 부동산상호`
  - `brokerName -> 중개사이름`
  - `phone.brokerage/mobile -> 전화1/전화2`
  - `prevJeonse/prevJeonsePrice/previousJeonse -> 기전세금`
  - `detail_source`, `detail_parse_state`, `missing_field_count`, `network_response_count`, `hydration_hit` 메타 유지

### 2. 단지명 조회 fast-fallback

- `src/core/parser.py`
  - 성공 단지명은 process cache에 저장
  - direct API `429` 발생 시 5분 cooldown 활성화
  - cooldown 동안 direct lookup 재시도 없이 즉시 `단지_{id}` fallback 반환
  - 기존 장시간 재시도 대기를 제거해 URL batch 등록 시 UI block 가능성을 낮춤

### 3. live smoke 확대

- `app_entry.py`
  - `--smoke-complex-id`
  - `--smoke-article-id`
- `src/utils/live_smoke.py`
  - 기본 probe를 `home + complex + detail`로 확장
  - complex probe는 `api/articles/complex/{id}` 응답을 확인
  - detail probe는 `front-api/v1/article/agent` 응답 확보 여부를 확인

### 4. URL / UI cleanup

- `src/ui/dialogs/batch.py`
  - placeholder 예시에 `new.land complex`, `land.naver.com complexNo`, `m.land`, `fin.land article` 반영
  - `get_urls()`는 helper 기반 URL 생성만 사용
- `src/core/crawler_parts/selenium_flow.py`
  - Selenium complex fallback URL도 helper 기반으로 통일
- 기준 정책
  - `get_complex_url()` 기본 family는 `new`
  - `get_article_url()` 기본 family는 `fin`
  - URL family는 시점에 따라 달라질 수 있음을 전제로 함

## 문서 / 패키징 정합성

- `README.md`
  - 최신 smoke CLI와 probe 구성 반영
  - URL batch 등록 예시와 fast-fallback 정책 반영
- `claude.md`, `gemini.md`
  - 실사이트 신뢰성 패치와 smoke 계약 반영
- `update_history.md`
  - `v15.0.19 (2026-04-10)` 항목 추가
- `naverland-scrapper.spec`
  - 이번 변경은 runtime/UI 레벨이라 추가 hidden import/hook 수정이 필요하지 않음을 재확인
- `.gitignore`
  - `.playwright-mcp/`만 예방적으로 추가

## 검증

- `python -m pyright`
  - 결과: `0 errors`
- `python -m pytest -q`
  - 결과: `205 passed`
- `python app_entry.py --live-smoke --smoke-headless`
  - 결과:
    - `home` probe ok
    - `complex` probe ok (`102378`)
    - `detail` probe ok (`2539123450`)

## 남은 관찰 포인트

- `front-api` 응답 키 이름은 실사이트 변경 가능성이 있으므로 smoke와 단위 테스트를 함께 유지해야 합니다.
- 단지명 lookup은 현재 정책상 `정확도보다 빠른 fallback`을 우선합니다.
- 샘플 smoke ID(`102378`, `2539123450`)는 향후 만료될 수 있으므로 장애 발생 시 먼저 교체 후보를 확인해야 합니다.
