"""Chrome WebDriver factory used by collector and scraper stages."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import undetected_chromedriver as uc

from scraper_pipeline.config import ChromeConfig

_log = logging.getLogger(__name__)


def create_driver(cfg: ChromeConfig) -> uc.Chrome:
    """Build and return a browser driver using the configured local profile."""
    options = uc.ChromeOptions()
    options.headless = cfg.headless

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--window-size=1366,768")

    if cfg.profile_name:
        options.add_argument(f"--profile-directory={cfg.profile_name}")
        _log.debug("Using sub-profile: %s", cfg.profile_name)

    user_data_dir = None
    if cfg.user_data_dir:
        user_data_dir = str(Path(cfg.user_data_dir).resolve())

    try:
        driver = uc.Chrome(
            options=options,
            version_main=cfg.chrome_version,
            user_data_dir=user_data_dir,
            use_subprocess=True,
        )

        time.sleep(1)
        try:
            driver.maximize_window()
            driver.execute_script("window.focus();")
        except Exception as win_exc:
            _log.debug("Could not maximize or focus window: %s", win_exc)

    except Exception as exc:
        msg = str(exc).lower()
        if "profile in use" in msg or "cannot create default profile directory" in msg:
            _log.critical(
                "Chrome profile is locked. Close all Chrome windows and try again. "
                "Or run: taskkill /f /im chrome.exe"
            )
        else:
            _log.error("Failed to start Chrome driver: %s", exc)
            _log.info("Tip: try running 'taskkill /f /im chrome.exe' in your terminal.")
        raise

    _log.debug("Chrome driver ready (version=%d, profile=%s)", cfg.chrome_version, user_data_dir)
    return driver


@contextmanager
def managed_driver(cfg: ChromeConfig) -> Iterator[uc.Chrome]:
    """Create a driver and guarantee cleanup on exit."""
    driver: Optional[uc.Chrome] = None
    try:
        driver = create_driver(cfg)
        yield driver
    finally:
        if driver is not None:
            try:
                driver.quit()
                _log.debug("Driver quit cleanly.")
            except Exception as exc:
                _log.debug("Driver quit raised (safe to ignore): %s", exc)
