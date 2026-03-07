from __future__ import annotations


class CrawlerDomScrollParseMixin:
    def _detect_block_signal(self, title, page_source):
        title_lower = str(title or "").lower()
        source_lower = str(page_source or "").lower()
        source_head = source_lower[:20000]
        haystack = f"{title_lower}\n{source_head}"
        for pattern in self.BLOCKED_PAGE_PATTERNS:
            if pattern in haystack:
                return pattern
        return None

    def _assert_not_blocked_page(self, driver, context=""):
        try:
            title = driver.title
        except Exception:
            title = ""
        try:
            page_source = driver.page_source
        except Exception:
            page_source = ""

        signal = self._detect_block_signal(title, page_source)
        if signal:
            ctx = f" ({context})" if context else ""
            self.log(f"   ⚠️ 차단/방어 페이지 감지{ctx}: {signal}", 30)
            raise RuntimeError(f"temporary blocked page detected{ctx}: {signal}")

    def _get_item_state(self, driver, selectors):
        script = """
            const selector = arguments[0];
            const nodes = Array.from(document.querySelectorAll(selector));
            const ids = [];
            for (const node of nodes) {
                let id =
                    node.getAttribute('data-article-id') ||
                    node.getAttribute('data-id') ||
                    node.getAttribute('id') ||
                    '';
                if (!id) {
                    const anchor = node.querySelector("a[href*='articleId=']");
                    if (anchor) {
                        const href = anchor.getAttribute('href') || '';
                        const m = href.match(/articleId=(\\d+)/);
                        if (m) {
                            id = m[1];
                        }
                    }
                }
                if (id) {
                    ids.push(String(id));
                }
            }
            return {count: nodes.length, ids: ids};
        """
        try:
            state = driver.execute_script(script, selectors) or {}
        except Exception:
            return 0, set()
        count = int(state.get("count", 0) or 0)
        raw_ids = state.get("ids", [])
        if not isinstance(raw_ids, list):
            raw_ids = []
        return count, {str(x) for x in raw_ids if x is not None}

    def _detect_scroll_container(self, driver):
        script = """
            const candidates = [];
            const seedSelectors = [
                '.article_list',
                '.item_list',
                '.list_contents',
                '[class*="article_list"]',
                '[class*="item_list"]',
                '[class*="ArticleList"]',
                '[class*="List"]'
            ];
            for (const sel of seedSelectors) {
                candidates.push(...Array.from(document.querySelectorAll(sel)));
            }
            if (candidates.length === 0) {
                candidates.push(...Array.from(document.querySelectorAll('div, section, ul')));
            }
            let best = null;
            let bestScroll = 0;
            for (const el of candidates.slice(0, 400)) {
                const style = window.getComputedStyle(el);
                const overflowY = style.overflowY || '';
                if (!(overflowY.includes('auto') || overflowY.includes('scroll'))) {
                    continue;
                }
                const scrollGap = el.scrollHeight - el.clientHeight;
                if (scrollGap > 40 && scrollGap > bestScroll) {
                    best = el;
                    bestScroll = scrollGap;
                }
            }
            window.__naver_scroll_container = best;
            return !!best;
        """
        try:
            return bool(driver.execute_script(script))
        except Exception:
            return False

    def _scroll_once(self, driver, use_container):
        if use_container:
            script = """
                const container = window.__naver_scroll_container;
                if (container) {
                    container.scrollTop = container.scrollHeight;
                    return true;
                }
                return false;
            """
            try:
                if bool(driver.execute_script(script)):
                    return True
            except Exception:
                pass
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        return False
    
    def _scroll(self, driver):
        """v14.2: 내부 컨테이너 우선 + window 폴백 스크롤"""
        try:
            selectors = ".item_article, .item_inner, .article_item, [class*='ArticleItem']"
            seen_ids = set()
            last_count = -1
            stable_count = 0
            max_scroll_attempts = 18
            use_container = self._detect_scroll_container(driver)
            if use_container:
                self.log("   ℹ️ 내부 스크롤 컨테이너 감지, 컨테이너 스크롤 우선 적용", 10)
            
            for _ in range(max_scroll_attempts):
                if self._should_stop():
                    break

                current_count, current_ids = self._get_item_state(driver, selectors)
                new_ids = current_ids - seen_ids
                seen_ids.update(current_ids)

                if current_count == last_count and not new_ids:
                    stable_count += 1
                    if stable_count >= 2:
                        break
                else:
                    stable_count = 0
                    last_count = current_count

                used_container = self._scroll_once(driver, use_container=use_container)
                if use_container and not used_container:
                    self.log("   ℹ️ 내부 컨테이너 스크롤 실패, window 스크롤로 폴백", 10)
                    use_container = False

                if not self._sleep_interruptible(0.8):
                    break
                
        except Exception as e:
            self.log(f"   ⚠️ 스크롤 오류: {e}", 30)
    
    def _parse(self, soup, name, cid, ttype):
        raw_items = []
        found_items = ItemParser.find_items(soup)
        
        if found_items:
            # 선택자 로깅 (ItemParser 내부 디버그 로그와 별개로 사용자에게 진행상황 표시)
            self.log(f"   🔍 파싱 대상: {len(found_items)}개")
        else:
            self.log("   ⚠️ 파싱 대상 항목을 찾지 못했습니다.", 10)
            return {"count": 0, "raw_items": [], "raw_count": 0}
        
        matched_count, skipped_type = 0, 0
        
        for item in found_items:
            if self._should_stop():
                break
            try:
                data = ItemParser.parse_element(item, name, cid, ttype)
                if data and data.get("면적(㎡)", 0) > 0:
                    detected_type = data.get("거래유형", "")
                    if detected_type == ttype:
                        raw_items.append(dict(data))
                        enriched = self._enrich_item_with_history_and_alerts(data)
                        if self._check_filters(enriched, ttype):
                            self._push_item(enriched)
                            matched_count += 1
                        else:
                            self.stats["filtered_out"] += 1
                    else:
                        skipped_type += 1
            except Exception as e:
                self.log(f"   ⚠️ 항목 파싱 중 오류: {e}", 30)
        
        if skipped_type > 0:
            self.log(f"   ℹ️ 다른 거래유형 {skipped_type}건 제외 (요청: {ttype})")
        
        return {
            "count": matched_count,
            "raw_items": raw_items,
            "raw_count": len(found_items),
        }

        
    def _check_filters(self, data, ttype):
        if self.area_filter.get("enabled"):
            sqm = data.get("면적(㎡)", 0)
            if sqm < self.area_filter.get("min", 0) or sqm > self.area_filter.get("max", 999):
                return False
        if self.price_filter.get("enabled"):
            price_range = self.price_filter.get(ttype, {}) or {}
            if ttype == "매매":
                min_p = price_range.get("min", 0)
                max_p = price_range.get("max", 999999)
                price = PriceConverter.to_int(data.get("매매가", "0"))
                if price < min_p or price > max_p:
                    return False
            elif ttype == "월세":
                deposit_min = price_range.get("deposit_min", price_range.get("min", 0))
                deposit_max = price_range.get("deposit_max", price_range.get("max", 999999))
                rent_min = price_range.get("rent_min", price_range.get("min", 0))
                rent_max = price_range.get("rent_max", price_range.get("max", 999999))
                deposit = PriceConverter.to_int(data.get("보증금", "0"))
                monthly_rent = PriceConverter.to_int(data.get("월세", "0"))
                if deposit < deposit_min or deposit > deposit_max:
                    return False
                if monthly_rent < rent_min or monthly_rent > rent_max:
                    return False
            else:
                min_p = price_range.get("min", 0)
                max_p = price_range.get("max", 999999)
                price = PriceConverter.to_int(data.get("보증금", "0"))
                if price < min_p or price > max_p:
                    return False
        return True
