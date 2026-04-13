"""
scraper_pipeline — WCN abstract scraping pipeline.

Five-stage pipeline:
    1. collect     — crawl paginated listing pages → collect article URLs
    2. deduplicate — flatten page-keyed dict → unique URL list
    3. scrape      — visit each article page → extract abstract data
    4. number      — parse abstract number from title field
    5. package     — wrap abstracts in meeting metadata envelope

Quickstart:
    from scraper_pipeline import Pipeline, PipelineConfig
    from scraper_pipeline.config import MeetingConfig, CollectorConfig

    cfg = PipelineConfig(
        work_dir="./output",
        collector=CollectorConfig(page_urls=[...]),
        meeting=MeetingConfig(meeting_name="WCN 2026"),
    )
    Pipeline(cfg).run()
"""

from .pipeline import Pipeline
from .config import PipelineConfig

__all__ = ["Pipeline", "PipelineConfig"]
