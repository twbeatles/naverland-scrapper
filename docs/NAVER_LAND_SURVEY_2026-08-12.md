# 네이버 부동산 사이트 조사 (2026-08-12)

이전 문서: [`NAVER_LAND_SURVEY_2026-08-04.md`](./NAVER_LAND_SURVEY_2026-08-04.md)

이 문서는 **2026-08-12** headless Playwright 라이브 프로브 + 코드 대조 결과입니다.  
앱 반영(Phase 0–1) 요약도 포함합니다.

## 핵심 변화 (08-04 대비)

| 항목 | 08-04 | 08-12 관측 / 조치 |
|------|-------|-------------------|
| `new.land` 목록 API | 유효 | **유효 유지** (auth 캡처 후 multipage) |
| `fin.land` HTML | 불안정(404/map) | **홈/map/articles → pstatic 404** (자동화 경로) |
| front-api | agent 직접 조회 도입 | 엔드포인트 존재, **세션 없으면 429** |
| geo 거래유형 쿼리 | `tradeTypes` | 사이트는 **`b=` 유지, `tradeTypes` 폐기** → 앱 `b=` 정렬 |
| 목록 `realtorName` | 미매핑 | **`부동산상호` 목록 단계에서 채움** |

## 호스트

- `new.land.naver.com` — 단지/지도/Article API/markers/overview (**핵심**)
- `fin.land.naver.com` — HTML 붕괴 가능; front-api는 조건부
- `m.land.naver.com` — fin 합류, 독립 HTML 소스 부적합

## 앱 반영 (본 라운드)

- `src/core/services/site_contract.py` — 호스트·geo URL·front-api URL 계약
- geo / complex page: `a` + **`b`** + `e=RETAIL`
- `normalize_article_payload`: `realtorName`, 동일주소 최고/최저가, 확인유형
- entry plan: 기본 `direct` + `new_home` only (fin/m은 옵션 플래그)
- warmup: `new.land` 단독
- detail: fin 404 시 m 재시도 축소, list 중개명 보존, empty detail wipe 방지

## 반영 체크리스트 (2026-08-12 후속 완료)

- [x] site_contract + geo `b=` + list `realtorName`
- [x] fin HTML degrade / entry plan / warmup new.land only
- [x] front-api-only 옵션 + 세션 워밍(auth/si) + 429 워커 축소
- [x] 상세 통계 list_meta / host_unreachable / 429 + finish 로그
- [x] 상세 결과 입력 순서 보존
- [x] 마커 `single-markers/2.0` 직접 호출 폴백
- [x] overview API name_lookup
- [x] 표시/export: 동일주소최고·최저, 확인유형, 상세주소, 직거래
- [x] 카드 메타: 확인일·중개소명
- [x] live-smoke: host-health, geo-contract(`b=`), realtorName, 마커 DOM 약화 허용
- [x] 설정 UI: `detail_front_api_only`
- [x] rebind globals 가드 테스트
- [x] 앱 종료 시 crawl_lock force_release

### 의도적 비범위 (유지)

- OPST 등 전 자산 유형
- article_history DB 컬럼 migration
- PRE 분양권 기본 on

## 검증

```powershell
python -m pytest -q tests/test_site_contract.py tests/test_response_capture_normalize.py tests/test_detail_fetcher.py tests/test_article_api.py tests/test_playwright_engine_globals.py
python -m pytest -q --ignore=tests/test_ui_wiring.py --ignore=tests/test_ui_runtime_smoke.py --ignore=tests/test_geo_tab_wiring.py
```

*작성: 2026-08-12 · 후속 완료 동기화: 동일일*
