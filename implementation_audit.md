# 기능 구현 리스크 감사 보고서 (업데이트: 2026-02-28)

## 1) 목적/범위/기준
- 목적: `README.md`, `claude.md`, `src/`, `tests/`를 교차 점검해 문서-구현 불일치 리스크를 관리한다.
- 범위: v14.2 스크래핑 정확도/종료 안전성/문서 정합성 반영 상태 기준으로 갱신한다.
- 기준: `pytest -q` 통과 여부 + 런타임 연결성(스레드/DB/설정 반영/알림 정책) 검증.

## 2) 현재 상태 요약
- 테스트: `pytest -q` 기준 전체 회귀 통과(`54 passed`).
- 결론:
  - 과거 핵심 미연결 이슈(F-01~F-08 대부분)는 코드/테스트로 해소됨.
  - 남은 항목은 “구조 개선/운영성 강화” 중심(P2)으로 축소됨.

## 3) 주요 이슈 처리 현황
| ID | 상태 | 요약 | 반영 |
|---|---|---|---|
| F-01 | Resolved | 크롤링 히스토리 저장 파이프라인 | `CrawlerTab._on_complex_finished -> add_crawl_history` 유지 + 회귀 테스트 |
| F-02 | Resolved | 신규/가격변동/소멸/알림 연결 | 이력 배치 업서트 + 대상 범위 소멸 + 알림 dedup(DB) |
| F-03 | Resolved | 설정값 미반영 | 속도/정렬/디바운스/완료음/재시도 설정 소비 지점 연결 |
| F-04 | Resolved | 종료 시 스레드-DB 레이스 | `shutdown_crawl(timeout)` 실패 시 종료 중단 + DB close 차단 |
| F-05 | Resolved | 즐겨찾기 초기화 보장 | `favorite_keys` 초기화 이미 적용됨 |
| F-06 | Resolved | 그룹 변경-예약 동기화 | `groups_updated -> _load_schedule_groups` 연결 유지 |
| F-07 | Resolved | 최근 검색 저장 | 크롤링 시작 시 `history_manager.add()` 저장 유지 |
| F-08 | Resolved | 단축키 불일치 | `SHORTCUTS["settings"]` 등록/테스트 보강 |
| F-09 | Open (Low) | 레거시 잔존 메서드 정리 필요 | 동작 영향은 낮음, 추후 dead-code 정리 권장 |
| F-10 | Resolved | 파이프라인 테스트 공백 | 캐시 정확도/월세 이중 조건/차단 감지/종료 정책/고급필터 회귀 추가 |

## 4) 이번 배치 핵심 변경
- 동시 크롤링 시작 가드 추가(`CrawlerTab.start_crawling`).
- 안전 종료 API 추가(`CrawlerTab.shutdown_crawl(timeout_ms)`).
- 앱 종료 오케스트레이션 개선(`RealEstateApp._shutdown`, 실패 시 종료 중단).
- 소멸 매물 처리 범위 제한(`mark_disappeared_articles_for_targets`).
- 알림 하루 1회 dedup 추가(`article_alert_log`, `record_alert_notification`).
- 재시도/통계/설정 반영 확장(`retry_on_error`, `max_retry_count`, `new_count/price_up/price_down`).
- 캐시를 원본(raw) 중심으로 저장하고 조회 시 재필터링하도록 변경.
- 월세 필터를 보증금/월세 금액 분리 모델로 확장.
- 차단 페이지를 즉시 실패로 처리하는 방어 시그널 감지 추가.
- URL 숫자 과추출 완화 및 이름 미확인 기본 체크 해제 적용.
- `.spec` 빌드 설정 점검 완료(추가 hidden import 변경 없음).

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
- [x] 월세 보증금+월세 금액 동시 필터 정책 반영
- [x] 캐시 히트 시 현재 필터 기준 재평가
- [x] 차단 페이지 0건 오인 방지(실패 경로 분기)
- [x] 회귀 테스트 보강 및 전체 통과
