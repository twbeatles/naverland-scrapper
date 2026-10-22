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
        from src.core.services.site_contract import DESKTOP_USER_AGENT

        self._page = self._browser.new_page(locale="ko-KR", user_agent=DESKTOP_USER_AGENT)
        try:
            self._page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
        except Exception:
            pass
        return self._page

    def _resolve_via_fin_api(self, page, aid: str) -> dict:
        """fin ``/search/articles?articleNumber=`` -> complexNumber (live 2026-10-22).

        The call must run in-page on a fin.land origin; out-of-browser requests get 429.
        """
        from src.core.services.site_contract import FIN_API_ORIGIN_PAGE, FRONT_API_BASE

        try:
            if not str(getattr(page, "url", "") or "").startswith("https://fin.land.naver.com/"):
                page.goto(FIN_API_ORIGIN_PAGE, wait_until="domcontentloaded", timeout=8000)
            url = f"{FRONT_API_BASE}/search/articles?articleNumber={aid}&userChannelType=PC"
            result = page.evaluate(
                """(url) => fetch(url, {headers: {accept: 'application/json'}})
                    .then(async (r) => ({status: r.status, body: await r.text()}))
                    .catch(() => ({status: 0, body: ''}))""",
                url,
            )
            if not isinstance(result, dict) or int(result.get("status", 0) or 0) != 200:
                return {}
            payload = json.loads(str(result.get("body", "") or ""))
        except Exception as e:
            self._logger.debug(f"매물 단지 fin API 조회 실패 ({aid}): {e}")
            return {}
        article = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(article, dict):
            return {}
        cid = str(article.get("complexNumber", "") or "").strip()
        if not cid:
            return {}
        from src.core.services.fin_article_api import fin_article_to_legacy

        asset = str(fin_article_to_legacy(article).get("realEstateTypeCode", "") or "APT")
        return {
            "source": "fin_search_articles:browser_fallback",
            "complex_id": cid,
            "asset_type": asset,
            "article_id": aid,
            "url": url,
        }

    def resolve(self, article_id, *, cancel_checker=None, fallback_asset_type="APT"):
        aid = str(article_id or "").strip()
        if not aid:
            return {}
        page = self._ensure_page()
        if page is None:
            return {}
        resolved = self._resolve_via_fin_api(page, aid)
        if resolved:
            return resolved
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
