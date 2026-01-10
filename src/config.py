from pathlib import Path
from src.utils.paths import get_base_dir

# ============ CONFIG ============
APP_VERSION = "v13.0"
APP_TITLE = f"🏠 네이버 부동산 크롤러 Pro Plus {APP_VERSION} (Analytics & Stability)"

BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "complexes.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
PRESETS_PATH = DATA_DIR / "presets.json"
CACHE_PATH = DATA_DIR / "crawl_cache.json"
HISTORY_PATH = DATA_DIR / "search_history.json"
RECENTLY_VIEWED_PATH = DATA_DIR / "recently_viewed.json"

CRAWL_SPEED_PRESETS = {
    "빠름": {"min": 1, "max": 2, "desc": "빠른 수집 (차단 위험)"},
    "보통": {"min": 3, "max": 5, "desc": "권장 속도"},
    "느림": {"min": 5, "max": 8, "desc": "안정적"},
    "매우 느림": {"min": 8, "max": 12, "desc": "가장 안전"}
}

SHORTCUTS = {
    "start_crawl": "Ctrl+R", "stop_crawl": "Ctrl+Shift+R", 
    "save_excel": "Ctrl+S", "save_csv": "Ctrl+Shift+S",
    "refresh": "F5", "search": "Ctrl+F", "settings": "Ctrl+,",
    "quit": "Ctrl+Q", "minimize_tray": "Ctrl+M", "toggle_theme": "Ctrl+T"
}

TRADE_COLORS = {
    "매매": {"bg": "#FFEBEE", "fg": "#C62828", "dark_bg": "#4A1C1C", "dark_fg": "#FF8A80"},
    "전세": {"bg": "#E8F5E9", "fg": "#2E7D32", "dark_bg": "#1C4A1C", "dark_fg": "#69F0AE"},
    "월세": {"bg": "#E3F2FD", "fg": "#1565C0", "dark_bg": "#1C2A4A", "dark_fg": "#82B1FF"}
}

APP_ICON_PATH = BASE_DIR / "icon.ico"
CRAWL_STATE_PATH = DATA_DIR / "crawl_state.json"  # v13.1: 크롤링 진행 상태 저장

# ============ DRIVER CONFIG (v13.1) ============
DRIVER_CONFIG = {
    "page_load_timeout": 30,
    "implicit_wait": 5,
    "scroll_wait": 0.5,
    "max_scroll_attempts": 10,
}

# ============ USER-AGENT POOL (v13.1) ============
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ============ PROXY CONFIG (v13.1) ============
# 프록시 사용 시 아래 리스트에 추가 (형식: "ip:port" 또는 "protocol://ip:port")
PROXY_LIST = []
PROXY_ROTATION_ENABLED = False

