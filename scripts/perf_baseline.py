import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import sys

# Headless-friendly default for benchmark environments.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup
from PyQt6.QtWidgets import QApplication

from src.core.cache import CrawlCache
from src.core.item_parser import ItemParser
from src.ui.app import RealEstateApp
from src.ui.widgets.dashboard import CardViewWidget
from src.utils.paths import LOG_DIR, ensure_directories


def _benchmark_parser():
    html = """
    <div class="item_inner">
      <div class="item_price"><strong>매매 10억 2,000만</strong></div>
      <div class="item_area">공급/전용 110/84㎡</div>
      <div class="item_floor">10/20층</div>
      <div class="item_direction">남향</div>
      <div class="item_desc">올수리 역세권</div>
    </div>
    """
    item = BeautifulSoup(html, "html.parser").select_one(".item_inner")
    n = 3000
    start = time.perf_counter()
    for _ in range(n):
        ItemParser.parse_element(item, "Bench", "12345", "매매")
    elapsed = time.perf_counter() - start
    throughput = n / elapsed if elapsed > 0 else 0
    return {"iterations": n, "elapsed_sec": elapsed, "throughput_items_per_sec": throughput}


def _benchmark_cache():
    payload = [{"id": i, "price": "1억"} for i in range(50)]
    with tempfile.TemporaryDirectory() as tmp:
        cache_path = Path(tmp) / "crawl_cache.json"
        with patch("src.core.cache.CACHE_PATH", cache_path):
            cache = CrawlCache(ttl_minutes=30, write_back_interval_sec=999, max_entries=2000)
            start_set = time.perf_counter()
            for i in range(100):
                cache.set(str(10000 + i), "매매", payload)
            set_elapsed = time.perf_counter() - start_set

            start_flush = time.perf_counter()
            cache.flush()
            flush_elapsed = time.perf_counter() - start_flush

    return {
        "set_100_elapsed_sec": set_elapsed,
        "flush_elapsed_sec": flush_elapsed,
    }


def _benchmark_card_render(app):
    card_view = CardViewWidget(is_dark=True)
    sample = {
        "단지명": "테스트단지",
        "거래유형": "매매",
        "매매가": "10억",
        "보증금": "",
        "월세": "",
        "면적(평)": 34.2,
        "면적(㎡)": 84.9,
        "층/방향": "10/20층 남향",
        "타입/특징": "올수리 역세권",
        "매물ID": "123",
        "단지ID": "456",
        "price_change": 0,
        "is_new": False,
    }
    data = []
    for i in range(1000):
        d = dict(sample)
        d["매물ID"] = str(i)
        data.append(d)

    start = time.perf_counter()
    card_view.set_data(data)
    app.processEvents()
    elapsed = time.perf_counter() - start
    card_view.deleteLater()
    app.processEvents()
    return {"items": 1000, "set_data_elapsed_sec": elapsed}


def _benchmark_app_init(app):
    start = time.perf_counter()
    window = RealEstateApp()
    elapsed = time.perf_counter() - start

    if hasattr(window, "schedule_timer") and window.schedule_timer:
        window.schedule_timer.stop()
    if hasattr(window, "tray_icon") and window.tray_icon:
        window.tray_icon.hide()
    if hasattr(window, "db") and window.db:
        window.db.close()
    window.deleteLater()
    app.processEvents()
    return {"init_elapsed_sec": elapsed}


def main():
    ensure_directories()
    app = QApplication.instance() or QApplication([])

    results = {
        "timestamp": datetime.now().isoformat(),
        "parser": _benchmark_parser(),
        "cache": _benchmark_cache(),
        "card_render": _benchmark_card_render(app),
        "app_init": _benchmark_app_init(app),
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LOG_DIR / f"perf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Performance baseline")
    print(f"- parser throughput: {results['parser']['throughput_items_per_sec']:.2f} items/s")
    print(f"- cache set(100): {results['cache']['set_100_elapsed_sec']:.4f}s")
    print(f"- cache flush: {results['cache']['flush_elapsed_sec']:.4f}s")
    print(f"- card set_data(1000): {results['card_render']['set_data_elapsed_sec']:.4f}s")
    print(f"- app init: {results['app_init']['init_elapsed_sec']:.4f}s")
    print(f"- json: {out_path}")


if __name__ == "__main__":
    raise SystemExit(main())
