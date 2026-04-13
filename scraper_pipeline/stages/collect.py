"""
stages/collect.py — Stage 1: URL collection.

Crawls a list of paginated listing pages and collects all article URLs
matching a CSS selector. Saves results as a page-keyed dict for auditability.

Input:  CollectorConfig.page_urls  (list of listing-page URLs)
Output: raw_urls.json              ({"page_1": [...], "page_2": [...], ...})
"""

from __future__ import annotations

import logging
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
from scraper_pipeline.utils.cloudflare import wait_for_cloudflare_clearance

_log = logging.getLogger(__name__)


class URLCollector:
    """
    Visits each listing page, extracts article hrefs, and saves them.

    One browser instance is opened per listing page (matches the original
    code's pattern, which is safer against per-page bot detection resets).
    """

    def __init__(self, cfg: CollectorConfig) -> None:
        self._cfg = cfg

    def run(self, output_path: Path) -> dict[str, list[str]]:
        """
        Collect URLs from all configured listing pages using a single browser instance.
        """
        cfg = self._cfg
        if not cfg.page_urls:
            _log.warning("CollectorConfig.page_urls is empty — nothing to collect.")
            return {}

        results: dict[str, list[str]] = OrderedDict()
        driver = None

        try:
            # Open browser once for all pages
            driver = create_driver(cfg.chrome)

            for idx, page_url in enumerate(cfg.page_urls, 1):
                _log.info("Collecting page %d/%d: %s", idx, len(cfg.page_urls), page_url)
                urls = self._collect_one_page(driver, page_url, idx)
                results[f"page_{idx}"] = urls
                _log.info("  → %d URLs collected", len(urls))

                if idx < len(cfg.page_urls):
                    time.sleep(cfg.inter_page_delay)

        finally:
            if driver is not None:
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

                # Robust Cloudflare handling: auto-bypass -> human interaction
                if not wait_for_cloudflare_clearance(driver, cfg.cloudflare, url):
                    _log.error("Failed to clear Cloudflare — skipping page %d: %s", page_number, url)
                    return []

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
