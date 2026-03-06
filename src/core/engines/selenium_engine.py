from __future__ import annotations

from .base import CrawlerEngine


class SeleniumCrawlerEngine(CrawlerEngine):
    engine_name = "selenium"

    def run(self) -> None:
        self.thread._run_selenium_loop()
