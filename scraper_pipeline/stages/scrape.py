"""Stage 3: visit article URLs and extract structured fields."""

from __future__ import annotations

import logging
import random
import signal
import threading
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from scraper_pipeline.config import ScraperConfig
from scraper_pipeline.extractors.base import BaseExtractor
from scraper_pipeline.models import CheckpointManager, ScrapeResult, StatsTracker
from scraper_pipeline.utils.cloudflare import AccessBlockedError, wait_for_bot_clearance
from scraper_pipeline.utils.driver import create_driver
from scraper_pipeline.utils.io import append_jsonl, jsonl_to_json

if TYPE_CHECKING:
    import undetected_chromedriver as uc

_log = logging.getLogger(__name__)


class ScraperEngine:
    """Drive the scraping loop for one batch of URLs."""

    def __init__(self, cfg: ScraperConfig, extractor: BaseExtractor) -> None:
        self._cfg = cfg
        self._extractor = extractor

    def run(
        self,
        urls: list[str],
        output_path: Path,
        checkpoint_path: Path,
        driver: Optional[uc.Chrome] = None,
    ) -> StatsTracker:
        """Scrape all URLs and write results to output_path."""
        cfg = self._cfg
        work_dir = output_path.parent
        work_dir.mkdir(parents=True, exist_ok=True)

        output_jsonl = work_dir / (output_path.stem + ".jsonl")
        failed_jsonl = work_dir / (output_path.stem + "_failed.jsonl")
        missing_jsonl = work_dir / (output_path.stem + "_missing.jsonl")
        screenshots = work_dir / cfg.screenshots_dir

        checkpoint = CheckpointManager(checkpoint_path)
        stats = StatsTracker(total=len(urls))
        shutdown = threading.Event()

        def _on_signal(sig: int, _frame: object) -> None:
            _log.warning("Signal %d - finishing current URL then stopping.", sig)
            shutdown.set()

        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)

        own_driver = False
        if driver is None:
            driver = create_driver(cfg.chrome)
            own_driver = True

        driver_restarts = 0
        is_first_url = True

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                expand=True,
            ) as progress:
                scrape_task = progress.add_task("[green]Scraping articles...", total=len(urls))
                progress.advance(scrape_task, stats.skipped)

                for url in urls:
                    if shutdown.is_set():
                        progress.update(scrape_task, description="[yellow]Shutdown requested...")
                        break

                    if cfg.sample_limit and stats.processed >= cfg.sample_limit:
                        progress.update(scrape_task, description="[yellow]Sample limit reached.")
                        break

                    if checkpoint.is_done(url):
                        continue

                    progress.update(scrape_task, description=f"[green]Scraping: [dim]{url}")
                    t_start = time.monotonic()
                    result: Optional[ScrapeResult] = None

                    for attempt in range(1, cfg.max_retries + 1):
                        try:
                            self._navigate_and_wait(driver, url, is_first_url)
                            is_first_url = False

                            record, missing = self._extractor.extract(driver)
                            record["link"] = url
                            result = ScrapeResult(
                                url=url,
                                record=record,
                                missing_fields=missing,
                                duration_sec=time.monotonic() - t_start,
                                attempts=attempt,
                            )
                            break

                        except WebDriverException:
                            progress.update(scrape_task, description="[red]Chrome crashed, restarting...")
                            try:
                                driver.quit()
                            except Exception:
                                pass
                            driver = None
                            driver_restarts += 1
                            if driver_restarts > cfg.max_driver_restarts:
                                shutdown.set()
                                break
                            time.sleep(3)
                            try:
                                driver = create_driver(cfg.chrome)
                            except Exception:
                                shutdown.set()
                                break
                            continue

                        except Exception as exc:
                            if attempt < cfg.max_retries:
                                backoff = cfg.retry_backoff_base**attempt + random.uniform(0, 1)
                                progress.update(
                                    scrape_task,
                                    description=f"[yellow]Retry {attempt}/{cfg.max_retries} for [dim]{url}",
                                )
                                time.sleep(backoff)
                            else:
                                if cfg.save_screenshots_on_failure and driver is not None:
                                    self._save_screenshot(driver, url, screenshots)
                                result = ScrapeResult(
                                    url=url,
                                    error=str(exc),
                                    duration_sec=time.monotonic() - t_start,
                                    attempts=attempt,
                                )

                    if shutdown.is_set() and driver is None:
                        break

                    if result is None:
                        result = ScrapeResult(
                            url=url,
                            error="No result produced (driver abort?)",
                            duration_sec=time.monotonic() - t_start,
                        )

                    stats.record(result)

                    if result.is_success or result.is_partial:
                        append_jsonl(output_jsonl, result.record)
                        if result.missing_fields:
                            append_jsonl(missing_jsonl, {"url": url, "missing_fields": result.missing_fields})
                    else:
                        append_jsonl(failed_jsonl, {"url": url, "error": result.error})

                    checkpoint.mark_done(url)
                    progress.advance(scrape_task)
                    time.sleep(random.uniform(cfg.request_delay_min, cfg.request_delay_max))
        finally:
            if own_driver and driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

            n_ok = jsonl_to_json(output_jsonl, output_path)
            n_failed = jsonl_to_json(failed_jsonl, output_path.parent / (output_path.stem + "_failed.json"))
            n_missing = jsonl_to_json(missing_jsonl, output_path.parent / (output_path.stem + "_missing.json"))

            stats.log_summary()
            _log.info(
                "Scrape output: %s (%d ok, %d failed, %d with missing fields)",
                output_path,
                n_ok,
                n_failed,
                n_missing,
            )

        return stats

    def _navigate_and_wait(self, driver: object, url: str, is_first: bool) -> None:
        """Load a URL, require legitimate access, then wait for the target element."""
        cfg = self._cfg
        driver.get(url)

        if not wait_for_bot_clearance(driver, cfg.cloudflare, url):
            raise AccessBlockedError(f"Access challenge or block page detected for {url}")

        if not is_first:
            time.sleep(random.uniform(1.0, cfg.post_nav_jitter))

        try:
            WebDriverWait(driver, cfg.page_load_timeout).until(
                EC.presence_of_element_located((By.XPATH, cfg.page_load_indicator_xpath))
            )
        except TimeoutException:
            _log.warning("Page load indicator not found within %ds: %s", cfg.page_load_timeout, url)

    @staticmethod
    def _save_screenshot(driver: object, url: str, screenshots_dir: Path) -> Optional[Path]:
        try:
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in url)[:100]
            path = screenshots_dir / f"{safe}_{int(time.time())}.png"
            driver.save_screenshot(str(path))
            return path
        except Exception as exc:
            _log.debug("Screenshot failed: %s", exc)
            return None
