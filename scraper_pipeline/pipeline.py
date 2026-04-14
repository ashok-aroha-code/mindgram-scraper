"""
pipeline.py — orchestrates all core stages end-to-end.

Typical usage:
    from scraper_pipeline import Pipeline, PipelineConfig
    from scraper_pipeline.config import CollectorConfig, ChromeConfig

    cfg = PipelineConfig(
        work_dir="./WCN_2026",
        collector=CollectorConfig(
            page_urls=["https://example.org/issue/ABC?pageStart=0"],
            css_selector="h3 a",
        ),
        output_file="results.json"
    )
    result = Pipeline(cfg, extractor=GenericExtractor(fields)).run()

Wait for completed stages:
    cfg.run_collect = False   # raw_urls.json already exists
    cfg.run_scrape  = False   # scraped_data.json already exists
    Pipeline(cfg, extractor=...).run()
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from scraper_pipeline.config import PipelineConfig
from scraper_pipeline.extractors.base import BaseExtractor
from scraper_pipeline.models import PipelineResult
from scraper_pipeline.stages.collect import URLCollector
from scraper_pipeline.stages.deduplicate import URLDeduplicator
from scraper_pipeline.stages.scrape import ScraperEngine
from scraper_pipeline.utils.driver import managed_driver
from scraper_pipeline.utils.io import read_json
from scraper_pipeline.utils.logging_setup import setup_logging

from rich.console import Console
from rich.table import Table

_log = logging.getLogger(__name__)


class Pipeline:
    """
    Runs the generic scraping pipeline:

        1. collect      URLCollector     → raw_urls.json
        2. deduplicate  URLDeduplicator  → article_urls.json
        3. scrape       ScraperEngine    → scraped_data.json
    """

    def __init__(
        self,
        cfg: PipelineConfig,
        extractor: BaseExtractor,
    ) -> None:
        self._cfg = cfg
        self._extractor = extractor

    def run(self) -> PipelineResult:
        """
        Execute enabled pipeline stages in order.
        """
        cfg = self._cfg
        work = Path(cfg.work_dir)
        work.mkdir(parents=True, exist_ok=True)

        _log.info("=" * 60)
        _log.info("🚀 PIPELINE STARTING | work_dir=%s", work)
        _log.info("=" * 60)
        _log.info(
            "Stages: [Collect: %s] [Dedup: %s] [Scrape: %s]",
            cfg.run_collect,
            cfg.run_deduplicate,
            cfg.run_scrape,
        )

        result = PipelineResult()

        # Manage a single driver session for the entire pipeline
        # (This keeps the browser open so bot-clearance persists)
        with managed_driver(cfg.collector.chrome) as driver:
            # --- Stage 1: Collect ------------------------------------------------
            raw_urls_path = cfg.resolve(cfg.raw_urls_file)

            if cfg.run_collect:
                _log.info("-" * 60)
                _log.info("📍 STAGE 1: URL Collection")
                _log.info("-" * 60)
                raw = URLCollector(cfg.collector).run(raw_urls_path, driver=driver)
                result.urls_collected = sum(len(v) for v in raw.values())
            else:
                if raw_urls_path.exists():
                    raw = read_json(raw_urls_path)
                    result.urls_collected = sum(len(v) if isinstance(v, list) else 0 for v in raw.values())

            # --- Stage 2: Deduplicate --------------------------------------------
            article_urls_path = cfg.resolve(cfg.article_urls_file)

            if cfg.run_deduplicate:
                _log.info("-" * 60)
                _log.info("🧹 STAGE 2: Deduplication")
                _log.info("-" * 60)
                urls = URLDeduplicator.run(raw_urls_path, article_urls_path)
                result.urls_after_dedup = len(urls)
            else:
                if article_urls_path.exists():
                    urls = read_json(article_urls_path)
                    result.urls_after_dedup = len(urls)

            # --- Stage 3: Scrape -------------------------------------------------
            scraped_path = cfg.resolve(cfg.scraped_data_file)

            if cfg.run_scrape:
                _log.info("-" * 60)
                _log.info("🔎 STAGE 3: Scraping (%d URLs)", len(urls))
                _log.info("-" * 60)
                stats = ScraperEngine(cfg.scraper, self._extractor).run(
                    urls=urls,
                    output_path=scraped_path,
                    checkpoint_path=cfg.resolve(cfg.checkpoint_file),
                    driver=driver,
                )
                result.scraped_success = stats.success
                result.scraped_partial = stats.partial
                result.scraped_failed = stats.failed
                result.scraped_skipped = stats.skipped
                result.output_file = str(scraped_path)

        _log.info("=" * 60)
        self._display_summary_table(result)
        _log.info("=" * 60)
        return result

    def _display_summary_table(self, result: PipelineResult) -> None:
        """Render a beautiful Rich table summarizing the pipeline's work."""
        console = Console()
        table = Table(title="🚀 Pipeline Results Summary", show_header=True, header_style="bold cyan", border_style="dim")
        
        table.add_column("Stage / Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_column("Status", justify="center")

        # Stage 1
        table.add_row(
            "URLs Collected", 
            str(result.urls_collected),
            "✅" if result.urls_collected > 0 else "❌"
        )
        
        # Stage 2
        table.add_row(
            "URLs After Dedup", 
            str(result.urls_after_dedup),
            "🧹"
        )

        table.add_section()

        # Stage 3
        table.add_row(
            "Scraped Success", 
            f"[green]{result.scraped_success}[/green]", 
            "✨"
        )
        table.add_row(
            "Scraped Partial", 
            f"[yellow]{result.scraped_partial}[/yellow]", 
            "⚠️"
        )
        table.add_row(
            "Scraped Failed", 
            f"[red]{result.scraped_failed}[/red]", 
            "🛑"
        )
        table.add_row(
            "Scraped Skipped", 
            f"[dim]{result.scraped_skipped}[/dim]", 
            "⏩"
        )

        console.print("\n")
        console.print(table)
        
        if result.output_file:
            console.print(f"\n[bold green]Final Data:[/bold green] [link file:///{Path(result.output_file).absolute()}]{result.output_file}[/link]\n")
