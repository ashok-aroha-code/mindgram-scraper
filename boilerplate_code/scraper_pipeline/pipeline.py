"""
pipeline.py — orchestrates all five stages end-to-end.

Typical usage:
    from scraper_pipeline import Pipeline, PipelineConfig
    from scraper_pipeline.config import CollectorConfig, MeetingConfig

    cfg = PipelineConfig(
        work_dir="./output",
        collector=CollectorConfig(
            page_urls=["https://example.org/issue/ABC?pageStart=0", ...],
            css_selector="h3 a",
        ),
        meeting=MeetingConfig(
            meeting_name="WCN 2026 Annual Meeting",
            date="2026-04-01",
            link="https://events.theisn.org/wcn26/program/search",
        ),
    )
    result = Pipeline(cfg).run()

Skip completed stages:
    cfg.run_collect = False   # raw_urls.json already exists
    cfg.run_scrape  = False   # scraped_data.json already exists
    Pipeline(cfg).run()

Custom extractor:
    Pipeline(cfg, extractor=MyCustomExtractor()).run()
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from scraper_pipeline.config import PipelineConfig
from scraper_pipeline.extractors.wcn import WCNExtractor
from scraper_pipeline.extractors.base import BaseExtractor
from scraper_pipeline.models import PipelineResult
from scraper_pipeline.stages.collect import URLCollector
from scraper_pipeline.stages.deduplicate import URLDeduplicator
from scraper_pipeline.stages.scrape import ScraperEngine
from scraper_pipeline.stages.process import NumberExtractor
from scraper_pipeline.stages.package import MeetingWrapper
from scraper_pipeline.utils.io import read_json
from scraper_pipeline.utils.logging_setup import setup_logging

_log = logging.getLogger(__name__)


class Pipeline:
    """
    Runs the five-stage scraping pipeline:

        1. collect      URLCollector     → raw_urls.json
        2. deduplicate  URLDeduplicator  → article_urls.json
        3. scrape       ScraperEngine    → scraped_data.json
        4. number       NumberExtractor  → numbered_data.json
        5. package      MeetingWrapper   → <output_file>.json

    Each stage can be skipped individually via PipelineConfig.run_<stage> = False,
    which lets you resume or re-run only the parts that need updating.
    """

    def __init__(
        self,
        cfg: PipelineConfig,
        extractor: Optional[BaseExtractor] = None,
    ) -> None:
        self._cfg = cfg
        self._extractor = extractor or WCNExtractor()

    def run(self) -> PipelineResult:
        """
        Execute enabled pipeline stages in order and return a summary.

        On any unrecoverable error the exception propagates — the caller
        decides whether to catch and retry or abort.
        """
        cfg = self._cfg
        work = Path(cfg.work_dir)
        work.mkdir(parents=True, exist_ok=True)

        # Configure logging now that work_dir exists
        setup_logging(
            log_file=cfg.resolve(cfg.log_file),
            max_bytes=cfg.log_max_bytes,
            backup_count=cfg.log_backup_count,
        )
        _log.info("=" * 60)
        _log.info("Pipeline starting | work_dir=%s", work)
        _log.info(
            "Stages: collect=%s dedup=%s scrape=%s number=%s package=%s",
            cfg.run_collect,
            cfg.run_deduplicate,
            cfg.run_scrape,
            cfg.run_number,
            cfg.run_package,
        )

        result = PipelineResult()

        # --- Stage 1: Collect ------------------------------------------------
        raw_urls_path = cfg.resolve(cfg.raw_urls_file)

        if cfg.run_collect:
            _log.info("--- Stage 1: URL collection ---")
            raw = URLCollector(cfg.collector).run(raw_urls_path)
            result.urls_collected = sum(len(v) for v in raw.values())
            _log.info("Stage 1 done — %d URLs collected.", result.urls_collected)
        else:
            _log.info("Stage 1 skipped — using existing %s", raw_urls_path)
            if raw_urls_path.exists():
                raw = read_json(raw_urls_path)
                result.urls_collected = (
                    sum(len(v) if isinstance(v, list) else 0 for v in raw.values())
                    if isinstance(raw, dict)
                    else len(raw)
                )

        # --- Stage 2: Deduplicate --------------------------------------------
        article_urls_path = cfg.resolve(cfg.article_urls_file)

        if cfg.run_deduplicate:
            _log.info("--- Stage 2: Deduplication ---")
            urls = URLDeduplicator.run(raw_urls_path, article_urls_path)
            result.urls_after_dedup = len(urls)
            _log.info("Stage 2 done — %d unique URLs.", result.urls_after_dedup)
        else:
            _log.info("Stage 2 skipped — using existing %s", article_urls_path)
            if article_urls_path.exists():
                urls = read_json(article_urls_path)
                result.urls_after_dedup = len(urls)
            else:
                _log.error(
                    "Stage 2 skipped but %s does not exist. "
                    "Enable run_deduplicate or supply the file.",
                    article_urls_path,
                )
                sys.exit(1)

        # --- Stage 3: Scrape -------------------------------------------------
        scraped_path = cfg.resolve(cfg.scraped_data_file)

        if cfg.run_scrape:
            _log.info("--- Stage 3: Scraping (%d URLs) ---", len(urls))
            stats = ScraperEngine(cfg.scraper, self._extractor).run(
                urls=urls,
                output_path=scraped_path,
                checkpoint_path=cfg.resolve(cfg.checkpoint_file),
            )
            result.scraped_success = stats.success
            result.scraped_partial = stats.partial
            result.scraped_failed = stats.failed
            result.scraped_skipped = stats.skipped
            _log.info(
                "Stage 3 done — ok=%d partial=%d failed=%d",
                stats.success,
                stats.partial,
                stats.failed,
            )
        else:
            _log.info("Stage 3 skipped — using existing %s", scraped_path)

        # --- Stage 4: Number extraction --------------------------------------
        numbered_path = cfg.resolve(cfg.numbered_data_file)

        if cfg.run_number:
            _log.info("--- Stage 4: Number extraction ---")
            result.abstracts_numbered = NumberExtractor(cfg.number).run(
                scraped_path, numbered_path
            )
            _log.info(
                "Stage 4 done — %d abstracts numbered.", result.abstracts_numbered
            )
        else:
            _log.info("Stage 4 skipped — using existing %s", numbered_path)
            numbered_path = scraped_path  # fallback: use scraped output directly

        # --- Stage 5: Meeting packaging --------------------------------------
        output_path = cfg.resolve(cfg.output_file)

        if cfg.run_package:
            _log.info("--- Stage 5: Meeting packaging ---")
            MeetingWrapper(cfg.meeting).run(numbered_path, output_path)
            result.output_file = str(output_path)
            _log.info("Stage 5 done — deliverable: %s", output_path)
        else:
            _log.info("Stage 5 skipped.")

        result.log()
        return result
