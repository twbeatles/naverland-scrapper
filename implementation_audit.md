# 기능 구현 리스크 감사 보고서 (업데이트: 2026-02-21)

## 1) 목적/범위/기준
- 목적: `README.md`, `claude.md`, `src/`, `tests/`를 교차 점검해 문서-구현 불일치 리스크를 관리한다.
- 범위: v14.1 1차 안정성+기능확장 반영 상태 기준으로 갱신한다.
- 기준: `pytest -q` 통과 여부 + 런타임 연결성(스레드/DB/설정 반영/알림 정책) 검증.

## 2) 현재 상태 요약
- 테스트: `pytest -q` 기준 전체 회귀 통과(기존 + 신규 케이스).
- 결론:
  - 과거 핵심 미연결 이슈(F-01~F-08 대부분)는 코드/테스트로 해소됨.
  - 남은 항목은 “구조 개선/운영성 강화” 중심(P2)으로 축소됨.

## 3) 주요 이슈 처리 현황
| ID | 상태 | 요약 | 반영 |
|---|---|---|---|
| F-01 | Resolved | 크롤링 히스토리 저장 파이프라인 | `CrawlerTab._on_complex_finished -> add_crawl_history` 유지 + 회귀 테스트 |
| F-02 | Resolved | 신규/가격변동/소멸/알림 연결 | 이력 배치 업서트 + 대상 범위 소멸 + 알림 dedup(DB) |
| F-03 | Resolved | 설정값 미반영 | 속도/정렬/디바운스/완료음/재시도 설정 소비 지점 연결 |
| F-04 | Resolved | 종료 시 스레드-DB 레이스 | `shutdown_crawl(timeout)` 후 DB close 순서 강제 |
| F-05 | Resolved | 즐겨찾기 초기화 보장 | `favorite_keys` 초기화 이미 적용됨 |
| F-06 | Resolved | 그룹 변경-예약 동기화 | `groups_updated -> _load_schedule_groups` 연결 유지 |
| F-07 | Resolved | 최근 검색 저장 | 크롤링 시작 시 `history_manager.add()` 저장 유지 |
| F-08 | Resolved | 단축키 불일치 | `SHORTCUTS["settings"]` 등록/테스트 보강 |
| F-09 | Open (Low) | 레거시 잔존 메서드 정리 필요 | 동작 영향은 낮음, 추후 dead-code 정리 권장 |
| F-10 | Resolved | 파이프라인 테스트 공백 | 동시실행 가드/종료순서/dedup/대상 소멸 회귀 추가 |

## 4) 이번 배치 핵심 변경
- 동시 크롤링 시작 가드 추가(`CrawlerTab.start_crawling`).
- 안전 종료 API 추가(`CrawlerTab.shutdown_crawl(timeout_ms)`).
- 앱 종료 오케스트레이션 개선(`RealEstateApp._shutdown`).
- 소멸 매물 처리 범위 제한(`mark_disappeared_articles_for_targets`).
- 알림 하루 1회 dedup 추가(`article_alert_log`, `record_alert_notification`).
- 재시도/통계/설정 반영 확장(`max_retry_count`, `new_count/price_up/price_down`).

## 5) 신규 공개 인터페이스
- `ComplexDatabase.mark_disappeared_articles_for_targets(targets) -> int`
- `ComplexDatabase.record_alert_notification(alert_id, article_id, complex_id, notified_on=None) -> bool`
- `CrawlerThread.__init__(..., max_retry_count=3, ...)`
- `CrawlerTab.shutdown_crawl(timeout_ms=8000) -> bool`
- `CrawlerTab.update_runtime_settings()`

## 6) 남은 권장 과제 (P2)
1. `src/ui/app.py`의 deprecated 메서드군 정리 또는 별도 모듈로 격리.
2. `ruff`/`vulture` 기반 dead-code 리포트 CI 도입.
3. 운영 로그에 알림 dedup hit 카운터(일/규칙별) 집계 추가.

## 7) 품질 확인 체크리스트
- [x] 크롤링 동시 실행 방지
- [x] 종료 시 스레드 정리 후 DB 종료
- [x] 대상 범위 소멸 처리 및 건수 정확성
- [x] 동일 알림 dedup(동일일자 중복 차단)
- [x] 설정 변경 즉시 반영(속도/정렬/디바운스/완료음/재시도)
- [x] 회귀 테스트 보강 및 전체 통과
