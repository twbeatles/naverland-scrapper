APP_TITLE = "네이버 부동산 매물 크롤러 Pro Plus"
APP_VERSION = "v14.0"

CRAWL_SPEED_PRESETS = {
    "빠름": {"min": 1, "max": 2, "desc": "빠른 수집 (차단 위험)"},
    "보통": {"min": 3, "max": 5, "desc": "권장 속도"},
    "느림": {"min": 5, "max": 8, "desc": "안전한 수집"},
    "매우 느림": {"min": 8, "max": 12, "desc": "가장 안전"}
}

SHORTCUTS = {
    "start_crawl": "Ctrl+R", "stop_crawl": "Ctrl+Shift+R", 
    "save_excel": "Ctrl+S", "save_csv": "Ctrl+Shift+S",
    "refresh": "F5", "search": "Ctrl+F", "settings": "Ctrl+,",
    "quit": "Ctrl+Q", "minimize_tray": "Ctrl+M", "toggle_theme": "Ctrl+T"
}

# 거래유형 색상
TRADE_COLORS = {
    "매매": {"bg": "#FFEBEE", "fg": "#C62828", "dark_bg": "#4A1C1C", "dark_fg": "#FF8A80"},
    "전세": {"bg": "#E8F5E9", "fg": "#2E7D32", "dark_bg": "#1C4A1C", "dark_fg": "#69F0AE"},
    "월세": {"bg": "#E3F2FD", "fg": "#1565C0", "dark_bg": "#1C2A4A", "dark_fg": "#82B1FF"}
}
