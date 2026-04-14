"""Detect access blocks and wait for a legitimate manual clearance window."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from selenium.common.exceptions import WebDriverException

if TYPE_CHECKING:
    import threading
    import undetected_chromedriver as uc
    from scraper_pipeline.config import CloudflareConfig

_log = logging.getLogger(__name__)


class AccessBlockedError(RuntimeError):
    """Raised when the target site presents a block or challenge page."""


_BLOCK_TITLE_MARKERS = [
    "just a moment",
    "attention required",
    "ddos protection",
    "cloudflare",
    "blocked",
    "access denied",
]

_BLOCK_BODY_MARKERS = [
    "enable javascript and cookies to continue",
    "please complete the security check",
    "please stand by, while we are checking your browser",
    "there was a problem providing the content you requested",
    "your access to this service has been temporarily limited",
    "please verify you are a human",
    "this site is protected by recaptcha",
    "bot protection",
    "ray id:",
]

_CF_XPATH_MARKERS = [
    "//div[@id='cf-challenge-running']",
    "//form[@id='challenge-form']",
    "//div[contains(@class,'cf-browser-verification')]",
    "//input[@name='cf-turnstile-response']",
    "//div[@id='challenge-stage']",
    "//div[@id='cf-wrapper']",
]


def is_bot_challenge_active(driver: uc.Chrome) -> bool:
    """Return True when the current page looks like a block/challenge page."""
    try:
        title = driver.title.lower().strip()
        for marker in _BLOCK_TITLE_MARKERS:
            if marker in title:
                _log.debug("Access block trigger [TITLE]: '%s' found in '%s'", marker, title)
                return True

        try:
            current_url = driver.current_url.lower()
            if "access-denied" in current_url or "/blocked" in current_url:
                _log.debug("Access block trigger [URL]: %s", current_url)
                return True
        except Exception:
            pass

        for xpath in _CF_XPATH_MARKERS:
            if driver.find_elements("xpath", xpath):
                _log.debug("Access block trigger [DOM]: %s", xpath)
                return True

        try:
            top_text = driver.execute_script(
                "return (document.body ? document.body.innerText : '').substring(0, 1500);"
            ).lower()
            for marker in _BLOCK_BODY_MARKERS:
                if marker in top_text:
                    _log.debug("Access block trigger [BODY]: '%s'", marker)
                    return True
        except Exception:
            pass

        return False
    except WebDriverException:
        return False


def wait_for_bot_clearance(
    driver: uc.Chrome, cfg: CloudflareConfig, url: str, shutdown_event: Optional[threading.Event] = None
) -> bool:
    """
    Wait for a block/challenge page to clear.

    This function does not attempt to bypass detection. It only gives a human
    operator time to resolve an access challenge in the visible browser window
    when that is permitted.
    """
    start_time = time.monotonic()
    human_prompted = False

    while (time.monotonic() - start_time) < cfg.total_timeout_seconds:
        if shutdown_event and shutdown_event.is_set():
            _log.debug("Shutdown requested while waiting for bot clearance.")
            return False

        if not is_bot_challenge_active(driver):
            if human_prompted:
                _log.info("Access challenge cleared. Resuming.")
            return True

        if not cfg.allow_manual_clearance:
            _log.error("Access block detected and manual clearance is disabled: %s", url)
            return False

        if not human_prompted and (time.monotonic() - start_time) > cfg.auto_wait_seconds:
            try:
                title = driver.title
                current_url = driver.current_url
            except Exception:
                title = "unknown"
                current_url = "unknown"

            _log.warning("ACCESS CHALLENGE OR BLOCK DETECTED")
            _log.warning("  URL:   %s", url)
            _log.warning("  Title: '%s'", title)
            _log.warning("  Curr:  %s", current_url)
            _log.warning("If you have legitimate access, resolve it manually in the browser window.")
            human_prompted = True

        time.sleep(max(cfg.check_interval, 0.5))

    _log.error("Access challenge timed out (%ds) for %s", cfg.total_timeout_seconds, url)
    return False
