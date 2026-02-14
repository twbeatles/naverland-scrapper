import time
import re
import random
import gc
import traceback
from PyQt6.QtCore import QThread, pyqtSignal

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from src.utils.constants import CRAWL_SPEED_PRESETS
from src.utils.helpers import AreaConverter, PriceConverter, PricePerPyeongCalculator, DateTimeHelper, ChromeParamHelper
from src.utils.logger import get_logger
from src.utils.retry_handler import RetryHandler
from src.core.item_parser import ItemParser

# 메모리 임계치 (MB) - 초과 시 드라이버 재시작
MEMORY_THRESHOLD_MB = 500

class CrawlerThread(QThread):
    log_signal = pyqtSignal(str, int)
    progress_signal = pyqtSignal(int, str, int)  # percent, current_name, remaining_seconds
    item_signal = pyqtSignal(dict)
    stats_signal = pyqtSignal(dict)
    complex_finished_signal = pyqtSignal(str, str, str, int)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    alert_triggered_signal = pyqtSignal(str, str, str, float, int)
    
    def __init__(self, targets, trade_types, area_filter, price_filter, db, speed="보통", cache=None):
        super().__init__()
        self.targets = targets
        self.trade_types = trade_types
        self.area_filter = area_filter
        self.price_filter = price_filter
        self.db = db
        self.speed = speed
        self.cache = cache  # v12.0: CrawlCache 인스턴스
        self._running = True
        self.collected_data = []
        self.stats = {"total_found": 0, "filtered_out": 0, "cache_hits": 0, "by_trade_type": {"매매": 0, "전세": 0, "월세": 0}}
        self.start_time = None
        self.items_per_second = 0
        self.retry_handler = RetryHandler()
    
    def stop(self): self._running = False
    def log(self, msg, level=20): self.log_signal.emit(msg, level)
    
    def _init_driver(self):
        """Chrome 드라이버 초기화 및 설정"""
        
        # Chrome 버전 자동 감지
        detected_version = ChromeParamHelper.get_chrome_major_version()
        version_msg = f" (감지된 버전: {detected_version})" if detected_version else " (버전 자동 감지)"
        self.log(f"🔧 Chrome 드라이버 초기화 중...{version_msg}")
        
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        options.add_argument("--log-level=3")
        
        driver = None
        try:
            # 감지된 버전이 있으면 해당 버전 사용, 없으면 None (최신/자동)
            driver = uc.Chrome(options=options, version_main=detected_version)
            self.log("✅ Chrome 드라이버 초기화 성공")
        except Exception as e:
            self.log(f"⚠️ Headless 실패, 일반 모드 시도... ({e})", 30)
            options2 = uc.ChromeOptions()
            options2.add_argument("--no-sandbox")
            options2.add_argument("--disable-dev-shm-usage")
            options2.add_argument("--disable-gpu")
            options2.add_argument("--window-size=1920,1080")
            options2.add_argument("--start-minimized")
            driver = uc.Chrome(options=options2, version_main=detected_version)
            self.log("✅ Chrome 드라이버 초기화 성공 (일반 모드)")
        
        if driver:
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(5)
            
        return driver

    def run(self):
        if not UC_AVAILABLE or not BS4_AVAILABLE:
            self.error_signal.emit("필수 라이브러리 미설치\npip install undetected-chromedriver beautifulsoup4")
            return
            
        driver = None
        self.start_time = time.time()
        
        try:
            self.log("🚀 크롤링 시작...")
            driver = self._init_driver()
            if not driver:
                raise Exception("드라이버 초기화 실패")
            
            total = len(self.targets) * len(self.trade_types)
            current = 0
            processed_complexes = 0  # 처리한 단지 수
            
            for name, cid in self.targets:
                if not self._running: break
                
                # v14.0: 메모리 기반 드라이버 재시작 (500MB 임계치)
                should_restart = False
                if PSUTIL_AVAILABLE:
                    memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
                    if memory_mb > MEMORY_THRESHOLD_MB:
                        should_restart = True
                        self.log(f"🔄 메모리 사용량 {memory_mb:.0f}MB 초과, 드라이버 재시작...")
                else:
                    # psutil 미설치 시 기존 방식 (3단지마다)
                    if processed_complexes > 0 and processed_complexes % 3 == 0:
                        should_restart = True
                        self.log("🔄 Chrome 드라이버 재시작 (메모리 정리)...")
                
                if should_restart:
                    try:
                        driver.quit()
                    except Exception as e:
                        self.log(f"⚠️ 드라이버 종료 실패 (무시): {e}", 30)
                    driver = None
                    gc.collect()
                    time.sleep(1)
                    
                    driver = self._init_driver()
                    if not driver:
                        raise Exception("드라이버 재시작 실패")
                
                complex_count = 0
                for ttype in self.trade_types:
                    if not self._running: break
                    current += 1
                    
                    # 예상 남은 시간 계산
                    elapsed = time.time() - self.start_time
                    avg_time = elapsed / current if current > 0 else 5
                    remaining = int(avg_time * (total - current))
                    
                    self.progress_signal.emit(int(current / total * 100), f"{name} ({ttype})", remaining)
                    self.log(f"\\n📍 [{current}/{total}] {name} - {ttype}")
                    
                    try:
                        count = self._crawl(driver, name, cid, ttype)
                        complex_count += count
                        self.stats["by_trade_type"][ttype] = self.stats["by_trade_type"].get(ttype, 0) + count
                        self.log(f"   ✅ {count}건 수집")
                    except Exception as e:
                        self.log(f"   ❌ 오류: {e}", 40)
                        self.log(f"   상세: {traceback.format_exc()}", 40)
                        
                        # 치명적 오류(세션 종료 등) 발생 시 드라이버 재시작 시도
                        if "SessionNotCreatedException" in str(e) or "NoSuchWindowException" in str(e) or "WebDriverException" in str(e):
                             self.log("⚠️ 드라이버 세션 오류 감지, 재시작 시도...", 30)
                             try:
                                 driver.quit()
                             except Exception as quit_err:
                                 self.log(f"⚠️ 드라이버 종료 실패 (무시): {quit_err}", 30)
                             driver = self._init_driver()
                    
                    speed_cfg = CRAWL_SPEED_PRESETS.get(self.speed, CRAWL_SPEED_PRESETS["보통"])
                    time.sleep(random.uniform(speed_cfg["min"], speed_cfg["max"]))
                
                self.complex_finished_signal.emit(name, cid, ",".join(self.trade_types), complex_count)
                processed_complexes += 1
            
            self.log(f"\\n{'='*50}\\n✅ 완료! 총 {len(self.collected_data)}건")
        except Exception as e:
            self.log(f"❌ 치명적 오류: {e}", 40)
            self.log(f"상세:\\n{traceback.format_exc()}", 40)
            self.error_signal.emit(str(e))
        finally:
            if driver:
                try:
                    driver.quit()
                    self.log("✅ Chrome 드라이버 종료 완료")
                except Exception as e:
                    self.log(f"⚠️ Chrome 드라이버 종료 중 오류: {e}", 30)
            self.finished_signal.emit(self.collected_data)
    
    def _crawl(self, driver, name, cid, ttype):
        # v12.0: 캐시 확인
        if self.cache:
            cached_items = self.cache.get(cid, ttype)
            if cached_items:
                self.log(f"   💾 캐시 히트! {len(cached_items)}건 로드")
                self.stats["cache_hits"] = self.stats.get("cache_hits", 0) + 1
                # 캐시된 아이템을 collected_data에 추가하고 시그널 발송
                for item in cached_items:
                    if self._check_filters(item, ttype):
                        self.collected_data.append(item)
                        self.item_signal.emit(item)
                        self.stats["total_found"] += 1
                    else:
                        self.stats["filtered_out"] += 1
                self.stats_signal.emit(self.stats)
                return len([i for i in cached_items if self._check_filters(i, ttype)])
        
        trade_param = {"매매": "A1", "전세": "B1", "월세": "B2"}.get(ttype, "A1")
        url = f"https://new.land.naver.com/complexes/{cid}?ms=37.5,127,16&a=APT&e=RETAIL&tradeTypes={trade_param}"
        
        self.log(f"   🔗 URL 접속 중...")
        try:
            self.retry_handler.execute_with_retry(driver.get, url)
        except Exception as e:
            self.log(f"   ❌ URL 접속 실패: {e}", 40)
            return 0
        
        # v14.0: 동적 대기 - 페이지 로드 완료까지 대기
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(("css selector", ".article_list, .item_list, .complex_list, [class*='article']"))
            )
        except TimeoutException:
            self.log("   ⚠️ 매물 리스트 로드 대기 시간 초과, 계속 진행...", 30)
        
        try:
            article_tab = driver.find_element("css selector", "a[href*='articleList'], .tab_item[data-tab='article']")
            article_tab.click()
            # v14.0: 탭 클릭 후 동적 대기
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(("css selector", ".item_article, .item_inner"))
                )
            except TimeoutException:
                self.log("   ℹ️ 매물 탭 로드 대기 시간 초과 (무시)", 10)
        except (NoSuchElementException, Exception) as e:
            # 탭 클릭 실패는 정상적인 상황일 수 있음 (탭이 없는 경우)
            self.log(f"   ℹ️ 매물 탭 찾기 실패 (정상): {type(e).__name__}", 10)
        
        self._scroll(driver)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        count = self._parse(soup, name, cid, ttype)
        
        # v12.0: 크롤링 결과 캐시 저장
        if self.cache and count > 0:
            # 이 단지+거래유형의 아이템만 필터링해서 캐시
            items_to_cache = [
                d for d in self.collected_data 
                if d.get("단지ID") == cid and d.get("거래유형") == ttype
            ]
            if items_to_cache:
                self.cache.set(cid, ttype, items_to_cache)
        
        return count
    
    def _scroll(self, driver):
        """v14.0: 컨텐츠 변화 감지 기반 최적화된 스크롤"""
        try:
            # 컨텐츠 아이템 수 기반 스크롤 (더 효율적)
            selectors = ".item_article, .item_inner, .article_item, [class*='ArticleItem']"
            last_count = 0
            stable_count = 0
            max_scroll_attempts = 15  # 최대 스크롤 횟수
            
            for _ in range(max_scroll_attempts):
                if not self._running:
                    break
                
                # 현재 아이템 수 확인
                try:
                    items = driver.find_elements("css selector", selectors)
                    current_count = len(items)
                except Exception:
                    current_count = 0
                
                # 아이템 수가 변하지 않으면 카운트 증가
                if current_count == last_count:
                    stable_count += 1
                    if stable_count >= 2:  # 2번 연속 변화 없으면 종료
                        break
                else:
                    stable_count = 0
                    last_count = current_count
                
                # 스크롤 실행
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.8)  # 최소 대기 (네트워크 요청 시간 고려)
                
        except Exception as e:
            self.log(f"   ⚠️ 스크롤 오류: {e}", 30)
    
    def _parse(self, soup, name, cid, ttype):
        items = []
        found_items = ItemParser.find_items(soup)
        
        if found_items:
            # 선택자 로깅 (ItemParser 내부 디버그 로그와 별개로 사용자에게 진행상황 표시)
            self.log(f"   🔍 파싱 대상: {len(found_items)}개")
        else:
            self.log("   ⚠️ 파싱 대상 항목을 찾지 못했습니다.", 10)
            return 0
        
        matched_count, skipped_type = 0, 0
        
        for item in found_items:
            if not self._running: break
            try:
                data = ItemParser.parse_element(item, name, cid, ttype)
                if data and data.get("면적(㎡)", 0) > 0:
                    detected_type = data.get("거래유형", "")
                    if detected_type == ttype:
                        if self._check_filters(data, ttype):
                            self.collected_data.append(data)
                            self.item_signal.emit(data)
                            items.append(data)
                            self.stats["total_found"] += 1
                            matched_count += 1
                        else:
                            self.stats["filtered_out"] += 1
                        self.stats_signal.emit(self.stats)
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
            price_range = self.price_filter.get(ttype, {})
            min_p, max_p = price_range.get("min", 0), price_range.get("max", 999999)
            if ttype == "매매": price = PriceConverter.to_int(data.get("매매가", "0"))
            else: price = PriceConverter.to_int(data.get("보증금", "0"))
            if price < min_p or price > max_p: return False
        return True
