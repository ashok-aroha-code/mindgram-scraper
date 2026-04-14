"""
utils/cloudflare.py — Cloudflare and ScienceDirect challenge detection and clearance.
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

from selenium.common.exceptions import WebDriverException

if TYPE_CHECKING:
    import undetected_chromedriver as uc
    from scraper_pipeline.config import CloudflareConfig

_log = logging.getLogger(__name__)

# ScienceDirect and Cloudflare block phrases in page text
_BLOCK_TEXT_MARKERS = [
    "there was a problem providing the content you requested",
    "access denied",
    "your access to this service has been temporarily limited",
    "please verify you are a human",
    "enable javascript and cookies to continue",
    "checking your browser",
    "service unavailable",
    "this site is protected by reCAPTCHA",
]

# Cloudflare DOM element XPaths
_CF_XPATH_MARKERS = [
    "//div[@id='cf-challenge-running']",
    "//form[@id='challenge-form']",
    "//div[@class='cf-browser-verification']",
    "//input[@name='cf-turnstile-response']",
    "//div[@id='challenge-stage']",
    "//div[@id='cf-wrapper']",
]


def is_bot_challenge_active(driver: uc.Chrome) -> bool:
    """
    Check if Cloudflare, ScienceDirect access block, or generic bot-wall is active.
    """
    try:
        title = driver.title.lower()

        # Title-based detection
        if any(m in title for m in ["just a moment", "cloudflare", "attention required", "access denied"]):
            return True

        # Page text detection (broad sweep)
        try:
            page_text = driver.find_element("tag name", "body").text.lower()
            if any(marker in page_text for marker in _BLOCK_TEXT_MARKERS):
                return True
        except Exception:
            pass

        # DOM element detection (Cloudflare challenge widgets)
        for xpath in _CF_XPATH_MARKERS:
            if driver.find_elements("xpath", xpath):
                return True

        # URL-based detection — SD sometimes redirects to /access-denied
        current_url = driver.current_url.lower()
        if "access-denied" in current_url or "blocked" in current_url:
            return True

        return False

    except WebDriverException:
        return False


def wait_for_bot_clearance(
    driver: uc.Chrome, cfg: CloudflareConfig, url: str
) -> bool:
    """
    Polled wait for bot challenge/block to be cleared.
    Uses jittered polling to avoid detection.
    """
    start_time = time.monotonic()
    human_prompted = False

    while (time.monotonic() - start_time) < cfg.total_timeout_seconds:
        if not is_bot_challenge_active(driver):
            if human_prompted:
                _log.info("✅ Challenge cleared! Resuming...")
            return True

        elapsed = time.monotonic() - start_time

        if elapsed > cfg.auto_wait_seconds and not human_prompted:
            try:
                title = driver.title
            except Exception:
                title = "unknown"
            _log.warning("!!! BOT CHALLENGE / BLOCK DETECTED on %s !!!", url)
            _log.warning("Page title: '%s'", title)
            _log.warning("Please solve the challenge manually in the browser window.")
            human_prompted = True

        # Jitter the poll interval to avoid fingerprinting the wait loop
        time.sleep(random.uniform(1.5, 2.5))

    _log.error("Clearance timed out (%ds) for %s", cfg.total_timeout_seconds, url)
    return False
