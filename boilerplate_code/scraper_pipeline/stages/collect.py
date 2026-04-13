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
        Collect URLs from all configured listing pages.

        Args:
            output_path: Where to write the page-keyed URL dict (raw_urls.json).

        Returns:
            OrderedDict mapping "page_N" → list of article URLs.
        """
        cfg = self._cfg
        if not cfg.page_urls:
            _log.warning("CollectorConfig.page_urls is empty — nothing to collect.")
            return {}

        results: dict[str, list[str]] = OrderedDict()

        for idx, page_url in enumerate(cfg.page_urls, 1):
            _log.info("Collecting page %d/%d: %s", idx, len(cfg.page_urls), page_url)
            urls = self._collect_one_page(page_url, idx)
            results[f"page_{idx}"] = urls
            _log.info("  → %d URLs collected", len(urls))

            if idx < len(cfg.page_urls):
                time.sleep(cfg.inter_page_delay)

        write_json(output_path, results)
        total = sum(len(v) for v in results.values())
        _log.info(
            "Collection complete — %d URLs across %d pages → %s",
            total,
            len(results),
            output_path,
        )
        return results

    def _collect_one_page(self, url: str, page_number: int) -> list[str]:
        """
        Open `url` in a new browser, wait for links, scrape hrefs, close browser.
        Retries up to CollectorConfig.max_retries times on timeout.
        """
        cfg = self._cfg

        for attempt in range(1, cfg.max_retries + 1):
            driver = None
            try:
                driver = create_driver(cfg.chrome)
                driver.get(url)

                if page_number == 1 and cfg.first_page_wait > 0:
                    _log.info(
                        "First page — pausing %ds for manual verification...",
                        cfg.first_page_wait,
                    )
                    time.sleep(cfg.first_page_wait)
                else:
                    time.sleep(cfg.page_load_wait)

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

            finally:
                if driver is not None:
                    try:
                        driver.quit()
                    except Exception:
                        pass

        return []
