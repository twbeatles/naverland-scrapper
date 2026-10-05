"""Central user-facing tab / menu labels (display only; not storage keys)."""

from __future__ import annotations

# Short labels for Fluent navigation / page titles (icons come from FluentIcon).
TAB_CRAWLER = "매물 수집"
TAB_GEO = "지도로 찾기"
TAB_DB = "내 단지"
TAB_GROUP = "단지 묶음"
TAB_SCHEDULE = "예약 수집"
TAB_HISTORY = "수집 기록"
TAB_STATS = "가격 통계"
TAB_DASHBOARD = "대시보드"
TAB_FAVORITES = "즐겨찾기"
TAB_GUIDE = "가이드"

NAV_GROUP_COLLECT = "수집"
NAV_GROUP_LIBRARY = "보관함"
NAV_GROUP_ANALYZE = "분석"
NAV_GROUP_AUTO = "자동화"
NAV_GROUP_SYSTEM = "설정·도움말"

SETTINGS_TAB_GENERAL = "기본"
SETTINGS_TAB_COLLECT = "매물 수집"
SETTINGS_TAB_PERF = "속도·안정"
SETTINGS_TAB_GEO = "지도 탐색"
SETTINGS_TAB_DISPLAY = "결과 화면"
SETTINGS_TAB_BASIC = "기본"
SETTINGS_TAB_ADVANCED = "고급"

BTN_EXTRA_COLUMNS = "표시 항목"


# ── Plain-language labels for internal tokens (display only) ──────────
ASSET_LABELS = {"APT": "아파트", "VL": "빌라"}
SCHEDULE_MODE_LABELS = {"complex": "단지 묶음 수집", "geo_sweep": "지도 범위 수집"}
CRAWL_MODE_LABELS = {"complex": "단지 수집", "geo_sweep": "지도 탐색"}
THEME_LABELS = {"dark": "어두운 테마", "light": "밝은 테마", "auto": "시스템 설정"}
HISTORY_STATUS_LABELS = {
    "success": "완료",
    "ok": "완료",
    "partial": "일부만 수집",
    "failed": "실패",
    "error": "실패",
    "blocked": "차단됨",
    "empty": "매물 없음",
    "incomplete": "중간에 끊김",
    "cancelled": "중지됨",
    "stopped": "중지됨",
}


def asset_label(token) -> str:
    """APT/VL 같은 내부 토큰을 화면용 이름으로 바꾼다 (모르는 값은 그대로)."""
    text = str(token or "").strip()
    return ASSET_LABELS.get(text.upper(), text)


def crawl_mode_label(token) -> str:
    text = str(token or "").strip()
    return CRAWL_MODE_LABELS.get(text.lower(), text)


def history_status_label(token) -> str:
    text = str(token or "").strip()
    return HISTORY_STATUS_LABELS.get(text.lower(), text)


def theme_label(token) -> str:
    text = str(token or "").strip()
    return THEME_LABELS.get(text.lower(), text)


CRAWL_OWNER_LABELS = {"complex": "매물 수집", "geo": "지도로 찾기"}


def crawl_owner_label(token) -> str:
    text = str(token or "").strip()
    return CRAWL_OWNER_LABELS.get(text.lower(), text or "다른 작업")
