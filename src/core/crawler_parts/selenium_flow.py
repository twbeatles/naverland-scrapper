from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.crawler import *  # noqa: F403


class CrawlerSeleniumFlowMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
        self.start_time = time.time()
        self._engine = None
        try:
            self.log("🚀 크롤링 시작...")
            self._engine = self._create_engine()
            self._engine.run()
            self._flush_pending_items_if_needed(force=True)
            self._flush_history_updates(force=True)
            self.log(f"\n{'='*50}\n✅ 완료! 총 {len(self.collected_data)}건")
        except RetryCancelledError:
            self.log("⏹ 중단 요청으로 크롤링을 종료했습니다.", 20)
        except Exception as e:
            self.log(f"❌ 치명적 오류: {e}", 40)
            self.log(f"상세:\n{traceback.format_exc()}", 40)
            self.error_signal.emit(str(e))
        finally:
            self._flush_pending_items_if_needed(force=True)
            self._flush_history_updates(force=True)
            if self._engine is not None:
                try:
                    self._engine.close()
                except Exception as e:
                    self.log(f"⚠️ 엔진 종료 중 오류: {e}", 30)
            self.finished_signal.emit(self.collected_data)

    def _run_selenium_loop(self):
        if not UC_AVAILABLE or not BS4_AVAILABLE:
            self.error_signal.emit("필수 라이브러리 미설치\npip install undetected-chromedriver beautifulsoup4")
            return
            
        driver = None
        
        try:
            driver = self._init_driver()
            if not driver:
                raise Exception("드라이버 초기화 실패")
            
            allowed_pairs = self._fallback_allowed_pairs
            total = len(allowed_pairs) if allowed_pairs is not None else len(self.targets) * len(self.trade_types)
            if total <= 0:
                self.log("ℹ️ Selenium fallback 대상 pair가 없어 종료합니다.", 10)
                return
            current = 0
            processed_complexes = 0  # 처리한 단지 수
            processed_target_pairs = set()
            
            for name, cid in self.targets:
                if self._should_stop():
                    break
                
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
                    if not self._sleep_interruptible(1.0):
                        break
                    
                    driver = self._init_driver()
                    if not driver:
                        raise Exception("드라이버 재시작 실패")
                
                complex_count = 0
                complex_trade_types = []
                for ttype in self.trade_types:
                    if self._should_stop():
                        break
                    pair_key = self._pair_key(name, cid, ttype)
                    if allowed_pairs is not None and pair_key not in allowed_pairs:
                        continue
                    self._current_pair = pair_key
                    current += 1
                    
                    # 예상 남은 시간 계산
                    remaining = self._estimate_remaining_seconds(current, total)

                    self.progress_signal.emit(int(current / total * 100), f"{name} ({ttype})", remaining)
                    self.log(f"\\n📍 [{current}/{total}] {name} - {ttype}")
                    
                    try:
                        batch_result = self._crawl(driver, name, cid, ttype)
                        count = int(batch_result.get("count", 0))
                        complex_count += count
                        complex_trade_types.append(ttype)
                        if cid and ttype:
                            processed_target_pairs.add((str(cid), str(ttype)))
                        self.stats["by_trade_type"][ttype] = self.stats["by_trade_type"].get(ttype, 0) + count
                        self._mark_pair_processed(name, cid, ttype)
                        self.log(f"   ✅ {count}건 수집")
                    except RetryCancelledError:
                        self.log("   ⏹ 중단 요청으로 현재 작업을 종료합니다.", 20)
                        self.stop()
                        break
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
                    
                    if not self._sleep_interruptible(self._get_speed_delay()):
                        break

                self._flush_history_updates(force=True)
                if not complex_trade_types:
                    continue
                self.record_crawl_history(
                    name,
                    cid,
                    ",".join(complex_trade_types),
                    int(complex_count),
                    engine="selenium",
                    mode=self.crawl_mode,
                )
                
                self.complex_finished_signal.emit(name, cid, ",".join(complex_trade_types), complex_count)
                processed_complexes += 1

            self._finalize_disappeared_articles(processed_target_pairs)
        except RetryCancelledError:
            raise
        except Exception:
            raise
        finally:
            self._current_pair = None
            if driver:
                try:
                    driver.quit()
                    self.log("✅ Chrome 드라이버 종료 완료")
                except Exception as e:
                    self.log(f"⚠️ Chrome 드라이버 종료 중 오류: {e}", 30)
    
    def _crawl(self, driver, name, cid, ttype):
        # v12.0: 캐시 확인
        if self.cache:
            cached_items = self.cache.get(
                cid,
                ttype,
                mode=self.crawl_mode,
                asset_type="APT",
            )
            if cached_items is not None:
                self.log(f"   💾 캐시 히트! {len(cached_items)}건 로드")
                self.stats["cache_hits"] = self.stats.get("cache_hits", 0) + 1
                matched_count = 0
                for raw_item in cached_items:
                    if not isinstance(raw_item, dict):
                        continue
                    processed_item = self._enrich_item_with_history_and_alerts(dict(raw_item))
                    if self._check_filters(processed_item, ttype):
                        self._push_item(processed_item)
                        matched_count += 1
                    else:
                        self.stats["filtered_out"] += 1
                self._flush_history_updates(force=True)
                self._flush_pending_items_if_needed(force=True)
                return {"count": matched_count, "cache_hit": True, "raw_count": len(cached_items)}
        
        trade_param = {"매매": "A1", "전세": "B1", "월세": "B2"}.get(ttype, "A1")
        url = f"https://new.land.naver.com/complexes/{cid}?ms=37.5,127,16&a=APT&e=RETAIL&tradeTypes={trade_param}"

        try:
            parse_result = self.retry_handler.execute_with_retry(
                self._crawl_once,
                driver,
                name,
                cid,
                ttype,
                url,
                cancel_checker=self._should_stop,
            )
        except RetryCancelledError:
            raise
        except Exception as e:
            self.log(f"   ❌ {name}({ttype}) 크롤링 실패: {e}", 40)
            raise
        count = int(parse_result.get("count", 0))
        
        # v14.2: 필터 통과 여부와 무관하게 raw_items 캐시 저장
        if self.cache:
            raw_items = parse_result.get("raw_items", [])
            if raw_items:
                self.cache.set(
                    cid,
                    ttype,
                    raw_items,
                    mode=self.crawl_mode,
                    asset_type="APT",
                )
            else:
                negative_ttl_seconds = max(0, int(self.negative_cache_ttl_minutes * 60))
                if negative_ttl_seconds > 0:
                    self.cache.set(
                        cid,
                        ttype,
                        [],
                        ttl_seconds=negative_ttl_seconds,
                        mode=self.crawl_mode,
                        asset_type="APT",
                    )
        
        self._flush_history_updates(force=True)
        self._flush_pending_items_if_needed(force=True)
        return {
            "count": count,
            "cache_hit": False,
            "raw_count": int(parse_result.get("raw_count", 0)),
        }

    def _crawl_once(self, driver, name, cid, ttype, url):
        self.log("   🔗 URL 접속 중...")
        driver.get(url)
        self._assert_not_blocked_page(driver, context="초기 페이지")

        # v14.0: 동적 대기 - 페이지 로드 완료까지 대기
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(("css selector", ".article_list, .item_list, .complex_list, [class*='article']"))
            )
        except TimeoutException:
            self.log("   ⚠️ 매물 리스트 로드 대기 시간 초과, 계속 진행...", 30)
        self._assert_not_blocked_page(driver, context="목록 대기")

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

        self._assert_not_blocked_page(driver, context="탭 진입")
        self._scroll(driver)
        self._assert_not_blocked_page(driver, context="스크롤 완료")

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        return self._parse(soup, name, cid, ttype)

