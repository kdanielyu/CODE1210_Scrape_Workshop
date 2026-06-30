from abc import ABC, abstractmethod

from core.models import SearchJob


class BaseScraper(ABC):
    name: str = "base"

    @abstractmethod
    def scrape(self, job: SearchJob) -> int:
        """Execute scraping for *job*. Returns number of records inserted."""

    def __call__(self, job: SearchJob) -> int:
        return self.scrape(job)
