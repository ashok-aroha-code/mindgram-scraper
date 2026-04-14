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


def is_bot_challenge_active(driver: uc.Chrome) -> bool:
    """
    Check if Cloudflare or a specific site block (like ScienceDirect) is active.
    """
    try:
        title = driver.title.lower()
        if any(m in title for m in ["just a moment", "cloudflare", "attention required"]):
            return True

        # ScienceDirect specific block text
        page_text = driver.find_element("tag name", "body").text.lower()
        if "there was a problem providing the content you requested" in page_text:
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


def wait_for_bot_clearance(
    driver: uc.Chrome, cfg: CloudflareConfig, url: str
) -> bool:
    """
    Polled wait for bot challenge/block to be cleared.
    """
    start_time = time.monotonic()
    human_prompted = False

    while (time.monotonic() - start_time) < cfg.total_timeout_seconds:
        if not is_bot_challenge_active(driver):
            if human_prompted:
                _log.info("Challenge cleared! Resuming...")
            return True

        elapsed = time.monotonic() - start_time

        if elapsed > cfg.auto_wait_seconds and not human_prompted:
            _log.warning("!!! BOT CHALLENGE / BLOCK DETECTED on %s !!!", url)
            _log.warning("Please solve the challenge or clear the 'Problem' page manually.")
            human_prompted = True

        time.sleep(2.0)

    _log.error("Clearance timed out for %s", url)
    return False
