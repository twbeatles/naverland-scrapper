# 부동산 크롤링/스크래핑 구현 리스크 감사 (2026-03-07)

## 1) 목적과 기준
- 목적: 현재 코드 기준으로 크롤링/스크래핑 기능에서 잠재 장애 요인, 데이터 품질 저하 요인, 운영 리스크를 선제 점검.
- 기준 문서: `README.md`, `claude.md`의 v15.0 운영/기능 정책(Playwright 기본 + Selenium fallback, geo sweep, 캐시/이력 저장).
- 점검 범위:
  - 엔진/수집: `src/core/crawler.py`, `src/core/crawler_parts/*`, `src/core/engines/playwright_engine.py`, `src/core/engines/playwright_parts/*`
  - 파싱/상세: `src/core/item_parser.py`, `src/core/services/response_capture.py`, `src/core/services/detail_fetcher.py`
  - 저장/이력: `src/core/database.py`, `src/core/database_parts/*`, `src/core/cache.py`

## 2) 요약 결론
- 현재 구조는 안정화 패치가 잘 반영되어 있고(캐시 컨텍스트 분리, DB write 직렬화, Playwright drain timeout 처리), 기본 운영 안정성은 양호함.
- 다만 아래 항목은 실제 운영에서 수집 누락/오탐/장기 차단 가능성을 높일 수 있어 우선 대응이 필요함.
  - Selenium 경로의 빈 결과 캐시 저장 조건
  - API 경로/DOM 구조 변경에 대한 취약한 결합
  - 차단/오류 누적 시 자동 감속·중단 정책 부족
  - 날짜 단위 이력 처리로 인한 경계시간 오판 가능성

## 3) 우선순위 리스크 목록

### P1 (높음)

1. **Selenium 경로의 0건 결과가 검증 없이 negative cache로 저장될 수 있음**
- 근거:
  - `src/core/crawler_parts/selenium_flow.py:247`
  - `src/core/crawler_parts/selenium_flow.py:257`
  - `src/core/crawler_parts/selenium_flow.py:267`
- 설명:
  - Selenium 경로는 `raw_items`가 비면 바로 빈 배열 캐시를 저장함.
  - Playwright 경로처럼 `response_seen`/`drain_timed_out` 검증이 없어, 일시적 파싱 실패/차단 페이지/로딩 이슈가 “정상 0건”으로 캐시될 수 있음.
- 영향:
  - TTL 동안 재조회가 생략되어 수집 누락이 고정될 수 있음.
- 권고:
  - Selenium도 Playwright와 동일한 negative-cache 가드(`confirmed_empty`) 정책으로 통일.
  - 최소한 차단 시그널 감지·파싱 실패 케이스는 0건 캐시 금지.

2. **차단 감지 이후 전역 감속/회피 정책이 약함**
- 근거:
  - `src/core/crawler_parts/dom_scroll_parse.py:25`
  - `src/core/crawler_parts/dom_scroll_parse.py:29`
  - `src/core/engines/playwright_parts/complex_mode.py:38`
  - `src/core/engines/playwright_parts/complex_mode.py:43`
- 설명:
  - 차단 페이지 감지 시 예외를 던지지만, 이후 흐름은 fallback 전환 위주이며 “차단 강도 증가 시 전체 속도 감속/일시 중지/쿨다운”이 체계적으로 없음.
- 영향:
  - 차단 상황에서 요청 밀도를 유지하면 계정/IP 단위 제한이 장기화될 수 있음.
- 권고:
  - 차단 신호 횟수 기반 회로 차단(circuit breaker) 도입.
  - `N`회 연속 차단 시 실행 일시중단 + UI 경고 + 자동 재시작 대기.

### P2 (중간)

3. **Playwright 응답 수집이 특정 API 패턴에 강하게 결합됨**
- 근거:
  - `src/core/engines/playwright_parts/complex_mode.py:177`
  - `src/core/engines/playwright_parts/complex_mode.py:185`
- 설명:
  - `expected = "/api/articles/{house|complex}/{cid}"` 패턴에 맞지 않으면 응답을 무시.
  - 서비스 API 경로 변경, A/B 테스트, 페이로드 구조 변형 시 무수집 가능성.
- 영향:
  - 정상 페이지에서도 수집량이 급감할 수 있음.
- 권고:
  - endpoint allowlist 다중 패턴 지원, payload schema 기반 판별(키 존재 검증) 추가.
  - “응답은 왔는데 매칭 실패” 카운터를 통계로 노출.

4. **상세 정보 파싱이 페이지 텍스트 정규식 중심이라 취약함**
- 근거:
  - `src/core/services/detail_fetcher.py:75`
  - `src/core/services/detail_fetcher.py:111`
  - `src/core/services/detail_fetcher.py:117`
- 설명:
  - DOM 구조/문구가 바뀌면 정규식 파싱 성공률이 급락할 수 있음.
  - 실패 시 대부분 무음(fallback empty)으로 처리되어 품질 저하를 즉시 감지하기 어려움.
- 영향:
  - 중개사/전화/기전세/전세이력 필드의 결측률 상승.
- 권고:
  - 항목별 파싱 성공률(metric) 기록 및 임계치 하락 시 경고.
  - 가능하면 텍스트 전체 정규식보다 구조적 셀렉터 우선 + 예비 규칙 체계화.

5. **날짜 단위(`CURRENT_DATE`) 상태처리의 경계시간 오판 가능성**
- 근거:
  - `src/core/database_parts/article_ops.py:150`
  - `src/core/database_parts/article_ops.py:180`
  - `src/core/database_parts/article_ops.py:501`
- 설명:
  - `last_seen`/`first_seen`가 날짜 단위라 장시간 실행이 자정 경계를 넘을 때 소멸 판정이 기대와 다를 수 있음.
- 영향:
  - 소멸 처리 false positive/false negative 가능성.
- 권고:
  - `DATE` 대신 `TIMESTAMP`로 전환하거나, 소멸 판정을 “마지막 실행 배치 ID” 기준으로 변경.

6. **geo sweep 요청량 제어가 정적 파라미터 중심**
- 근거:
  - `src/core/engines/playwright_parts/geo_mode.py:184`
  - `src/core/engines/playwright_parts/geo_mode.py:196`
- 설명:
  - `rings/step_px/dwell_ms` 고정 조합으로 요청량이 급증할 수 있으나, 차단률/응답속도 기반 동적 조절 로직이 없음.
- 영향:
  - 대규모 좌표 탐색 시 차단률 증가 및 수집 품질 저하.
- 권고:
  - 평균 응답시간, 차단률, drain timeout 비율에 따라 sweep 강도를 자동 완화.

### P3 (개선)

7. **오류/예외 관측성 표준화 부족**
- 근거:
  - `src/core/engines/playwright_parts/complex_mode.py:182`
  - `src/core/engines/playwright_parts/complex_mode.py:235`
  - `src/core/engines/playwright_parts/complex_mode.py:282`
- 설명:
  - 다양한 예외가 로그만 남기고 계속 진행되어 원인/빈도 집계가 어려움.
- 권고:
  - error_code 분류(네트워크/차단/파싱/DB) + 카운터를 stats payload에 포함.

8. **개인정보(중개사 연락처) 저장 정책 명시 부족**
- 근거:
  - `src/core/services/detail_fetcher.py:117`
  - `src/core/database_parts/schema.py:95`
- 설명:
  - 전화번호 수집/저장이 구현되어 있으나 보존기간/마스킹/삭제정책 문서화가 부족.
- 권고:
  - 최소 보존기간 정책, 내보내기 시 마스킹 옵션, 삭제 API/문서 명시.

## 4) 즉시 적용 권장 작업 (Shortlist)
1. Selenium negative cache 저장 조건을 Playwright 정책과 동일하게 변경.
2. 차단 감지 누적 기반 쿨다운(circuit breaker) 추가.
3. 파싱 성공률/응답 매칭 실패율/차단률을 `stats_signal`에 추가해 UI 노출.
4. `last_seen`/`disappeared` 판정 기준을 timestamp 또는 run-id 기반으로 보강.
5. README/운영문서에 연락처 데이터 보존/마스킹 정책 명시.

## 5) 참고
- 본 문서는 2026-03-07 시점 코드 기준 정적 점검 결과이며, 실운영 트래픽·차단 패턴에 따라 우선순위는 조정될 수 있음.

## 6) 문서/패키징 정합성 추적 (2026-03-07, rev2)
- 상태:
  - 본 감사 문서는 저장소 기준 문서로 복구/유지됨.
  - `README.md`, `claude.md`, `gemini.md`, `update_history.md`와 정책 문구를 동기화함.
- `.spec` 재검증:
  - `naverland-scrapper.spec`는 현재 분할 리팩토링 구조(`database_parts`, `crawler_parts`, `playwright_parts`, `app_parts`, `crawler_tab_parts`) 기준에서도 추가 수정 불필요.
- `.gitignore` 재검증:
  - 빌드/로그/백업/Playwright 산출물 관련 무시 규칙이 이미 충분하며, 추가 패턴은 현 시점에서 필요하지 않음.
