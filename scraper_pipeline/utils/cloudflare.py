"""
utils/cloudflare.py — Cloudflare challenge detection and clearance.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from selenium.common.exceptions import WebDriverException

if TYPE_CHECKING:
    import undetected_chromedriver as uc
    from scraper_pipeline.config import CloudflareConfig

_log = logging.getLogger(__name__)


def is_cloudflare_active(driver: uc.Chrome) -> bool:
    """
    Check if Cloudflare is currently blocking the target page with a challenge.
    """
    try:
        title = driver.title.lower()
        if "just a moment" in title or "cloudflare" in title or "attention required" in title:
            return True

        # Check for specific Cloudflare elements
        markers = [
            "//div[@id='cf-challenge-running']",
            "//form[@id='challenge-form']",
            "//div[@class='cf-browser-verification']",
            "//input[@name='cf-turnstile-response']",
        ]
        for xpath in markers:
            if driver.find_elements("xpath", xpath):
                return True

        return False
    except WebDriverException:
        return False


def wait_for_cloudflare_clearance(
    driver: uc.Chrome, cfg: CloudflareConfig, url: str
) -> bool:
    """
    Polled wait for Cloudflare challenge to be cleared.
    1. Wait `auto_wait_seconds` to let UD driver solve it automatically.
    2. If still active, log a warning and wait up to `total_timeout_seconds`.
    """
    start_time = time.monotonic()
    last_detected = 0.0
    human_prompted = False

    while (time.monotonic() - start_time) < cfg.total_timeout_seconds:
        if not is_cloudflare_active(driver):
            if human_prompted:
                _log.info("Cloudflare challenge cleared! Resuming...")
            return True

        elapsed = time.monotonic() - start_time

        # If we've passed the auto-wait threshold and haven't prompted the human yet
        if elapsed > cfg.auto_wait_seconds and not human_prompted:
            _log.warning(
                "!!! CLOUDFLARE DETECTED on %s !!!", url
            )
            _log.warning(
                "Automatic bypass failed. PLEASE SOLVE THE CHALLENGE MANUALLY in the browser window."
            )
            _log.warning(
                "The scraper will wait up to %d more seconds for you...",
                int(cfg.total_timeout_seconds - elapsed),
            )
            human_prompted = True

        time.sleep(2.0)

    _log.error("Cloudflare clearance timed out after %ds for %s", cfg.total_timeout_seconds, url)
    return False
