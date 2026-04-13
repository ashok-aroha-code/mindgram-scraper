"""
utils/driver.py — Chrome WebDriver factory.

Centralised here so both the collector and scraper stages use
identical driver configuration with no duplication.
"""

from __future__ import annotations

import logging
import random
from contextlib import contextmanager
from typing import Iterator, List, Optional

import undetected_chromedriver as uc

from scraper_pipeline.config import ChromeConfig

_log = logging.getLogger(__name__)


def create_driver(cfg: ChromeConfig) -> uc.Chrome:
    """
    Build and return an undetected Chrome driver.
    """
    options = uc.ChromeOptions()
    options.headless = cfg.headless
    
    # Redundant flags removed to prevent fingerprint inconsistency
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-first-run")
    options.add_argument("--no-service-autorun")
    options.add_argument("--no-default-browser-check")
    
    # Suppress "Who's using Chrome?" and Search Engine Choice screens
    options.add_argument("--disable-features=SearchEngineChoice,ProfilePicker")

    if cfg.user_agents:
        options.add_argument(f"--user-agent={random.choice(cfg.user_agents)}")

    # Ensure user_data_dir is absolute for stability
    user_data_dir = None
    if cfg.user_data_dir:
        from pathlib import Path
        user_data_dir = str(Path(cfg.user_data_dir).resolve())

    # Initialize driver with persistent profile if configured
    try:
        driver = uc.Chrome(
            options=options, 
            version_main=cfg.chrome_version,
            user_data_dir=user_data_dir,
            use_subprocess=True
        )
    except Exception as exc:
        _log.error("Failed to start undetected-chromedriver: %s", exc)
        _log.info("TIP: Try running 'taskkill /f /im chrome.exe' in your terminal and delete the 'chrome_profile' folder.")
        raise
    
    _log.debug(
        "Driver created (version=%d, headless=%s, profile=%s)", 
        cfg.chrome_version, cfg.headless, user_data_dir
    )
    return driver


@contextmanager
def managed_driver(cfg: ChromeConfig) -> Iterator[uc.Chrome]:
    """
    Context manager that creates a driver and guarantees driver.quit()
    even if an exception is raised inside the `with` block.

    Usage:
        with managed_driver(cfg.chrome) as driver:
            driver.get(url)
    """
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
