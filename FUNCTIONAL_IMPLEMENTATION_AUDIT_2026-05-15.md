# 기능 구현 리스크 점검 및 클로저 보고서 (2026-05-15)

## 점검 범위

- 기준 문서: `README.md`, `claude.md`, `gemini.md`, `update_history.md`
- 보조 계약: `naverland-scrapper.spec`, `.gitignore`
- 주요 코드 영역: URL 파서/단지명 조회, URL 일괄 등록, Playwright live-smoke, 모바일 상세 파서, Geo 크롤링, 예약 Geo, 수동 단지 등록 UI, 패키징 검증 흐름

## 최초 리스크 요약

최초 점검에서는 소스 테스트와 live-smoke가 통과했지만 운영 환경에서 아래 항목이 품질 저하나 검증 사각지대로 이어질 수 있다고 판단했다.

1. 직접 단지명 API가 `429`를 반환한 뒤 cooldown 중인 미캐시 단지가 browser fallback 없이 `단지_{id}`로 내려갈 수 있음
2. 기본 live-smoke article ID가 실제 검증 대상인지 seed인지 문서상 모호함
3. Geo APT/VL 체크박스를 모두 해제하면 전체 수집으로 확장되어 사용자의 의도와 다르게 실행될 수 있음
4. 수동 단지 ID 추가가 `APT`로 고정되어 `VL` 사용자가 URL 일괄 등록 등 우회 경로를 써야 함
5. live-smoke가 상세 페이지 접근성은 확인하지만 모바일 상세 필드 파싱 품질까지 검증하지 않음
6. 릴리스 전 검증에서 source 실행과 frozen 실행을 분리해 확인해야 함

## 구현 결과

| 항목 | 처리 결과 |
| --- | --- |
| 이름 조회 429 cooldown | `_name_lookup_cooldown_until`을 direct API cooldown으로만 적용하고, cooldown 중 미캐시 단지도 browser fallback을 시도하도록 수정했다. 성공명은 `(asset_type, complex_id)` 캐시에 저장한다. |
| live-smoke seed/effective | 기본 `--smoke-article-id=2625154515`를 고정 검증 대상이 아닌 seed로 명확화했다. 기본 seed를 쓰면 complex probe의 현재 `sample_article`이 effective article ID가 될 수 있다. |
| smoke JSON 관측성 | JSON 로그에 `requested_article_id`, `effective_article_id`, `runtime_source`, 실행 파일 경로, base/data dir, `include_detail_fields`를 기록한다. |
| 상세 필드 smoke | `--live-smoke-detail-fields` 옵션을 추가해 `detail_parse_state`, 핵심 필드 수, 누락 필드 수, network/hydration 메타를 검증한다. |
| Geo 자산 미선택 | 지도 탐색과 예약 Geo에서 APT/VL 모두 미선택 상태를 전체 수집으로 확장하지 않고 경고 후 차단한다. |
| 수동 단지 자산 선택 | 직접 추가 입력 줄에 `APT/VL` 선택 컨트롤을 추가했고 기본값은 기존 호환성을 위해 `APT`로 유지했다. |
| 문서/spec/ignore | `README.md`, `claude.md`, `gemini.md`, `update_history.md`, `naverland-scrapper.spec`, `.gitignore`를 코드 변경과 맞게 갱신했다. |

## 패키징 및 ignore 판단

`naverland-scrapper.spec`는 새 변경에 대해 추가 hidden import, runtime hook, data bundle이 필요하지 않다. 변경된 기능은 기존에 포함되는 Python runtime/UI/test/doc 영역이며, Playwright hidden imports, runtime hook, Chromium bundle 수집 규칙으로 충분하다.

`.gitignore`도 신규 패턴이 필요하지 않다. `git check-ignore -v` 기준으로 source/frozen smoke JSON 로그는 `logs/`, PyInstaller 산출물은 `build/`와 `dist/`, runtime DB/설정 파일은 `data/`, 테스트/bytecode 산출물은 cache/pycache 규칙에 포함된다.

## 검증 결과

| 항목 | 결과 |
| --- | --- |
| 핵심 회귀 테스트 | `python -m pytest tests/test_parser_module.py tests/test_app_entry.py tests/test_live_smoke.py tests/test_ui_wiring.py tests/test_ui_runtime_smoke.py -q` => `107 passed` |
| 전체 테스트 | `python -m pytest -q` => `267 passed` |
| 문법 컴파일 | `python -m compileall -q app_entry.py src tests` => 통과 |
| 사전 점검 | `python -m src.utils.preflight` => 통과 |
| 타입 점검 | `npx --yes pyright` => `0 errors, 0 warnings, 0 informations` |
| source live-smoke | `logs/live-smoke-source-2026-05-15.json` 기준 `ok=true`, effective article `2626368166` |
| source detail-field smoke | `logs/live-smoke-detail-fields-2026-05-15.json` 기준 `ok=true`, `detail-fields` 통과 |
| PyInstaller build | `pyinstaller -y naverland-scrapper.spec` => `dist/naverland/naverland.exe` 생성 |
| frozen preflight | `dist\naverland\naverland.exe --preflight` => exit 0, 선택 라이브러리 `plyer` 누락 warning-only |
| frozen live-smoke | `logs/live-smoke-frozen-2026-05-15.json` 기준 `ok=true`, `runtime_source=frozen` |
| frozen detail-field smoke | `logs/live-smoke-frozen-detail-fields-2026-05-15.json` 기준 `ok=true`, `detail-fields` 통과 |

첫 `pyinstaller naverland-scrapper.spec` 실행은 기존 `dist/naverland` 출력 폴더가 남아 있어 COLLECT 단계에서 중단되었다. 빌드 산출물은 ignore 대상이므로 `pyinstaller -y naverland-scrapper.spec`로 기존 출력 폴더를 교체했고, 이후 frozen 검증을 완료했다.
