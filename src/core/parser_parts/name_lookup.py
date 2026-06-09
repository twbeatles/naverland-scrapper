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
from src.core.parser_parts.contracts import runtime_contract


class NaverNameLookupMixin:

    @classmethod
    def _name_cache_key(cls, complex_id, asset_type="APT") -> str:
        return f"{runtime_contract(cls)._normalize_asset_type(asset_type)}:{str(complex_id or '').strip()}"

    @classmethod
    def _fetch_name_impl(cls, complex_id, asset_type="APT"):
        """네이버 API를 호출해 단지명을 조회한다."""
        asset_token = runtime_contract(cls)._normalize_asset_type(asset_type)
        entity_path = "houses" if asset_token == "VL" else "complexes"
        url = f"https://new.land.naver.com/api/{entity_path}/{complex_id}?sameAddressGroup=false"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            detail = data.get("complexDetail", {}) if isinstance(data, dict) else {}
            name_candidates = (
                detail.get("complexName"),
                detail.get("name"),
                data.get("complexName") if isinstance(data, dict) else "",
                data.get("name") if isinstance(data, dict) else "",
            )
            for candidate in name_candidates:
                token = str(candidate or "").strip()
                if token:
                    return token
            return f"단지_{complex_id}"

    @classmethod
    def _fetch_name_browser_fallback(cls, complex_id, asset_type="APT", cancel_checker=None):
        cid = str(complex_id or "").strip()
        if not cid or cls._is_cancelled(cancel_checker):
            return ""
        try:
            from playwright.sync_api import sync_playwright

            from src.utils.helpers import build_complex_url, ChromeParamHelper
        except Exception as e:
            get_logger("NaverURLParser").debug(f"단지명 browser fallback 사용 불가: {e}")
            return ""

        asset_token = runtime_contract(cls)._normalize_asset_type(asset_type)
        expected_entity = "houses" if asset_token == "VL" else "complexes"
        expected_detail = f"/api/{expected_entity}/{cid}"
        expected_articles = f"/api/articles/{'house' if asset_token == 'VL' else 'complex'}/{cid}"
        captured_name = ""

        def _extract_name_from_payload(payload) -> str:
            if not isinstance(payload, dict):
                return ""
            detail = payload.get("complexDetail", {}) if isinstance(payload, dict) else {}
            candidates = (
                detail.get("complexName") if isinstance(detail, dict) else "",
                detail.get("name") if isinstance(detail, dict) else "",
                payload.get("complexName"),
                payload.get("name"),
            )
            for candidate in candidates:
                token = str(candidate or "").strip()
                if token:
                    return token
            article_list = payload.get("articleList") or payload.get("articles") or []
            if isinstance(article_list, list):
                for article in article_list:
                    if not isinstance(article, dict):
                        continue
                    token = str(article.get("articleName") or article.get("atclNm") or "").strip()
                    if token:
                        return token
            return ""

        try:
            chrome_path = ChromeParamHelper.get_chrome_executable_path()
            with sync_playwright() as playwright:
                if chrome_path:
                    browser = playwright.chromium.launch(executable_path=chrome_path, headless=True)
                else:
                    browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(
                        locale="ko-KR",
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    )
                    page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                    )

                    def _handle(response):
                        nonlocal captured_name
                        if captured_name:
                            return
                        url = str(getattr(response, "url", "") or "")
                        if expected_detail not in url and expected_articles not in url:
                            return
                        try:
                            name = _extract_name_from_payload(response.json())
                        except Exception:
                            name = ""
                        if name:
                            captured_name = name

                    page.on("response", _handle)
                    page.goto(
                        build_complex_url(cid, asset_type=asset_token),
                        wait_until="domcontentloaded",
                        timeout=12000,
                    )
                    try:
                        page.wait_for_load_state("networkidle", timeout=3000)
                    except Exception:
                        pass
                    if not captured_name:
                        page.wait_for_timeout(3000)
                    return str(captured_name or "").strip()
                finally:
                    browser.close()
        except RetryCancelledError:
            raise
        except Exception as e:
            get_logger("NaverURLParser").debug(f"단지명 browser fallback 실패 ({asset_token}:{cid}): {e}")
            return ""

    @classmethod
    def _fallback_name(cls, complex_id):
        return f"단지_{complex_id}"

    @staticmethod
    def _is_cancelled(cancel_checker) -> bool:
        if not callable(cancel_checker):
            return False
        try:
            return bool(cancel_checker())
        except Exception:
            return False

    @classmethod
    def _activate_name_lookup_cooldown(cls):
        runtime_cls = runtime_contract(cls)
        runtime_cls._name_lookup_cooldown_until = max(
            float(runtime_cls._name_lookup_cooldown_until or 0.0),
            time.monotonic() + float(runtime_cls._NAME_LOOKUP_COOLDOWN_SECONDS),
        )

    @classmethod
    def _consume_http_error_body(cls, error: HTTPError) -> str:
        try:
            return error.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    @classmethod
    def _reset_runtime_state_for_tests(cls):
        runtime_cls = runtime_contract(cls)
        runtime_cls._name_cache.clear()
        runtime_cls._name_lookup_cooldown_until = 0.0

    @classmethod
    def fetch_complex_name(cls, complex_id, asset_type="APT", cancel_checker=None):
        """단지 ID로 단지명을 조회한다."""
        runtime_cls = runtime_contract(cls)
        cid = str(complex_id or "").strip()
        asset_token = runtime_cls._normalize_asset_type(asset_type)
        fallback_name = cls._fallback_name(cid)
        if not cid:
            return fallback_name
        if cls._is_cancelled(cancel_checker):
            raise RetryCancelledError("lookup cancelled before attempt")

        cache_key = cls._name_cache_key(cid, asset_token)
        cached = runtime_cls._name_cache.get(cache_key, "")
        if cached:
            return cached

        logger = get_logger("NaverURLParser")
        direct_lookup_cooling_down = time.monotonic() < float(runtime_cls._name_lookup_cooldown_until or 0.0)
        if direct_lookup_cooling_down:
            logger.debug(f"단지명 direct 조회 cooldown 중, browser fallback 시도 ({asset_token}:{cid})")
            browser_name = str(
                cls._fetch_name_browser_fallback(
                    cid,
                    asset_type=asset_token,
                    cancel_checker=cancel_checker,
                )
                or ""
            ).strip()
            if browser_name:
                runtime_cls._name_cache[cache_key] = browser_name
                return browser_name
            return fallback_name

        try:
            name = str(cls._fetch_name_impl(cid, asset_type=asset_token) or "").strip() or fallback_name
            if name and not name.startswith("단지_"):
                runtime_cls._name_cache[cache_key] = name
            return name
        except RetryCancelledError:
            raise
        except Exception as e:
            if cls._is_cancelled(cancel_checker):
                raise RetryCancelledError("lookup cancelled after exception") from e
            if isinstance(e, HTTPError):
                response_body = cls._consume_http_error_body(e)
                status = int(getattr(e, "code", 0) or 0)
                if status == 429 or "TOO_MANY_REQUESTS" in response_body:
                    cls._activate_name_lookup_cooldown()
                    logger.warning(f"단지명 조회 rate limit ({asset_token}:{cid}): status={status}")
                    browser_name = str(
                        cls._fetch_name_browser_fallback(
                            cid,
                            asset_type=asset_token,
                            cancel_checker=cancel_checker,
                        )
                        or ""
                    ).strip()
                    if browser_name:
                        runtime_cls._name_cache[cache_key] = browser_name
                        return browser_name
                else:
                    logger.debug(
                        f"단지명 조회 HTTP 실패 ({asset_token}:{cid}): status={status}, body={response_body[:160]}"
                    )
            else:
                logger.debug(f"단지명 조회 실패 ({asset_token}:{cid}): {e}")
            return fallback_name
