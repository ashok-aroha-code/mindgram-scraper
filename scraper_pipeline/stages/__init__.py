"""Three pipeline stages: collect → deduplicate → scrape."""

from .collect import URLCollector
from .deduplicate import URLDeduplicator
from .scrape import ScraperEngine

__all__ = [
    "URLCollector",
    "URLDeduplicator",
    "ScraperEngine",
]
