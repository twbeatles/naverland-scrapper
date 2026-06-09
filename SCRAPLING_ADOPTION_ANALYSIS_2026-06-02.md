# Scrapling Adoption Status

현재 코드베이스에는 Scrapling을 도입하지 않았습니다.

## 현재 결정

- 기본 수집 엔진은 Playwright입니다.
- 일반 단지 수집의 보조 fallback으로 Selenium을 유지합니다.
- 지도 기반 수집은 Playwright 경로를 사용합니다.
- 목록 수집 속도 개선은 신규 크롤링 의존성 대신 Article API fast path와 기존 response-capture fallback 최적화로 처리했습니다.

## 도입 보류 이유

- 현재 장애 대응 로직은 Playwright response, page state, mobile detail fetch, SQLite history/cache 흐름과 강하게 결합되어 있습니다.
- Scrapling 도입은 수집 엔진 추가 수준이 아니라 parser, cache, fallback, live smoke, packaging 검증 범위를 함께 늘립니다.
- 현재 성능 기준은 기존 구조 안에서 개선되었고, live smoke도 통과합니다.

## 재검토 조건

- 네이버 페이지/API 구조 변화로 Playwright fallback 안정성이 크게 떨어질 때
- Article API fast path가 장기간 차단되고 response-capture만으로 수집 속도 목표를 맞추기 어려울 때
- 신규 엔진 도입 비용을 감당할 별도 회귀 테스트와 패키징 검증 시간이 확보될 때

재검토 전에는 `python -m pytest -q`, `python scripts/perf_baseline.py`, live smoke 전체 probe를 기준선으로 남겨야 합니다.
