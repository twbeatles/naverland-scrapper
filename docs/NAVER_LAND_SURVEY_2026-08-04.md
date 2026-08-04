# 네이버 부동산 사이트 조사 보고서 (2026-08-04)

이 문서는 `naverland-scrapper` 앱이 의존하는 네이버 부동산 관련 호스트·API·응답 형태를 **2026-08-04** 기준으로 조사한 결과와, 앱에 반영할 수정/추가 항목을 정리한다.

조사 수단:

- CodeGraph MCP로 앱 수집 경로(article API / detail / geo / DB) 추적
- Playwright 라이브 프로브 (`new.land` / `fin.land` / `m.land`)
- 기존 live-smoke 로그 (`logs/live-smoke-after-structure.json` 등)
- 공개 스크래퍼·문서 (front-api, article API 파라미터 관례)

---

## 1. 호스트 현황

| 호스트 | 타이틀/역할 (관측) | 앱 의존 | 상태 |
|--------|-------------------|---------|------|
| `new.land.naver.com` | **네이버페이 부동산** — 단지 지도·목록·`/api/articles/*` | complex 수집, geo | **유효** |
| `fin.land.naver.com` | **Npay 부동산** — 매물 상세 SPA·`front-api` | detail 보강 | **핵심, HTML 불안정** |
| `m.land.naver.com` | 홈/매물이 fin 쪽으로 리다이렉트 | detail fallback | **독립 HTML 소스로 부적합** |
| `land.naver.com` | 레거시 진입 | URL 파서 일부 | 리다이렉트 가능 |

라이브 홈 프로브 예:

- `new.land.naver.com/` → complexes 맵, `a=APT:ABYG:JGC&e=RETAIL`
- `m.land.naver.com/` → `fin.land.naver.com/map?...`
- `fin.land.naver.com/` → Npay 맵

---

## 2. 매물 목록 API (`new.land`)

### 엔드포인트

```
GET https://new.land.naver.com/api/articles/complex/{complexNo}
GET https://new.land.naver.com/api/articles/house/{houseNo}   # VL 등
```

### 브라우저가 쓰는 기본 쿼리 (남산타운 3833 관측)

- `realEstateType=APT:ABYG:JGC` — 앱 `article_api_real_estate_type("APT")`와 **일치**
- `tradeType` (비어 있으면 전체, 앱은 A1/B1/B2 지정)
- `page`, `type=list`, `order=rank`, `priceType=RETAIL`, `sameAddressGroup=false`
- 가격/면적 상한 등 필터 파라미터

### 페이지네이션

- 응답 `articleList` (페이지당 약 20건)
- `isMoreData` / `moreData` 플래그
- 앱: `src/core/services/article_api.py` + fast path 다중 페이지 루프 **이미 반영**

### Rate limit

- 브라우저 세션 없이 연속 `request.get` 시 **429 TOO_MANY_REQUESTS** 빈번
- 앱 fast path도 auth/cookie 없이 호출하면 실패 → 기존처럼 페이지 워밍업 후 Authorization 캡처 필요
- 페이지 간 짧은 간격·429 시 fallback 강화 권장

### 분양권(PRE)

- 일부 외부 도구: `APT:ABYG:JGC:PRE`
- 라이브 UI 기본 URL에는 PRE 없음 → **기본 제외, 옵션으로만**

---

## 3. 매물 상세 · front-api (`fin.land`) — **최대 갭**

### HTML 경로 문제

| URL | 관측 |
|-----|------|
| `fin.land.naver.com/articles/{id}` | 307 후 **404 HTML**(`financial.pstatic.net/404.html`) 또는 **map-only SPA** 가능 |
| `m.land.naver.com/article/info/{id}` | fin articles로 리다이렉트 후 동일 문제 |
| `new.land.naver.com/articles/{id}` | 일반 네이버 페이지에 가깝고 상세 데이터 부족 |

live-smoke 예 (`live-smoke-after-structure.json`):

- detail-fields: `parse_state=partial`, `core_field_count=1`, `network_response_count=0`, `hydration_hit=0`
- 중개사·전화·기전세 DOM 파싱이 실환경에서 취약

### 살아 있는 front-api (네비게이션 중 관측)

```
GET https://fin.land.naver.com/front-api/v1/article/agent?articleNumber={aid}
GET https://fin.land.naver.com/front-api/v1/article/maintenanceFee?articleNumber={aid}
GET https://fin.land.naver.com/front-api/v1/article/oldMaintenanceFee?articleNumber={aid}
GET https://fin.land.naver.com/front-api/v1/article/transport?itemType=article&itemId={aid}
```

공개 자료 추가 후보:

```
GET /front-api/v1/article/key?articleId=
GET /front-api/v1/article/basicInfo?articleId=&realEstateType=&tradeType=
GET /front-api/v1/complex?complexNumber=
```

### 앱 조치 방향

1. DOM 텍스트 의존을 줄이고 **agent(및 관련) front-api를 request 컨텍스트로 직접 호출**
2. 네트워크 캡처 응답 키 집합 확장 (`brokerageName`, nested `phone` 등)
3. 최종 URL이 404/map이어도 agent JSON이 있으면 **partial/success** 로 인정
4. m.land detail URL은 후순위 유지

---

## 4. 목록 필드 매핑 갭

앱 `normalize_article_payload`가 이미 쓰는 핵심 필드:

- `articleNo` / `atclNo`, `dealOrWarrantPrc`, `rentPrc`, `area1`/`area2`, `floorInfo`, `direction`, `tagList`/`articleFeatureDesc`, trade/asset type codes

목록에 자주 있으나 앱 결과 dict에 없던 메타 (추가 권장):

| API 필드 | 앱 키 |
|----------|--------|
| `articleConfirmYmd` | `확인일` |
| `buildingName` | `동` |
| `areaName` | `타입명` |
| `sameAddrCnt` | `동일주소건수` |
| `cpName` | `정보제공` |
| article `latitude`/`longitude` | 위도/경도 보강 |

DB `article_history` 스키마 확장은 2차. 1차는 결과 dict·export 중심.

---

## 5. Geo 스캔

- 앱: `https://new.land.naver.com/complexes?ms=...&a=APT&tradeTypes=A1`
- 사이트 기본: `a=APT:ABYG:JGC` (+ `e=RETAIL`)
- 마커 API: `complexes/single-markers` / `houses/single-markers` (live-smoke 성공 이력)
- **권장:** geo URL의 `a=` 를 `article_api_real_estate_type`과 동일 복합 문자열로 통일

---

## 6. 앱 구조 요약 (CodeGraph)

```
PlaywrightCrawlerEngine
  complex_mode: article_api fast path → response_capture → detail_enrichment
  geo_mode: scan markers → complex crawl per marker
services:
  article_api.py          URL/페이지네이션 순수 함수
  response_capture.py     목록 정규화
  detail_fetcher.py       상세 보강 (front-api 강화 대상)
```

이미 양호:

- multi-page Article API, response-capture supplement
- 경로 bootstrap, Settings 격리, live-smoke 골격

---

## 7. 반영 체크리스트

- [x] 본 조사 문서 저장
- [x] front-api agent 직접 조회 + 파서 강화
- [x] 목록 메타 필드 (`확인일`, `동`, …)
- [x] Article API 429 구분·페이지 간 delay
- [x] Geo `a=` 복합 타입 정렬
- [x] 수집/표시 옵션 + 설정 탭 UI + 결과「표시 항목」
- [x] 전역 수집 락 (매물 수집 ↔ 지도 ↔ 예약)
- [x] 완료 로그에 상세 skip/상한/API 실패 요약
- [x] 단위 테스트 (`pytest` 328 passed, 2026-08-04)
- [x] live-smoke (detail-fields `success` 이력; 로그는 로컬 `logs/` 미추적)
- [x] `update_history.md` / `PROJECT_AUDIT.md` / `README.md` 동기화

### 후속 (의도적 제외 · 경량 원칙)

- OPST(오피스텔) 등 자산 유형 전면 지원
- article_history 신규 컬럼 migration (메타 필드는 결과 dict/export 전용)
- 분양권(PRE) 기본 수집 (옵션 기본 off 유지)

---

## 8. 참고

- 프로젝트 내부: `PROJECT_AUDIT.md`, `update_history.md`, `README.md`, `naverland-scrapper.spec`
- 외부: Npay 부동산 프론트 API 관례, 비공식 내부 API 사용 시 약관·rate limit 주의

*문서 작성일: 2026-08-04 · 동기화: 2026-08-04 (감사 수정 반영 후)*
