import time
import random
from threading import Lock
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.config import CRAWL_SPEED_PRESETS

# 메모리 보호를 위한 최대 수집 한도
MAX_COLLECTED_ITEMS = 10000
from src.crawler.driver import initialize_driver, setup_driver_settings, cleanup_driver
from src.crawler.parser import PageParser
from src.crawler.cache import CrawlCache
from src.crawler.handler import RetryHandler
from src.utils.logger import get_logger

class CrawlerThread(QThread):
    log_signal = pyqtSignal(str, int)
    progress_signal = pyqtSignal(int, str, int)  # percent, current_name, remaining_seconds
    item_signal = pyqtSignal(dict)
    stats_signal = pyqtSignal(dict)
    complex_finished_signal = pyqtSignal(str, str, str, int)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    alert_triggered_signal = pyqtSignal(str, str, str, float, int)
    
    def __init__(self, targets, trade_types, area_filter, price_filter, db, speed="보통", cache=None, retry_handler=None):
        super().__init__()
        self.targets = targets
        self.trade_types = trade_types
        self.area_filter = area_filter
        self.price_filter = price_filter
        self.db = db
        self.speed = speed
        self.cache = cache if cache else CrawlCache()
        self.retry_handler = retry_handler if retry_handler else RetryHandler()
        self._running = True
        self._lock = Lock()  # Thread safety for shared data
        self.collected_data = []
        self.stats = {"total_found": 0, "filtered_out": 0, "cache_hits": 0, "by_trade_type": {"매매": 0, "전세": 0, "월세": 0}}
        self.start_time = None
        self._driver = None  # Store driver reference for cleanup
    
    def stop(self):
        """Graceful shutdown - 현재 작업 완료 후 안전하게 중단"""
        self._running = False
        self.log("⏹️ 중단 요청됨. 현재 작업 완료 후 종료합니다...", 30)
    def log(self, msg, level=20): self.log_signal.emit(msg, level)
    
    def run(self):
        # BeautifulSoup 미설치 시 조기 종료
        if not BS4_AVAILABLE:
            self.error_signal.emit("BeautifulSoup 라이브러리가 설치되지 않았습니다. 'pip install beautifulsoup4' 명령으로 설치해주세요.")
            self.finished_signal.emit([])
            return
        
        driver = None
        try:
            driver = initialize_driver()
            driver = setup_driver_settings(driver)
            self._driver = driver  # Store reference
        except Exception as e:
            self.error_signal.emit(str(e))
            return

        self.start_time = time.time()
        
        try:
            self.log("🚀 크롤링 시작...")
            
            total = len(self.targets) * len(self.trade_types)
            current = 0
            
            for name, cid in self.targets:
                if not self._running: break
                complex_count = 0
                for ttype in self.trade_types:
                    if not self._running: break
                    current += 1
                    
                    # 예상 남은 시간 계산
                    elapsed = time.time() - self.start_time
                    avg_time = elapsed / current if current > 0 else 5
                    remaining = int(avg_time * (total - current))
                    
                    self.progress_signal.emit(int(current / total * 100), f"{name} ({ttype})", remaining)
                    self.log(f"\n📍 [{current}/{total}] {name} - {ttype}")
                    
                    try:
                        count, needs_reinit = self._crawl(driver, name, cid, ttype)
                        if needs_reinit:
                            self.log("   🔄 드라이버 재초기화 중...", 30)
                            cleanup_driver(driver, force_kill=True)
                            try:
                                driver = initialize_driver()
                                driver = setup_driver_settings(driver)
                                self._driver = driver
                                self.log("   ✅ 드라이버 재초기화 성공")
                                # 재시도
                                count, _ = self._crawl(driver, name, cid, ttype)
                            except Exception as reinit_err:
                                self.log(f"   ❌ 드라이버 재초기화 실패: {reinit_err}", 40)
                                count = 0
                        complex_count += count
                        self.stats["by_trade_type"][ttype] = self.stats["by_trade_type"].get(ttype, 0) + count
                        self.log(f"   ✅ {count}건 수집")
                    except Exception as e:
                        self.log(f"   ❌ 오류: {e}", 40)
                        import traceback
                        self.log(f"   상세: {traceback.format_exc()}", 40)
                    
                    speed_cfg = CRAWL_SPEED_PRESETS.get(self.speed, CRAWL_SPEED_PRESETS["보통"])
                    time.sleep(random.uniform(speed_cfg["min"], speed_cfg["max"]))
                
                self.complex_finished_signal.emit(name, cid, ",".join(self.trade_types), complex_count)
            
            self.log(f"\n{'='*50}\n✅ 완료! 총 {len(self.collected_data)}건")
        except Exception as e:
            self.log(f"❌ 치명적 오류: {e}", 40)
            self.error_signal.emit(str(e))
        finally:
            # 강화된 드라이버 정리 로직
            if driver:
                success = cleanup_driver(driver, force_kill=True)
                if success:
                    self.log("✅ Chrome 드라이버 종료 완료")
                else:
                    self.log("⚠️ Chrome 드라이버 종료 실패 - 수동 정리 필요할 수 있음", 30)
            self._driver = None
            
            # Thread-safe하게 결과 전달
            with self._lock:
                result_data = self.collected_data.copy()
            self.finished_signal.emit(result_data)
    
    def _crawl(self, driver, name, cid, ttype):
        # driver 상태 검증
        if driver is None:
            self.log("   ❌ 드라이버가 초기화되지 않았습니다.", 40)
            return 0, True
        try:
            # 세션 유효성 확인
            _ = driver.current_url
        except Exception as e:
            self.log(f"   ❌ 드라이버 세션이 유효하지 않습니다: {e}", 40)
            return 0, True
        
        if self.cache:
            cached_items = self.cache.get(cid, ttype)
            if cached_items:
                self.log(f"   💾 캐시 히트! {len(cached_items)}건 로드")
                self.stats["cache_hits"] = self.stats.get("cache_hits", 0) + 1
                for item in cached_items:
                    if self._check_filters(item, ttype):
                        with self._lock:
                            self.collected_data.append(item)
                            self.stats["total_found"] += 1
                        self.item_signal.emit(item)
                    else:
                        with self._lock:
                            self.stats["filtered_out"] += 1
                with self._lock:
                    self.stats_signal.emit(self.stats.copy())
                return len([i for i in cached_items if self._check_filters(i, ttype)]), False
        
        trade_param = {"매매": "A1", "전세": "B1", "월세": "B2"}.get(ttype, "A1")
        url = f"https://new.land.naver.com/complexes/{cid}?ms=37.5,127,16&a=APT&e=RETAIL&tradeTypes={trade_param}"
        
        self.log(f"   🔗 URL 접속 중...")
        
        def load_page():
            driver.get(url)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#complexOverviewList, .complex_overview_list, .detail_contents"))
                )
            except Exception:
                pass
        
        if self.retry_handler:
            try:
                self.retry_handler.execute_with_retry(load_page)
            except Exception as e:
                self.log(f"   ⚠️ 페이지 로드 재시도 실패: {e}", 30)
                driver.get(url)
                time.sleep(3)
        else:
            driver.get(url)
            time.sleep(3)
        
        try:
            wait = WebDriverWait(driver, 5)
            article_tab = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='articleId'], .tab_item[data-tab='article']")))
            article_tab.click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".article_list, .item_list, .complex_list")))
        except Exception as e:
            pass
        
        self._scroll(driver)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        count = self._parse(soup, name, cid, ttype)
        
        if self.cache and count > 0:
            items_to_cache = [
                d for d in self.collected_data 
                if d.get("단지ID") == cid and d.get("거래유형") == ttype
            ]
            if items_to_cache:
                self.cache.set(cid, ttype, items_to_cache)
        
        return count, False
    
    def _scroll(self, driver):
        try:
            container = None
            for sel in [".article_list", ".item_list", ".complex_list", "[class*='article']"]:
                try:
                    container = driver.find_element(By.CSS_SELECTOR, sel)
                    if container: break
                except Exception:
                    continue
            
            if not container:
                last_h = 0
                for _ in range(5):
                    if not self._running: break
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(0.5)
                    new_h = driver.execute_script("return document.body.scrollHeight")
                    if new_h == last_h: break
                    last_h = new_h
                return
            
            last_height = driver.execute_script("return arguments[0].scrollHeight", container)
            attempts = 0
            max_attempts = 10
            
            while self._running:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", container)
                time.sleep(0.5)
                new_height = driver.execute_script("return arguments[0].scrollHeight", container)
                
                if new_height == last_height:
                    attempts += 1
                    if attempts >= max_attempts:
                        break
                    time.sleep(0.5)
                else:
                    attempts = 0
                    last_height = new_height
        except Exception as e:
            self.log(f"   ⚠️ 스크롤 오류: {e}", 30)
    
    def _parse(self, soup, name, cid, ttype):
        items = []
        article_items = []
        
        for sel in [".item_article", ".item_inner", ".article_item", "[class*='ArticleItem']", ".complex_item", "li[data-article-id]", ".list_item"]:
            found = soup.select(sel)
            if found:
                article_items = found
                self.log(f"   📋 선택자 '{sel}': {len(found)}개 발견")
                break
        
        if not article_items:
            self.log("   ⚠️ 표준 선택자 실패, 대체 방식 시도...")
            article_items = soup.find_all(['div', 'li'], class_=lambda x: x and ('item' in x.lower() or 'article' in x.lower()))
        
        self.log(f"   🔍 파싱 대상: {len(article_items)}개")
        
        matched_count, skipped_type = 0, 0
        
        for item in article_items:
            if not self._running: break
            try:
                data = PageParser.parse_item(item, name, cid, ttype)
                if data and data.get("면적(㎡)", 0) > 0:
                    detected_type = data.get("거래유형", "")
                    if detected_type == ttype:
                        if self._check_filters(data, ttype):
                            with self._lock:
                                # 메모리 보호: 최대 수집 한도 체크
                                if len(self.collected_data) >= MAX_COLLECTED_ITEMS:
                                    self.log(f"⚠️ 최대 수집 한도({MAX_COLLECTED_ITEMS}건) 도달. 수집 중단.", 30)
                                    return matched_count
                                self.collected_data.append(data)
                                self.stats["total_found"] += 1
                            self.item_signal.emit(data)
                            items.append(data)
                            matched_count += 1
                        else:
                            with self._lock:
                                self.stats["filtered_out"] += 1
                        with self._lock:
                            self.stats_signal.emit(self.stats.copy())
                    else:
                        skipped_type += 1
            except Exception as e:
                self.log(f"   ⚠️ 항목 파싱 중 오류: {e}", 30)
        
        if skipped_type > 0:
            self.log(f"   ℹ️ 다른 거래유형 {skipped_type}건 제외 (요청: {ttype})")
        
        return matched_count
    
    def _check_filters(self, data, ttype):
        if self.area_filter.get("enabled"):
            sqm = data.get("면적(㎡)", 0)
            if sqm < self.area_filter.get("min", 0) or sqm > self.area_filter.get("max", 999):
                return False
        if self.price_filter.get("enabled"):
            from src.utils.converters import PriceConverter
            price_range = self.price_filter.get(ttype, {})
            min_p, max_p = price_range.get("min", 0), price_range.get("max", 999999)
            
            # 가격 변환 (단일 로직으로 통일)
            if ttype == "매매":
                price = PriceConverter.to_int(data.get("매매가", "0"))
            else:
                price = PriceConverter.to_int(data.get("보증금", "0"))
            
            if price < min_p or price > max_p:
                return False
        return True

