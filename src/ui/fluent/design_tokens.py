"""Design tokens — DESKTOP_UI_DESIGN_RULES §5 single source of truth.

페이지 코드에 임의 숫자/색상을 흩뿌리지 말고 여기서 가져다 쓴다.
spacing scale: 4 / 8 / 12 / 16 / 24 / 32
"""

from __future__ import annotations

# --- spacing scale ---
SPACE_XXS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32

# --- control heights ---
CONTROL_HEIGHT_SM = 32
CONTROL_HEIGHT_MD = 36
CONTROL_HEIGHT_LG = 40

# --- page / section ---
PAGE_MARGIN = 24
SECTION_GAP = 24
GROUP_GAP = 16
FORM_ROW_GAP = 12
CARD_RADIUS = 8
NAV_EXPAND_WIDTH = 208

# --- typography (px) ---
FONT_PAGE_TITLE = 22
FONT_SECTION_TITLE = 16
FONT_BODY = 13
FONT_SECONDARY = 12
FONT_CAPTION = 11

FONT_STACK = "'Pretendard', 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"

# --- window (srtgo/ktrain parity: fit available geometry, never fixed coords) ---
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 960
MIN_WINDOW_HEIGHT = 640
SCREEN_MARGIN = 40


def preferred_window_size(avail_width: int, avail_height: int) -> tuple[int, int]:
    """화면 가용 영역을 넘지 않는 기본 창 크기."""
    width = min(DEFAULT_WINDOW_WIDTH, max(MIN_WINDOW_WIDTH, avail_width - SCREEN_MARGIN))
    height = min(DEFAULT_WINDOW_HEIGHT, max(MIN_WINDOW_HEIGHT, avail_height - SCREEN_MARGIN))
    return width, height


# --- semantic colors (domain chrome keeps amber identity; not SRT/KTX red/blue) ---
ACCENT_DARK = "#f59e0b"
ACCENT_LIGHT = "#0ea5e9"
TEXT_SECONDARY_DARK = "#b6b6c6"
TEXT_SECONDARY_LIGHT = "#64748b"


def _resolve_theme_key(theme_name: str | None) -> str:
    name = str(theme_name or "auto").strip().lower()
    if name in ("light", "dark"):
        return name
    try:
        import darkdetect
        return "light" if darkdetect.theme() == "Light" else "dark"
    except Exception:
        return "dark"


def secondary_label_qss(theme_name: str | None) -> str:
    return f"font-size: {FONT_SECONDARY}px; color: {secondary_text_color(theme_name)};"


def empty_state_qss(theme_name: str | None, padding: int = 20) -> str:
    return f"color: {secondary_text_color(theme_name)}; padding: {int(padding)}px; font-size: {FONT_BODY}px;"


def secondary_text_color(theme_name: str | None) -> str:
    """보조 설명 텍스트용 semantic color (inline #888 대체). auto는 OS 설정으로 해소."""
    if _resolve_theme_key(theme_name) == "light":
        return TEXT_SECONDARY_LIGHT
    return TEXT_SECONDARY_DARK
