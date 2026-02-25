# 기능 안정성 면밀 감사 리포트 (업데이트: 2026-02-25)

## 1. 개요
- 목표: `README.md`, `claude.md` 기준으로 구현/테스트 정합성을 점검하고 개선 백로그(AUD-001~010)를 실행한다.
- 범위: Crawler / DB / UI / Export / 설정/복원 / 테스트 / 문서
- 기준 문서: `README.md`, `claude.md`
- 점검일: 2026-02-25

## 2. 평가 기준
- Severity: `Critical / High / Medium / Low`
- Priority: `P0 / P1 / P2 / P3`
- Confidence: `High / Medium / Low`

## 3. 문서-구현 정합성 매트릭스
| 항목 | 상태 | 비고 |
|---|---|---|
| DB 백업/복원 안정성 | 반영 완료 | online backup + integrity/필수 테이블 검증 |
| 복원 중 동시성 제어 | 반영 완료 | maintenance mode + 타이머/크롤러 차단 |
| 종료 시퀀스 안전성 | 반영 완료 | `_shutdown() -> bool`, 실패 시 DB close 금지 |
| 고급 필터 진입/해제 동선 | 반영 완료 | 앱 메뉴 ↔ CrawlerTab 연결 |
| 가격변동 부호 정합성 | 반영 완료 | UI/CSV/Excel 모두 `+/-` 표기 통일 |
| 대시보드 경고 가시성 | 반영 완료 | warning signal + throttling |
| 테스트 공백 | 반영 완료 | 복원/종료/고급필터/통계 반복 진입 회귀 추가 |

## 4. 핵심 리스크 Top N
1. AUD-001: WAL 백업/복원 정합성
2. AUD-002: 복원 중 동시 접근
3. AUD-003: 종료 타임아웃 경계
4. AUD-004: 가격변동 하락값 출력 왜곡
5. AUD-005: 구버전 복원 후 스키마 보강

## 5. 상세 개선 백로그
| ID | 영역 | 심각도 | 우선순위 | 신뢰도 | 상태 | 핵심 반영 |
|---|---|---|---|---|---|---|
| AUD-001 | DB | Critical | P0 | High | Done | SQLite online backup + atomic restore |
| AUD-002 | UI/복원 | High | P0 | High | Done | maintenance mode + timer/crawler guard |
| AUD-003 | UI/종료 | High | P1 | High | Done | `_shutdown()->bool`, fail-fast close block |
| AUD-004 | UI/Export | High | P1 | High | Done | `PriceConverter.to_signed_string` 통일 |
| AUD-005 | DB | High | P1 | Medium | Done | 복원 후 `_init_tables` + integrity/table check |
| AUD-006 | UI/문서 | Medium | P2 | High | Done | 필터 메뉴 진입/해제 경로 복원 |
| AUD-007 | 대시보드 | Medium | P2 | Medium | Done | non-fatal warning signal/throttle |
| AUD-008 | DB Pool | Medium | P2 | Medium | Done | closing barrier + lease tracking |
| AUD-009 | 테스트 | Medium | P2 | High | Done | 복원/종료/maintenance 회귀 테스트 |
| AUD-010 | Export/테스트 | Medium | P2 | High | Done | formatter/export 회귀 테스트 |

## 6. 즉시 대응(Quick Wins)
- `pytest.ini` 추가: `-p no:langsmith_plugin`로 테스트 환경 외부 플러그인 경고 제거.
- README에 고급 필터 진입/DB 복원 유지보수 모드 동선 명시.

## 7. 중기 개선
- app 레거시 위임 메서드 정리(호환성 확인 후 제거).
- dead-code 검사(`ruff`/`vulture`) CI 도입.
- 운영 로그에 알림 dedup hit 지표 집계.

## 8. 검증 시나리오
1. 스크래핑 완료 직후 통계 탭 반복 진입 안정성
2. 크롤링 중지/종료/재시작 시 DB 연결 무결성
3. DB 백업/복원 전후 탭 로드 정상성
4. 오염 데이터(형식 혼합/NULL)에서 통계/대시보드 내성
5. 알림 dedup/소멸 경계조건 정확성
6. 장시간 로그/대량 결과 렌더링 성능 저하 여부

## 9. 부록
- 자동 회귀: `PYTHONPATH=. pytest -q` → `54 passed`
- 주요 파일:
  - `src/core/database.py`
  - `src/ui/app.py`
  - `src/ui/widgets/crawler_tab.py`
  - `src/core/export.py`
  - `src/utils/helpers.py`
  - `src/ui/widgets/dashboard.py`
  - `src/ui/widgets/chart.py`
  - `src/utils/plot.py`
