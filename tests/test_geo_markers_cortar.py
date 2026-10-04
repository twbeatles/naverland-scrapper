"""Geo marker cortarNo resolution tests (live shape captured 2026-10-04)."""

import unittest

from src.core.engines.playwright_parts.geo_mode_parts.markers import (
    PlaywrightGeoMarkerMixin,
)


_MIXIN = PlaywrightGeoMarkerMixin()


class _FakeResponse:
    def __init__(self, status, payload=None, raises=False):
        self.status = status
        self._payload = payload
        self._raises = raises

    async def json(self):
        if self._raises:
            raise RuntimeError("bad payload")
        return self._payload


class _FakeRequestContext:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.urls = []

    async def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        if self._exc is not None:
            raise self._exc
        return self._response


class TestResolveCortarNo(unittest.IsolatedAsyncioTestCase):
    async def test_resolves_region_code(self):
        ctx = _FakeRequestContext(
            _FakeResponse(200, {"cortarNo": "4113510300", "cortarName": "x"})
        )
        result = await PlaywrightGeoMarkerMixin._resolve_cortar_no(
            _MIXIN, ctx, lat=37.3595704, lon=127.105399, zoom=16
        )
        self.assertEqual(result, "4113510300")
        self.assertTrue(any("/api/cortars" in url for url in ctx.urls))

    async def test_http_error_returns_empty(self):
        ctx = _FakeRequestContext(_FakeResponse(500, {}))
        result = await PlaywrightGeoMarkerMixin._resolve_cortar_no(
            _MIXIN, ctx, lat=37.5, lon=127.0, zoom=15
        )
        self.assertEqual(result, "")

    async def test_exception_returns_empty(self):
        ctx = _FakeRequestContext(exc=RuntimeError("down"))
        result = await PlaywrightGeoMarkerMixin._resolve_cortar_no(
            _MIXIN, ctx, lat=37.5, lon=127.0, zoom=15
        )
        self.assertEqual(result, "")

    async def test_non_dict_returns_empty(self):
        ctx = _FakeRequestContext(_FakeResponse(200, []))
        result = await PlaywrightGeoMarkerMixin._resolve_cortar_no(
            _MIXIN, ctx, lat=37.5, lon=127.0, zoom=15
        )
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
