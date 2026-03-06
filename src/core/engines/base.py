from __future__ import annotations

from abc import ABC, abstractmethod


class CrawlerEngine(ABC):
    engine_name = "base"

    def __init__(self, thread):
        self.thread = thread

    @abstractmethod
    def run(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        return None
