"""Stage 1: collect article URLs from listing pages."""

from __future__ import annotations

import logging
import random
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from scraper_pipeline.config import CollectorConfig
from scraper_pipeline.utils.cloudflare import wait_for_bot_clearance
from scraper_pipeline.utils.driver import create_driver
from scraper_pipeline.utils.io import write_json

if TYPE_CHECKING:
    import undetected_chromedriver as uc

_log = logging.getLogger(__name__)


class URLCollector:
    """Visit listing pages, extract article hrefs, and save them."""

    def __init__(self, cfg: CollectorConfig) -> None:
        self._cfg = cfg

    def run(self, output_path: Path, driver: Optional[uc.Chrome] = None) -> dict[str, list[str]]:
        """Collect URLs from listing pages using static or templated pagination."""
        cfg = self._cfg
        results: dict[str, list[str]] = OrderedDict()

        own_driver = False
        if driver is None:
            driver = create_driver(cfg.chrome)
            own_driver = True

        queue: list[str] = list(cfg.page_urls)
        if cfg.url_template and cfg.end_page is not None:
            for p in range(cfg.start_page, cfg.end_page + 1, cfg.page_increment):
                queue.append(cfg.url_template.format(page=p))

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                expand=True,
            ) as progress:
                collect_task = progress.add_task("[cyan]Collecting URLs...", total=len(queue))

                for idx, url in enumerate(queue, 1):
                    progress.update(
                        collect_task,
                        description=f"[cyan]Collecting page {idx}/{len(queue)}: [dim]{url}",
                    )
                    urls = self._collect_one_page(driver, url, idx)
                    results[f"page_{idx}"] = urls
                    progress.advance(collect_task)

                    if idx < len(queue):
                        time.sleep(random.uniform(cfg.inter_page_delay_min, cfg.inter_page_delay_max))

                if cfg.url_template and cfg.end_page is None:
                    current_page = cfg.start_page
                    idx_offset = len(queue)
                    cont_task = progress.add_task("[magenta]Continuous search...", total=None)

                    while True:
                        idx_offset += 1
                        url = cfg.url_template.format(page=current_page)
                        progress.update(
                            cont_task,
                            description=f"[magenta]Searching page {current_page}: [dim]{url}",
                        )

                        urls = self._collect_one_page(driver, url, idx_offset)
                        if not urls:
                            progress.update(cont_task, description="[yellow]End of collection reached.")
                            break

                        results[f"page_{idx_offset}"] = urls
                        current_page += cfg.page_increment
                        time.sleep(random.uniform(cfg.inter_page_delay_min, cfg.inter_page_delay_max))
        finally:
            if own_driver and driver is not None:
                try:
                    driver.quit()
                    _log.debug("Collector browser closed.")
                except Exception:
                    pass

        write_json(output_path, results)
        total = sum(len(v) for v in results.values())
        _log.info("Collection complete - %d URLs across %d pages -> %s", total, len(results), output_path)
        return results

    def _collect_one_page(self, driver: uc.Chrome, url: str, page_number: int) -> list[str]:
        """Navigate to a listing page and extract hrefs."""
        cfg = self._cfg

        for attempt in range(1, cfg.max_retries + 1):
            try:
                driver.get(url)
                if not wait_for_bot_clearance(driver, cfg.cloudflare, url):
                    _log.error(
                        "Access challenge or block page detected - skipping page %d: %s",
                        page_number,
                        url,
                    )
                    return []

                elements = WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, cfg.css_selector))
                )
                hrefs = [el.get_attribute("href") for el in elements if el.get_attribute("href")]
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
                    _log.error("Giving up on page %d after %d attempts.", page_number, cfg.max_retries)
                    return []
                time.sleep(5)
            except Exception as exc:
                _log.error("Unexpected error on page %d: %s", page_number, exc)
                return []

        return []
