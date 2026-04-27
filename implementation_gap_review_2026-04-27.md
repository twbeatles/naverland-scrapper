# 기능 구현 잠재 이슈 및 개선 적용 현황 (2026-04-27)

## 검토 및 적용 요약

`README.md`, `claude.md`, `gemini.md`, `update_history.md`, `naverland-scrapper.spec`, `.gitignore`를 현재 코드 변경과 다시 대조했다.

이번 안정화 패스에서 적용한 정책은 다음과 같다.

- 예약 complex 수집은 Playwright에서 `APT/VL`을 모두 등록한다.
- Selenium complex 수집은 기존 제약대로 `APT`만 허용하고 `VL`은 제외한다.
- 예약 실패/대상 없음 복원 시 수동 task의 `asset_type`을 보존한다.
- URL 일괄 등록은 `fin.land`/`m.land` article-only URL을 백그라운드 worker에서 단지 ID로 역조회한다.
- 월세 UI 가격 기준은 결과 정렬, 고급 필터, 카드 필터, 대시보드 가격 분포에서 `월세액 우선`으로 통일한다.
- GitHub Actions에는 pytest를 추가하지 않고 `compileall + pyright + preflight`만 유지한다.

## 반영된 주요 변경

| 영역 | 상태 | 변경 내용 |
|---|---|---|
| 예약 complex 수집 | 적용 | `crawl_engine`별로 Playwright는 `APT/VL` 모두 등록, Selenium은 `VL` 제외 |
| 예약 task 복원 | 적용 | snapshot/restore를 `(name, cid, asset_type)` 기준으로 확장 |
| URL 일괄 등록 | 적용 | article-only URL을 unresolved entry로 넘기고 worker에서 `complex_id`, `asset_type` 역조회 |
| 월세 가격 기준 | 적용 | `PriceConverter.representative_price_int()` 추가 및 UI 가격 기반 기능에 적용 |
| Selenium DOM parser | 적용 | `월세 1억/120` selector/fallback parsing 테스트 추가 및 fallback 보정 |
| mixin rebind | 적용 | 누락 helper rebind 추가, stale `_is_confirmed_empty_state` 제거, meta-test 추가 |
| 문서 정합성 | 적용 | README/claude/gemini/update_history/spec/gitignore 주석을 현재 정책으로 동기화 |
| CI pytest | 제외 유지 | `.github/workflows/ci.yml`에는 pytest step을 추가하지 않음 |
| PyInstaller spec | 변경 불필요 | 추가 hidden import/runtime hook/data bundle 필요 없음 |
| .gitignore | 변경 불필요 | 기존 build/log/data/Playwright/runtime artifact ignore 규칙으로 충분 |

## 검증 결과

- `python -m pytest -q` -> `227 passed in 55.56s`
- `npx --yes pyright` -> `0 errors, 0 warnings, 0 informations`
- `python -m src.utils.preflight` -> 정상 종료

## 남은 주의점

- article-only URL 역조회는 네이버 페이지/응답 구조 변화에 영향을 받을 수 있다. 실패 시 해당 row만 unchecked 상태와 "단지 역조회 실패" 상태로 남도록 처리했다.
- CI에서는 pytest를 실행하지 않으므로, 기능 변경 시 로컬 전체 테스트 결과를 작업 요약에 계속 남기는 방식으로 운용한다.

