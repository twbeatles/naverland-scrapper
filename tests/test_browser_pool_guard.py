import os
import sys
import unittest
from types import SimpleNamespace

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.engines.playwright_parts.runtime_parts.browser import (
    PlaywrightBrowserRuntimeMixin,
)


class _FakePage:
    def __init__(self):
        self.init_scripts = []

    async def add_init_script(self, script):
        self.init_scripts.append(script)


class _FakeContext:
    def __init__(self):
        self.new_page_calls = 0

    async def new_page(self):
        self.new_page_calls += 1
        return _FakePage()


class TestBrowserPoolGuard(unittest.IsolatedAsyncioTestCase):
    def _make_runtime(self):
        runtime = PlaywrightBrowserRuntimeMixin(SimpleNamespace())
        self.addCleanup(runtime._loop.close)
        return runtime

    async def test_new_mobile_pool_page_without_context_raises(self):
        runtime = self._make_runtime()
        runtime._mobile_context = None
        with self.assertRaises(RuntimeError):
            await runtime._new_mobile_pool_page()

    async def test_new_mobile_pool_page_uses_context(self):
        runtime = self._make_runtime()
        context = _FakeContext()
        runtime._mobile_context = context
        page = await runtime._new_mobile_pool_page()
        self.assertIsInstance(page, _FakePage)
        self.assertEqual(context.new_page_calls, 1)
        self.assertEqual(len(page.init_scripts), 1)


if __name__ == "__main__":
    unittest.main()
