import platform
from matplotlib import font_manager, rc
from src.utils.logger import get_logger

logger = get_logger("Plot")

_FONT_SETUP_DONE = False
_HAS_KOREAN_FONT = False


def setup_korean_font(force: bool = False) -> bool:
    """Matplotlib 한국어 폰트 설정 (성공 여부 반환)"""
    global _FONT_SETUP_DONE, _HAS_KOREAN_FONT
    if _FONT_SETUP_DONE and not force:
        return _HAS_KOREAN_FONT

    try:
        system_name = platform.system()

        available_fonts = {f.name for f in font_manager.fontManager.ttflist}
        preferred_fonts = []
        if system_name == "Windows":
            preferred_fonts = [
                "Malgun Gothic",
                "NanumGothic",
                "Noto Sans CJK KR",
                "Arial Unicode MS",
            ]
        elif system_name == "Darwin":
            preferred_fonts = [
                "AppleGothic",
                "NanumGothic",
                "Noto Sans CJK KR",
                "Arial Unicode MS",
            ]
        else:
            preferred_fonts = [
                "NanumGothic",
                "Noto Sans CJK KR",
                "UnDotum",
                "Arial Unicode MS",
            ]

        selected_font = None
        for candidate in preferred_fonts:
            if candidate in available_fonts:
                selected_font = candidate
                break

        if selected_font:
            rc("font", family=[selected_font, "DejaVu Sans"])
            rc("axes", unicode_minus=False)
            _HAS_KOREAN_FONT = True
            logger.info(f"Matplotlib Font set to: {selected_font}")
        else:
            rc("font", family=["DejaVu Sans"])
            rc("axes", unicode_minus=False)
            _HAS_KOREAN_FONT = False
            logger.warning("Korean-capable matplotlib font not found; fallback to ASCII labels.")
        _FONT_SETUP_DONE = True
        return _HAS_KOREAN_FONT
    except Exception as e:
        logger.warning(f"Font setup failed: {e}")
        _FONT_SETUP_DONE = True
        _HAS_KOREAN_FONT = False
        return False


def supports_korean_text() -> bool:
    if not _FONT_SETUP_DONE:
        return setup_korean_font()
    return _HAS_KOREAN_FONT


def sanitize_text_for_matplotlib(text: str, fallback: str = "Chart") -> str:
    if supports_korean_text():
        return str(text or "")
    source = str(text or "")
    ascii_only = "".join(ch if ord(ch) < 128 else " " for ch in source)
    normalized = " ".join(ascii_only.split())
    return normalized or fallback
