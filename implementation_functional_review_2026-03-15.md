# 구현 기능 점검 리뷰 (2026-03-15)

## 범위
- 저장소 실코드 기준 점검
- 참조 문서: `claude.md`, `README.md`
- 확인 대상: 크롤링 엔진, DB 스키마/쓰기 경로, UI 연동, 스케줄/내보내기 흐름

## 요약
- 전체 테스트는 현재 통과 상태입니다: `131 passed`
- 다만 최근에 확장된 `APT`/`VL` 자산 분리와 그 주변 기능들은 아직 일부 핵심 테이블/로직에 완전히 반영되지 않았습니다.
- 특히 기사(매물) 단위 이력, 즐겨찾기, purge/disappeared 처리 쪽은 자산 분리가 불완전해서, 운영 데이터가 쌓일수록 교차 오염이 발생할 가능성이 큽니다.

## 주요 발견 사항

### 1. `APT`/`VL` 자산 분리가 매물 이력 계층에는 끝까지 반영되지 않았음
- 심각도: 높음
- 근거
  - `article_history` 유니크 키가 아직 `(article_id, complex_id)` 입니다. `asset_type`가 키에 포함되지 않습니다. [schema.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/schema.py#L183) [schema.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/schema.py#L215)
  - bulk upsert도 동일 키로 충돌 처리합니다. [article_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/article_ops.py#L147) [article_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/article_ops.py#L164)
  - 이력 조회 캐시도 `complex_id`만 기준으로 읽습니다. `asset_type`가 빠져 있습니다. [history_alerts.py](C:/twbeatles-repos/naverland-scrapper/src/core/crawler_parts/history_alerts.py#L196) [article_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/article_ops.py#L13)
  - 즐겨찾기 테이블도 `(article_id, complex_id)`만 유니크 키입니다. [schema.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/schema.py#L218) [schema.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/schema.py#L226)
  - 즐겨찾기 join 역시 `article_id + complex_id`로만 연결합니다. [article_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/article_ops.py#L457) [article_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/article_ops.py#L466)
- 실제 확인
  - 로컬에서 `same article_id + same complex_id`로 `APT`와 `VL`을 각각 저장해 보니, 최종적으로 1행만 남고 뒤에 쓴 `VL` 데이터가 `APT`를 덮어썼습니다.
- 영향
  - `geo_sweep`로 들어온 `VL` 기사와 기존 `APT` 기사 이력이 서로 덮일 수 있습니다.
  - 신규여부, 가격변동, 최근 시세 비교가 잘못 표시될 수 있습니다.
  - 즐겨찾기/메모도 자산유형 간 충돌 가능성이 있습니다.
- 권장 조치
  - `article_history`, `article_favorites`의 키와 join을 최소 `(asset_type, article_id, complex_id)` 수준으로 재설계
  - `get_article_history_state_bulk()`와 관련 캐시 key에도 `asset_type` 포함
  - 자산 충돌 케이스용 마이그레이션 및 회귀 테스트 추가

### 2. disappeared 처리와 purge가 자산 경계를 일부 무시함
- 심각도: 높음
- 근거
  - complex 모드에서 쓰는 disappeared 대상 처리의 pair 경로는 `(complex_id, trade_type)`만 사용합니다. [article_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/article_ops.py#L534) [article_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/article_ops.py#L577)
  - purge는 `article_history/crawl_history/price_snapshots`는 자산 스코프를 보지만, `alert_settings/article_favorites/article_alert_log`는 `complex_id`만으로 지웁니다. [complex_group_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/complex_group_ops.py#L202) [complex_group_ops.py](C:/twbeatles-repos/naverland-scrapper/src/core/database_parts/complex_group_ops.py#L217)
- 실제 확인
  - 로컬에서 `CID1`에 대해 `APT`와 `VL` 기사 이력을 만든 뒤 `mark_disappeared_articles_for_targets([('CID1', '매매')])`를 호출하니 두 자산 모두 `disappeared` 처리되었습니다.
  - `APT` 단지를 `purge_related=True`로 삭제했더니 같은 `complex_id`를 쓰는 `VL`의 `alert_settings`까지 함께 삭제되었습니다.
- 영향
  - complex 모드 후처리가 geo/VL 데이터까지 잘못 소멸 처리할 수 있습니다.
  - 특정 자산만 정리하려고 해도 다른 자산의 알림/즐겨찾기/로그가 같이 사라질 수 있습니다.
- 권장 조치
  - pair 기반 disappeared 경로도 `asset_type`를 반드시 포함하도록 정리
  - purge 대상 테이블 전부를 자산 스코프로 통일
  - `APT/VL same complex_id` 케이스에 대한 삭제/소멸 회귀 테스트 추가

### 3. 내보내기 기능이 현재 화면 상태가 아니라 원본 수집 전체를 저장함
- 심각도: 중간
- 근거
  - 고급 필터와 중복 묶음은 화면 렌더링 레이어에서만 적용됩니다. [result_render.py](C:/twbeatles-repos/naverland-scrapper/src/ui/widgets/crawler_tab_parts/result_render.py#L28) [result_render.py](C:/twbeatles-repos/naverland-scrapper/src/ui/widgets/crawler_tab_parts/result_render.py#L35)
  - 하지만 Excel/CSV/JSON 저장은 모두 `self.collected_data`를 그대로 넘깁니다. [io_actions.py](C:/twbeatles-repos/naverland-scrapper/src/ui/widgets/crawler_tab_parts/io_actions.py#L71) [io_actions.py](C:/twbeatles-repos/naverland-scrapper/src/ui/widgets/crawler_tab_parts/io_actions.py#L84) [io_actions.py](C:/twbeatles-repos/naverland-scrapper/src/ui/widgets/crawler_tab_parts/io_actions.py#L97)
- 영향
  - 사용자는 화면에서 10건만 보고 있다고 생각해도, 저장 파일에는 숨겨진 행/필터 제외 행/중복 원본이 함께 들어갈 수 있습니다.
  - 리뷰/공유용 산출물 기준으로는 혼선이 큽니다.
- 권장 조치
  - `현재 화면 기준 저장`과 `원본 전체 저장`을 분리
  - 최소한 저장 전에 현재 적용 범위를 명시하는 UX 추가
  - 회귀 테스트: 고급 필터 ON, compact ON 상태에서 export 결과 검증

### 4. 예약 실행은 사실상 `complex/APT` 전용이고 `geo_sweep` 경로가 닫혀 있음
- 심각도: 중간
- 근거
  - 예약 실행은 항상 `crawler_tab`만 사용합니다. [stats_schedule.py](C:/twbeatles-repos/naverland-scrapper/src/ui/app_parts/stats_schedule.py#L33) [stats_schedule.py](C:/twbeatles-repos/naverland-scrapper/src/ui/app_parts/stats_schedule.py#L69)
  - 여기서 읽는 `settings["crawl_mode"]`는 기본 설정에 존재하지 않습니다. [managers.py](C:/twbeatles-repos/naverland-scrapper/src/core/managers.py#L11) [managers.py](C:/twbeatles-repos/naverland-scrapper/src/core/managers.py#L57)
  - 결과적으로 예약 실행은 기본값 `"complex"`로 동작하고, `VL`은 제외됩니다. [stats_schedule.py](C:/twbeatles-repos/naverland-scrapper/src/ui/app_parts/stats_schedule.py#L48) [stats_schedule.py](C:/twbeatles-repos/naverland-scrapper/src/ui/app_parts/stats_schedule.py#L54)
- 영향
  - 문서상 기능 폭에 비해 예약 자동화는 `complex/APT`에만 묶입니다.
  - `geo_sweep` 자동화, VL-only 그룹 자동 실행은 현재 구조상 불가능합니다.
- 권장 조치
  - 예약 실행 설정에 `complex / geo_sweep`를 명시적으로 저장
  - `geo_tab` 스케줄 경로 또는 별도 스케줄 DTO를 추가
  - VL-only 그룹의 예약 요구가 있다면 현재는 기능 공백으로 보는 편이 맞습니다.

### 5. Geo 운영 통계는 UI가 기대하는 “실시간” 값으로는 갱신되지 않음
- 심각도: 낮음
- 근거
  - `geo_discovered_count`, `geo_dedup_count`는 탐색이 모두 끝난 뒤 한 번만 세팅됩니다. [geo_mode.py](C:/twbeatles-repos/naverland-scrapper/src/core/engines/playwright_parts/geo_mode.py#L141) [geo_mode.py](C:/twbeatles-repos/naverland-scrapper/src/core/engines/playwright_parts/geo_mode.py#L143)
  - 반면 UI는 이 값들을 상태바에서 실시간 운영 통계처럼 사용합니다. [geo_crawler_tab.py](C:/twbeatles-repos/naverland-scrapper/src/ui/widgets/geo_crawler_tab.py#L296) [geo_crawler_tab.py](C:/twbeatles-repos/naverland-scrapper/src/ui/widgets/geo_crawler_tab.py#L310)
- 영향
  - 발견 단지 테이블은 늘어나는데 상태바 수치는 한동안 `0`으로 보일 수 있습니다.
  - 차단/중복/발견 상태를 실시간으로 판단하기 어려워 운영성이 떨어집니다.
- 권장 조치
  - marker handler에서 `geo_discovered_count`/`geo_dedup_count`를 increment하고 `emit_stats()` 호출
  - 문서가 약속한 “운영 통계” 수준으로 맞추는 것이 좋습니다.

## 추가하면 좋은 보완 항목
- `APT/VL same complex_id` 회귀 테스트를 `article_history`, `favorites`, `purge`, `disappeared`까지 확대
- export 동작을 `원본 저장` / `현재 화면 저장`으로 분리
- 예약 실행 설정에 엔진/모드/자산 스코프를 명시적으로 포함
- 카드뷰 즐겨찾기 토글이 앱 전역 상태(`favorite_keys`, 즐겨찾기 탭 refresh)와 즉시 동기화되도록 이벤트 경로 정리

## 이번 점검에서 실제로 확인한 것
- 코드 정독: 크롤러, Playwright/Selenium 엔진, DB 스키마/연산, UI 스케줄/저장 흐름
- 테스트 실행: `pytest -q`
  - 결과: `131 passed in 14.58s`
- 추가 로컬 재현
  - `APT/VL` 동일 `article_id + complex_id` 저장 시 `article_history`가 1행으로 합쳐지는 현상 확인
  - `mark_disappeared_articles_for_targets([('CID1', '매매')])`가 자산 구분 없이 양쪽 데이터를 같이 소멸 처리하는 현상 확인
  - `purge_related=True` 삭제 시 동일 `complex_id`의 다른 자산 알림 설정까지 제거되는 현상 확인

## 우선순위 제안
1. 자산 스코프 정합성부터 고치기
2. disappeared / purge 후처리 자산 분리 보강
3. export semantics 정리
4. 예약 실행 모드 설계 확정
5. geo 실시간 운영 통계 개선

## 후속 구현 반영 결과 (2026-03-15)
- 본 문서의 제안 항목은 이번 구현 패스에서 전부 반영했습니다.
- 주요 반영 내용
  - `article_history`, `article_favorites`를 `(asset_type, article_id, complex_id)` 기준으로 마이그레이션
  - startup 시 schema migration 전 자동 DB backup 생성
  - disappeared/purge 경로를 `(asset_type, complex_id, trade_type)` 및 asset-scoped predicate 기준으로 통일
  - 즐겨찾기 상태를 카드뷰/즐겨찾기탭/최근 본 매물/결과 재렌더 전체에서 asset scope 기준으로 동기화
  - 저장 메뉴를 `화면 기준 저장` / `원본 저장`으로 분리
  - 예약 실행에 `complex` + `geo_sweep` 모드 지원 추가
  - geo marker 처리 시점에 `geo_discovered_count`, `geo_dedup_count`를 즉시 emit하도록 보강

## .spec / 문서 / .gitignore 점검 결과
- `.spec`
  - `naverland-scrapper.spec`를 재점검했고, 이번 기능 반영 범위에서는 hidden import/runtime hook/data bundle 추가 수정이 필요하지 않았습니다.
  - 재점검 기준 주석 날짜를 `2026-03-15`로 갱신했습니다.
- `.md` 문서 정합성
  - `README.md`, `claude.md`, `gemini.md`, `update_history.md`, 본 리뷰 문서에 동일 기준으로 반영 내용을 동기화했습니다.
  - 공통 반영 기준은 `asset-scoped history/favorites`, `visible/raw export`, `scheduled geo support`, `geo runtime stats`, `.spec 재점검 결과`입니다.
- `.gitignore`
  - 현재 규칙으로 build/log/data/backup/Playwright 산출물과 DB/JSON/Excel/CSV 파일을 충분히 무시하고 있어 추가 수정은 필요하지 않았습니다.

## 최종 검증
- `python -m pytest -q`
  - 결과: `137 passed in 10.47s`
