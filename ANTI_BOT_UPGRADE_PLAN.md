# Naverland Scrapper 대규모 업그레이드 계획

작성일: 2026-03-06
상태: 2026-03-06 기준 1차 구현 반영 완료. 현재 코드베이스는 Playwright 기본 엔진, Selenium fallback, 지도 탐색 탭, DB/export 확장, spec/테스트 정합화까지 반영된 상태입니다.

## 1. 목적

현재 `naverland-scrapper`는 PyQt 기반 데스크톱 앱, SQLite 이력 관리, 알림/필터/내보내기 기능이 이미 잘 갖춰져 있다. 반면 참고 리포지토리 `anti_bot_scraper`는 단일 스크립트 중심이지만 다음 강점이 있다.

- Playwright + asyncio 기반 고속 수집
- 지도 중심 좌표/줌 기반 광역 스윕
- 네트워크 응답 가로채기 기반 수집
- 다중 워커 탭을 이용한 상세 매물 병렬 수집
- 모바일 상세 페이지 기반 추가 정보 확보
- 아파트/빌라 동시 수집과 갭투자 분석용 확장 필드

이번 업그레이드의 목표는 참고 리포지토리의 "빠른 수집 엔진"과 "지도/응답 기반 수집 방식"을 현재 앱의 구조에 맞게 흡수하는 것이다. 단, 현재 앱의 강점인 UI, DB, 알림, 그룹, 히스토리, 내보내기 기능은 유지한다.

## 2. 참고 소스 요약

### 현재 프로젝트

- UI: `PyQt6`
- 수집 엔진: `undetected-chromedriver` + `selenium`
- 구조: `src/core`, `src/ui`, `src/utils`
- 주요 강점:
  - 결과 테이블/대시보드/그룹 관리
  - 이력 추적, 소멸 매물 처리, 알림 설정
  - 캐시, DB 백업/복원, 엑셀 템플릿
  - 이미 테스트 스위트가 존재함

### 참고 리포지토리

- 검사 기준: `anti_bot_scraper` `1d20c361fe5209f0d3348c00b6e1ab7317c9a792`
- 구조: `README.md`, `scraper_kr.py`, `scraper_eng.py`
- 기술 포인트:
  - 단일 대형 Playwright 스크립트
  - 지도 이동용 Mercator 좌표 변환
  - grid sweep
  - 네트워크 response interception
  - 모바일 상세 페이지 병렬 수집
  - 매매가/기전세금 기반 필터링

## 3. 업그레이드 원칙

1. 전면 교체보다 병행 도입을 우선한다.
2. 현재 UI/DB 레이어는 유지하고, 수집 엔진만 교체 가능한 구조로 분리한다.
3. 단일 스크립트를 그대로 복사하지 않고 서비스/모듈 단위로 분해한다.
4. 사이트 차단 회피를 목적으로 한 공격적 우회보다, 합법 범위 내의 안정성/속도/복원력을 우선한다.
5. 기존 기능 회귀를 막기 위해 단계별 테스트를 먼저 보강한다.

## 4. 현재 구조와 참고 구조의 차이

| 영역 | 현재 앱 | 참고 리포지토리 | 업그레이드 방향 |
| --- | --- | --- | --- |
| 수집 실행 모델 | `QThread` 단일 크롤러 중심 | `asyncio` 이벤트 루프 기반 | 엔진 인터페이스 도입 후 Playwright 엔진 추가 |
| 탐색 방식 | 단지 ID/URL 직접 진입 | 지도 좌표 기반 광역 스윕 | 좌표 기반 "탐색 모드" 신규 도입 |
| 데이터 획득 | DOM 스크롤 + 파싱 | API 응답 가로채기 + 상세 파싱 | 목록 수집은 응답 기반, 상세는 페이지 기반 혼합 |
| 상세 정보 | 리스트 중심 파싱 | 모바일 상세 페이지 병렬 처리 | 상세 수집 전용 워커 풀 추가 |
| 자산 유형 | 네이버 단지 중심 | APT/VL 동시 | APT 우선, VL은 2차 확장 |
| 출력 | UI/DB/CSV/XLSX 강함 | Excel 중심 | 현재 앱의 DB/UI/export 유지 |
| 운영 안정성 | 강함 | 상대적으로 단순 | 현재 앱의 안정성 레이어를 유지 |

## 5. 이식 대상 기능 목록

### 즉시 도입 가치가 큰 항목

- Playwright 기반 비동기 수집 엔진
- 지도 좌표 + 줌 기반 영역 탐색
- Mercator 변환 유틸
- 그리드 스윕 로직
- 네트워크 응답 가로채기 기반 매물/단지 수집
- 다중 상세 페이지 워커 풀
- 모바일 상세 페이지 수집 경로
- 아파트/빌라 자산 유형 스위치
- 저비용 리소스 차단 옵션
- 수집 대상 우선순위화

### 현재 앱과 결합 시 가치가 큰 항목

- 기존 `alert_settings`, `article_history`, `crawl_history`와 연동
- 기존 캐시 레이어와 response-based raw cache 결합
- 기존 결과 테이블과 신규 필드 병합
- 기존 Excel/CSV/JSON exporter 확장

### 직접 이식하지 않을 항목

- 단일 파일 스크립트 구조
- 콘솔 출력 중심 UX
- 참고 리포지토리의 하드코딩된 전역 설정 방식
- 회피 자체를 목적으로 한 취약한 fingerprint 조작의 남용

## 6. 목표 아키텍처

현재 구조를 유지하면서 `수집 엔진`을 분리한다.

```text
src/
  core/
    engines/
      __init__.py
      base.py
      selenium_engine.py
      playwright_engine.py
    services/
      map_geometry.py
      map_navigation.py
      response_capture.py
      detail_fetcher.py
      enrichment.py
      gap_analysis.py
    models/
      crawl_models.py
    crawler.py              # UI와 엔진을 연결하는 orchestration 레이어
    database.py
    cache.py
    export.py
  ui/
    dialogs/
      geo_search.py         # 신규
      engine_settings.py    # 신규 또는 기존 설정창 통합
    widgets/
      crawler_tab.py        # 모드 선택, 좌표 검색, 엔진 상태 표시
```

### 핵심 설계 포인트

- `CrawlerThread`는 완전히 제거하지 않고, UI 친화적인 orchestration 레이어로 축소한다.
- Playwright는 별도 엔진 클래스로 캡슐화하고, Qt 시그널에는 배치 이벤트만 넘긴다.
- 목록 수집과 상세 수집을 분리한다.
- 상세 수집 결과는 현재 DB 스키마와 호환되게 정규화한다.
- 기존 캐시/이력/알림/소멸 처리 로직은 최대한 재사용한다.

## 7. 데이터 모델 확장안

기존 컬럼 외에 아래 필드를 신규 후보로 본다.

- `자산유형` (`APT`, `VL`)
- `위도`, `경도`, `줌`
- `수집모드` (`complex`, `geo_sweep`)
- `부동산상호`
- `중개사이름`
- `전화1`
- `전화2`
- `기전세금(원)`
- `전세_기간(년)`
- `전세_기간내_최고(원)`
- `전세_기간내_최저(원)`
- `갭금액(원)`
- `갭비율`
- `원본응답ID` 또는 `마커ID`

주의:

- 개인정보성 데이터는 저장/노출 범위를 설정 가능하게 해야 한다.
- exporter, UI 컬럼, DB migration, 테스트가 같이 움직여야 한다.

## 8. 단계별 로드맵

### Phase 0. 베이스라인 확보

목표:

- 현재 앱 기능 회귀 방지 기반 마련

작업:

- 현행 테스트 실행 및 실패 현황 정리
- 핵심 워크플로우 스모크 체크
- 크롤링 성능 기준치 측정
- 신규 엔진 플래그 설계 (`selenium`, `playwright`)

완료 기준:

- "현행 안정 버전" 기준점 문서화
- 신규 엔진 도입 전 테스트 안전망 확보

### Phase 1. 엔진 인터페이스 분리

목표:

- 현재 `CrawlerThread` 내부 로직을 엔진 추상화 뒤로 이동

작업:

- 엔진 공통 이벤트 모델 정의
- 기존 selenium 크롤러를 `selenium_engine.py`로 이동
- UI는 엔진 종류를 몰라도 동작하도록 연결 수정

완료 기준:

- 기존 기능 동일 동작
- 엔진 교체가 가능한 구조 완성

### Phase 2. Playwright 고속 엔진 1차 도입

목표:

- 참고 리포지토리의 핵심 성능 구조를 현재 앱에 병합

작업:

- Playwright 의존성 및 preflight 추가
- context/page lifecycle 관리 모듈 추가
- 리소스 차단 옵션 추가
- 목록 수집용 response capture 구현
- 지도 진입 및 줌/좌표 이동 유틸 구현

완료 기준:

- 최소 1개 지역에서 목록 수집 성공
- 결과가 UI/DB로 정상 유입

### Phase 3. 지리 기반 탐색 모드

목표:

- 단지 ID 기반 수집 외에 "좌표 기반 광역 탐색" 지원

작업:

- Mercator 변환 유틸 구현
- grid sweep 구현
- 좌표/줌 입력 UI 추가
- 탐색 대상 단지/매물 dedupe 로직 추가
- 매물 수 기반 우선순위 옵션 추가

완료 기준:

- 사용자가 좌표만 넣어도 주변 매물 수집 가능
- 중복 없이 DB 저장 가능

### Phase 4. 상세 정보 병렬 수집

목표:

- 모바일 상세 페이지 + 워커 풀 기반 고속 enrichment

작업:

- 상세 페이지 워커 탭 풀 구현
- 기사/매물 상세 정보 파서 추가
- 중개사 정보, 전화번호, 기전세금 필드 파싱
- 기존 이력/알림 로직과 연결

완료 기준:

- 목록과 상세 정보가 분리되어 수집
- 워커 수 조절 가능
- 앱 중단/종료 시 안전하게 정리

### Phase 5. 분석/필터/UI 확장

목표:

- 참고 리포지토리의 투자 분석 성격 기능을 앱 레벨 기능으로 승격

작업:

- 갭금액/갭비율 계산 유틸 추가
- 고급 필터에 신규 필드 반영
- 결과 컬럼/정렬/검색 반영
- exporter 컬럼 템플릿 확장
- 대시보드 요약 카드 추가

완료 기준:

- 신규 필드가 UI/DB/export 전 구간에서 일관 동작

### Phase 6. 안정화 및 배포

목표:

- 기능 추가보다 운영 안정성 확보

작업:

- 테스트 보강
- 장시간 수집 메모리/리소스 누수 확인
- 차단/빈 응답/리다이렉트/부분 실패 대응
- PyInstaller 배포 점검
- README/설정 가이드 업데이트

완료 기준:

- 릴리즈 가능한 수준의 문서/테스트/빌드 상태 확보

## 9. 우선 구현 추천 순서

실제 작업은 아래 순서를 권장한다.

1. 엔진 인터페이스 분리
2. Playwright 의존성 및 기본 엔진 골격 추가
3. response capture 기반 목록 수집
4. 좌표 기반 sweep 모드 추가
5. 상세 수집 워커 풀 추가
6. DB/UI/export 신규 필드 반영
7. VL 지원과 고급 분석 기능 확장

이 순서를 지키면 기존 앱을 깨지 않고 "빠른 수집" 가치를 먼저 확보할 수 있다.

## 10. 위험 요소

### 기술 리스크

- Qt 스레드와 asyncio 이벤트 루프 결합 난이도
- Playwright 브라우저 수명주기 관리 실패 시 메모리 증가
- 네이버 프론트엔드/API 구조 변경에 민감
- 목록 API와 상세 페이지 데이터 포맷 불일치 가능성

### 제품 리스크

- 기존 단지/그룹 기반 UX와 좌표 기반 UX가 충돌할 수 있음
- 신규 컬럼 증가로 테이블 복잡도가 급상승할 수 있음
- 개인정보성 필드 저장에 대한 사용자 설정이 필요함

### 대응 방안

- 엔진 추상화와 feature flag 도입
- 신규 필드는 opt-in 저장/표시 정책 적용
- 상세 수집은 fail-soft 구조로 설계
- 테스트는 파서/정규화/DB migration 중심으로 먼저 확보

## 11. 테스트 전략

### 단위 테스트

- Mercator 좌표 변환
- grid sweep 좌표 생성
- response payload 정규화
- gap 분석 계산
- 모바일 상세 파싱

### 통합 테스트

- 엔진 이벤트 -> UI 배치 반영
- DB 저장/이력/알림 연동
- exporter 신규 컬럼 반영

### 수동 검증

- 기존 단지 ID 수집
- 좌표 기반 수집
- 대량 수집 중 중단/종료
- 빌드 실행 파일 동작

## 12. 구현 시 수정 가능성이 높은 파일

- `requirements.txt`
- `src/utils/preflight.py`
- `src/core/crawler.py`
- `src/core/database.py`
- `src/core/export.py`
- `src/core/cache.py`
- `src/ui/widgets/crawler_tab.py`
- `src/ui/dialogs/settings.py`

신규 파일 후보:

- `src/core/engines/base.py`
- `src/core/engines/playwright_engine.py`
- `src/core/services/map_geometry.py`
- `src/core/services/map_navigation.py`
- `src/core/services/response_capture.py`
- `src/core/services/detail_fetcher.py`
- `src/core/services/gap_analysis.py`
- `src/ui/dialogs/geo_search.py`

## 13. 결론

이 업그레이드는 "기존 앱을 버리고 새 스크립트를 붙여넣는 작업"이 아니라, 현재 앱의 강한 운영 레이어 위에 Playwright 기반 고속 수집 엔진을 추가하는 작업으로 보는 것이 맞다.

가장 중요한 1차 목표는 아래 두 가지다.

- 기존 UI/DB/알림 체계를 유지한 채 Playwright 고속 엔진을 병행 도입한다.
- 단지 ID 기반 수집을 넘어 좌표 기반 광역 수집 모드를 추가한다.

다음 작업부터는 이 문서를 기준으로 Phase 1부터 실제 코드 변경에 들어간다.
