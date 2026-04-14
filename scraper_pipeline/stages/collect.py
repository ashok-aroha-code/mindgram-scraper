"""
stages/collect.py — Stage 1: URL collection.

Crawls a list of paginated listing pages and collects all article URLs
matching a CSS selector. Saves results as a page-keyed dict for auditability.

Input:  CollectorConfig.page_urls  (list of listing-page URLs)
Output: raw_urls.json              ({"page_1": [...], "page_2": [...], ...})
"""

from __future__ import annotations

import logging
import random
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from scraper_pipeline.config import CollectorConfig
from scraper_pipeline.utils.driver import create_driver
from scraper_pipeline.utils.io import write_json
from scraper_pipeline.utils.cloudflare import wait_for_bot_clearance

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

_log = logging.getLogger(__name__)


class URLCollector:
    """
    Visits each listing page, extracts article hrefs, and saves them.

    One browser instance is opened per listing page (matches the original
    code's pattern, which is safer against per-page bot detection resets).
    """

    def __init__(self, cfg: CollectorConfig) -> None:
        self._cfg = cfg

    def run(self, output_path: Path, driver: Optional[uc.Chrome] = None) -> dict[str, list[str]]:
        """
        Collect URLs from listing pages using dynamic pagination if configured.
        """
        cfg = self._cfg
        results: dict[str, list[str]] = OrderedDict()
        
        # Decide if we own the driver or if it's external
        own_driver = False
        if driver is None:
            driver = create_driver(cfg.chrome)
            own_driver = True

        # Build initial queue from static URLs or dynamic template
        queue: list[str] = list(cfg.page_urls)
        
        # If range mode is configured (start and end page)
        if cfg.url_template and cfg.end_page is not None:
            for p in range(cfg.start_page, cfg.end_page + 1, cfg.page_increment):
                queue.append(cfg.url_template.format(page=p))
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                expand=True
            ) as progress:
                # 1. Process the queued URLs
                collect_task = progress.add_task("[cyan]Collecting URLs...", total=len(queue))
                
                for idx, url in enumerate(queue, 1):
                    progress.update(collect_task, description=f"[cyan]Collecting page {idx}/{len(queue)}: [dim]{url}")
                    urls = self._collect_one_page(driver, url, idx)
                    results[f"page_{idx}"] = urls
                    progress.advance(collect_task)
                    
                    if idx < len(queue):
                        time.sleep(cfg.inter_page_delay)

                # 2. Continuous mode (if template provided but no end_page)
                if cfg.url_template and cfg.end_page is None:
                    current_page = cfg.start_page
                    idx_offset = len(queue)
                    
                    cont_task = progress.add_task("[magenta]Continuous search...", total=None)
                    
                    while True:
                        idx_offset += 1
                        url = cfg.url_template.format(page=current_page)
                        progress.update(cont_task, description=f"[magenta]Searching page {current_page}: [dim]{url}")
                        
                        urls = self._collect_one_page(driver, url, idx_offset)
                        if not urls:
                            progress.update(cont_task, description="[yellow]End of collection reached.")
                            break
                        
                        results[f"page_{idx_offset}"] = urls
                        current_page += cfg.page_increment
                        time.sleep(cfg.inter_page_delay)

        finally:
            if own_driver and driver is not None:
                try:
                    driver.quit()
                    _log.debug("Collector browser closed.")
                except Exception:
                    pass

        write_json(output_path, results)
        total = sum(len(v) for v in results.values())
        _log.info(
            "Collection complete — %d URLs across %d pages → %s",
            total,
            len(results),
            output_path,
        )
        return results

    def _collect_one_page(self, driver: uc.Chrome, url: str, page_number: int) -> list[str]:
        """
        Navigate to `url` using existing `driver`, scrape hrefs.
        Retries up to CollectorConfig.max_retries times on timeout.
        """
        cfg = self._cfg

        for attempt in range(1, cfg.max_retries + 1):
            try:
                driver.get(url)

                # Robust bot/ScienceDirect handling: auto-bypass -> human interaction
                if not wait_for_bot_clearance(driver, cfg.cloudflare, url):
                    _log.error("Failed to clear bot challenge — skipping page %d: %s", page_number, url)
                    return []

                # Small human-like jitter
                time.sleep(random.uniform(2.0, 5.0))

                elements = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, cfg.css_selector)
                    )
                )
                hrefs = [
                    el.get_attribute("href")
                    for el in elements
                    if el.get_attribute("href")
                ]
                return hrefs

            except TimeoutException:
                _log.warning(
                    "Timeout on page %d (attempt %d/%d): %s",
                    page_number,
                    attempt,
                    cfg.max_retries,
                    url,
                )
                if attempt == cfg.max_retries:
                    _log.error(
                        "Giving up on page %d after %d attempts.",
                        page_number,
                        cfg.max_retries,
                    )
                    return []
                time.sleep(5)

            except Exception as exc:
                _log.error("Unexpected error on page %d: %s", page_number, exc)
                return []

        return []
