"""
stages/scrape.py — Stage 3: article scraping engine.

The production-grade loop that visits each article URL and calls the
supplied extractor. All reliability features live here:
    • Checkpoint-based resumability
    • Per-URL retry with exponential backoff
    • Chrome crash detection and driver auto-restart
    • SIGINT/SIGTERM graceful shutdown
    • Incremental JSONL writes (crash-safe) → merged to JSON on completion
    • Screenshots saved for every URL that exhausts all retries

Input:  article_urls.json   (flat list of article URLs)
Output: scraped_data.json   (list of extracted record dicts)
"""

from __future__ import annotations

import logging
import random
import signal
import threading
import time
from pathlib import Path
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from scraper_pipeline.config import ScraperConfig
from scraper_pipeline.extractors.base import BaseExtractor
from scraper_pipeline.models import CheckpointManager, ScrapeResult, StatsTracker
from scraper_pipeline.utils.driver import create_driver
from scraper_pipeline.utils.io import append_jsonl, jsonl_to_json

_log = logging.getLogger(__name__)


class ScraperEngine:
    """
    Drives the scraping loop for one batch of URLs.

    Usage:
        engine = ScraperEngine(cfg, extractor=WCNExtractor())
        stats  = engine.run(
            urls=url_list,
            output_path=Path("scraped_data.json"),
            checkpoint_path=Path(".scraper_checkpoint.json"),
        )
    """

    def __init__(self, cfg: ScraperConfig, extractor: BaseExtractor) -> None:
        self._cfg = cfg
        self._extractor = extractor

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def run(
        self,
        urls: list[str],
        output_path: Path,
        checkpoint_path: Path,
    ) -> StatsTracker:
        """
        Scrape all URLs and write results to `output_path`.

        Resumes from where a previous run stopped (using `checkpoint_path`).
        Results are written to a JSONL working file immediately after each URL,
        then merged into the final JSON array when the loop finishes.

        Returns:
            StatsTracker with success/partial/failed/skipped counts.
        """
        cfg = self._cfg
        work_dir = output_path.parent
        work_dir.mkdir(parents=True, exist_ok=True)

        # JSONL working files (one line per URL, written incrementally)
        output_jsonl = work_dir / (output_path.stem + ".jsonl")
        failed_jsonl = work_dir / (output_path.stem + "_failed.jsonl")
        missing_jsonl = work_dir / (output_path.stem + "_missing.jsonl")
        screenshots = work_dir / cfg.screenshots_dir

        checkpoint = CheckpointManager(checkpoint_path)
        stats = StatsTracker(total=len(urls))

        # --- Graceful shutdown -----------------------------------------------
        shutdown = threading.Event()

        def _on_signal(sig: int, _frame: object) -> None:
            _log.warning("Signal %d — finishing current URL then stopping.", sig)
            shutdown.set()

        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)

        # --- Main loop -------------------------------------------------------
        driver: Optional[object] = None
        driver_restarts = 0
        is_first_url = True

        try:
            driver = create_driver(cfg.chrome)

            for url in urls:
                if shutdown.is_set():
                    _log.info("Shutdown flag — stopping before: %s", url)
                    break

                if checkpoint.is_done(url):
                    stats.record_skipped()
                    continue

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
                        break  # success

                    except WebDriverException as exc:
                        _log.error(
                            "Chrome crash on %s (attempt %d): %s", url, attempt, exc
                        )
                        try:
                            driver.quit()
                        except Exception:
                            pass
                        driver = None

                        driver_restarts += 1
                        if driver_restarts > cfg.max_driver_restarts:
                            _log.critical(
                                "Max driver restarts (%d) hit — aborting.",
                                cfg.max_driver_restarts,
                            )
                            shutdown.set()
                            break

                        _log.info("Restarting Chrome (restart #%d)...", driver_restarts)
                        time.sleep(3)
                        try:
                            driver = create_driver(cfg.chrome)
                        except Exception as restart_exc:
                            _log.critical(
                                "Driver restart failed: %s — aborting.", restart_exc
                            )
                            shutdown.set()
                            break
                        # Driver crash is not the page's fault — don't burn a retry
                        continue

                    except Exception as exc:
                        if attempt < cfg.max_retries:
                            backoff = cfg.retry_backoff_base**attempt + random.uniform(
                                0, 1
                            )
                            _log.warning(
                                "Attempt %d/%d failed on %s: %s — retrying in %.1fs",
                                attempt,
                                cfg.max_retries,
                                url,
                                exc,
                                backoff,
                            )
                            time.sleep(backoff)
                        else:
                            _log.error(
                                "All %d attempts exhausted on %s: %s",
                                cfg.max_retries,
                                url,
                                exc,
                            )
                            if cfg.save_screenshots_on_failure and driver is not None:
                                shot = self._save_screenshot(driver, url, screenshots)
                                if shot:
                                    _log.info("Debug screenshot: %s", shot)
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

                # Write to JSONL BEFORE updating checkpoint
                if result.is_success or result.is_partial:
                    append_jsonl(output_jsonl, result.record)
                    if result.missing_fields:
                        append_jsonl(
                            missing_jsonl,
                            {"url": url, "missing_fields": result.missing_fields},
                        )
                else:
                    append_jsonl(failed_jsonl, {"url": url, "error": result.error})

                checkpoint.mark_done(url)

                if stats.processed % cfg.log_progress_every == 0:
                    stats.log_progress(url)

                time.sleep(random.uniform(cfg.request_delay_min, cfg.request_delay_max))

        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

            # Merge JSONL working files → final JSON arrays
            n_ok = jsonl_to_json(output_jsonl, output_path)
            n_failed = jsonl_to_json(
                failed_jsonl, output_path.parent / (output_path.stem + "_failed.json")
            )
            n_missing = jsonl_to_json(
                missing_jsonl, output_path.parent / (output_path.stem + "_missing.json")
            )

            stats.log_summary()
            _log.info(
                "Scrape output: %s (%d ok, %d failed, %d with missing fields)",
                output_path,
                n_ok,
                n_failed,
                n_missing,
            )

        return stats

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _navigate_and_wait(self, driver: object, url: str, is_first: bool) -> None:
        """Load URL, optionally wait for manual CAPTCHA, then wait for page indicator."""
        cfg = self._cfg
        driver.get(url)

        if is_first and cfg.first_page_wait > 0:
            _log.info(
                "First URL — pausing %ds for manual verification...",
                cfg.first_page_wait,
            )
            time.sleep(cfg.first_page_wait)
        else:
            time.sleep(random.uniform(1.0, cfg.post_nav_jitter))

        try:
            WebDriverWait(driver, cfg.page_load_timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, cfg.page_load_indicator_xpath)
                )
            )
        except TimeoutException:
            _log.warning(
                "Page load indicator not found within %ds: %s",
                cfg.page_load_timeout,
                url,
            )

    @staticmethod
    def _save_screenshot(
        driver: object, url: str, screenshots_dir: Path
    ) -> Optional[Path]:
        try:
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            safe = "".join(c if c.isalnum() else "_" for c in url)[:100]
            path = screenshots_dir / f"{safe}_{int(time.time())}.png"
            driver.save_screenshot(str(path))
            return path
        except Exception as exc:
            _log.debug("Screenshot failed: %s", exc)
            return None
