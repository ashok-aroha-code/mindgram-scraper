"""
utils/driver.py — Chrome WebDriver factory.

Centralised here so both the collector and scraper stages use
identical driver configuration with no duplication.
"""

from __future__ import annotations

import logging
import random
import time
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
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 2. Advanced Stealth: Remove automation indicators
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Suppress "Who's using Chrome?" and Search Engine Choice screens
    options.add_argument("--disable-features=SearchEngineChoice,ProfilePicker")

    # Random Window Size (Avoids perfect 1920x1080 footprints)
    resolutions = ["1366,768", "1280,800", "1440,900", "1536,864", "1600,900"]
    options.add_argument(f"--window-size={random.choice(resolutions)}")

    if cfg.user_agents:
        ua = random.choice(cfg.user_agents)
        options.add_argument(f"--user-agent={ua}")
        _log.debug("Using UA: %s", ua)

    # 6. Profile & Sub-profile
    if cfg.profile_name:
        options.add_argument(f"--profile-directory={cfg.profile_name}")
        _log.debug("Using Sub-profile: %s", cfg.profile_name)

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
        msg = str(exc).lower()
        if "profile in use" in msg or "cannot create default profile directory" in msg:
            _log.critical("❌ CHROME PROFILE IS LOCKED: Please close all open Chrome windows on your computer and try again.")
        else:
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


def perform_stealth_jitter(driver: uc.Chrome):
    """
    Simulates human behavior by performing random scrolling and small delays.
    Useful for confusing bot detection that looks for static behavior.
    """
    try:
        # 1. Initial random wait
        time.sleep(random.uniform(1.0, 3.0))

        # 2. Random scroll "reading" behavior
        total_height = driver.execute_script("return document.body.scrollHeight")
        viewport_height = driver.execute_script("return window.innerHeight")
        
        if total_height > viewport_height:
            # Scroll down a few times in small chunks
            scroll_steps = random.randint(2, 5)
            for _ in range(scroll_steps):
                # Scroll down between 100 and 400 pixels
                scroll_by = random.randint(100, 400)
                driver.execute_script(f"window.scrollBy(0, {scroll_by});")
                time.sleep(random.uniform(0.5, 1.5))
            
            # Occasionally scroll back up a bit
            if random.random() > 0.5:
                driver.execute_script(f"window.scrollBy(0, -{random.randint(100, 300)});")
                time.sleep(random.uniform(0.5, 1.0))
        
        # 3. Final jitter wait
        time.sleep(random.uniform(1.0, 2.0))
        
    except Exception as exc:
        _log.debug("Stealth jitter failed (non-critical): %s", exc)
