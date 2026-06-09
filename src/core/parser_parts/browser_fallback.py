import json
import re
import time
import urllib.request
from html import unescape
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError

from src.utils.logger import get_logger
from src.utils.retry_handler import RetryCancelledError

logger = get_logger("Parser")


class ArticleLookupBrowserFallbackSession:

    def __init__(self, parser_cls=None):
        if parser_cls is None:
            from src.core.parser import NaverURLParser

            parser_cls = NaverURLParser
        self._parser_cls = parser_cls
        self._playwright = None
        self._browser = None
        self._page = None
        self._logger = get_logger("NaverURLParser")

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            self._logger.debug(f"매물 단지 browser fallback 사용 불가: {e}")
            return None
        self._playwright = sync_playwright().start()
        chrome_path = ""
        try:
            from src.utils.helpers import ChromeParamHelper

            chrome_path = ChromeParamHelper.get_chrome_executable_path()
        except Exception as e:
            self._logger.debug(f"매물 단지 browser fallback Chrome 경로 확인 실패: {e}")
        if chrome_path:
            try:
                self._browser = self._playwright.chromium.launch(
                    executable_path=chrome_path,
                    headless=True,
                )
            except Exception as e:
                self._logger.debug(f"매물 단지 browser fallback local Chrome 실행 실패: {e}")
                self._browser = self._playwright.chromium.launch(headless=True)
        else:
            self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page(
            locale="ko-KR",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )
        try:
            self._page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
        except Exception:
            pass
        return self._page

    def resolve(self, article_id, *, cancel_checker=None, fallback_asset_type="APT"):
        aid = str(article_id or "").strip()
        if not aid:
            return {}
        page = self._ensure_page()
        if page is None:
            return {}
        for source, url in self._parser_cls._article_lookup_urls(aid):
            if self._parser_cls._is_cancelled(cancel_checker):
                raise RetryCancelledError("article lookup cancelled during browser fallback")
            captured_artifacts: list[str] = []

            def _capture_response(response):
                try:
                    response_url = str(getattr(response, "url", "") or "")
                    if response_url:
                        captured_artifacts.append(response_url)
                except Exception:
                    pass

            can_listen = hasattr(page, "on") and hasattr(page, "remove_listener")
            if can_listen:
                try:
                    page.on("response", _capture_response)
                except Exception:
                    can_listen = False
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=8000)
                try:
                    page.wait_for_load_state("networkidle", timeout=2000)
                except Exception:
                    pass
                body = ""
                try:
                    body = page.inner_text("body", timeout=1000)
                except Exception:
                    pass
                try:
                    content = page.content()
                except Exception:
                    content = ""
                cid, asset_type = self._parser_cls._extract_article_complex_info(
                    f"{body}\n{content}\n" + "\n".join(captured_artifacts),
                    fallback_asset_type=fallback_asset_type,
                )
                if cid:
                    return {
                        "source": f"{source}:browser_fallback",
                        "complex_id": cid,
                        "asset_type": asset_type,
                        "article_id": aid,
                        "url": url,
                    }
            except RetryCancelledError:
                raise
            except Exception as e:
                self._logger.debug(f"매물 단지 browser fallback 실패 ({source}:{aid}): {e}")
                continue
            finally:
                if can_listen:
                    try:
                        page.remove_listener("response", _capture_response)
                    except Exception:
                        pass
        return {}

    def close(self):
        try:
            if self._page is not None:
                self._page.close()
        except Exception:
            pass
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._browser = None
        self._playwright = None
