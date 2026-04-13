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
    Applies all bot-detection bypass flags and optionally rotates user-agent.
    """
    options = uc.ChromeOptions()
    options.headless = cfg.headless
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    if cfg.user_agents:
        options.add_argument(f"--user-agent={random.choice(cfg.user_agents)}")

    driver = uc.Chrome(options=options, version_main=cfg.chrome_version)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    _log.debug(
        "Driver created (version=%d, headless=%s)", cfg.chrome_version, cfg.headless
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
