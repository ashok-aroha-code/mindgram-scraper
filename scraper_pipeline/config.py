"""
config.py — all pipeline configuration in one place.

Every ✏️  comment marks a field you change for a new conference.
All other fields have production-sensible defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Shared defaults
# ---------------------------------------------------------------------------


@dataclass
class CloudflareConfig:
    """Settings for handling Cloudflare challenges."""

    auto_wait_seconds: int = 10  # Wait for UD driver to auto-solve
    total_timeout_seconds: int = 300  # Total time (including human intervention)
    check_interval: float = 1.0  # Polling interval


# ---------------------------------------------------------------------------
# Shared Chrome settings (reused by both the collector and scraper stages)
# ---------------------------------------------------------------------------


@dataclass
class ChromeConfig:
    chrome_version: int = 147
    headless: bool = False
    user_agents: List[str] = field(default_factory=list)  # Uses _STEALTH_USER_AGENTS in driver.py when empty
    user_data_dir: Optional[str] = "chrome_profile"  # Enable persistent sessions
    profile_name: Optional[str] = None  # Use specific sub-profile directory


# ---------------------------------------------------------------------------
# Stage 1 — URL collection
# ---------------------------------------------------------------------------


@dataclass
class CollectorConfig:
    """
    Config for crawling paginated listing pages and collecting article URLs.

    ✏️  Required before running:
        cfg.collector.page_urls = [
            "https://example.org/issue/ABC?pageStart=0",
            "https://example.org/issue/ABC?pageStart=1",
            ...
        ]
    """

    page_urls: List[str] = field(default_factory=list)
    url_template: Optional[str] = None  # e.g. "https://site.com/p={page}"
    start_page: int = 1
    end_page: Optional[int] = None
    page_increment: int = 1

    # ✏️  CSS selector that matches the <a> tags for individual articles
    css_selector: str = "h3 a"

    page_load_wait: int = 10         # seconds to sleep after driver.get()
    inter_page_delay_min: float = 4.0  # minimum seconds between listing pages
    inter_page_delay_max: float = 9.0  # maximum seconds between listing pages
    first_page_wait: int = 30        # seconds for manual CAPTCHA on page 1
    max_retries: int = 3
    chrome: ChromeConfig = field(default_factory=ChromeConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)


# ---------------------------------------------------------------------------
# Stage 3 — Article scraping
# ---------------------------------------------------------------------------


@dataclass
class ScraperConfig:
    """
    Config for visiting individual article pages and extracting data.
    """

    # --- Timing ---------------------------------------------------------------
    request_delay_min: float = 2.0
    request_delay_max: float = 5.0
    first_page_wait: int = 30
    page_load_timeout: int = 25
    post_nav_jitter: float = 3.0

    # --- Reliability ----------------------------------------------------------
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    max_driver_restarts: int = 5

    # --- Page detection -------------------------------------------------------
    page_load_indicator_xpath: str = "//h1"

    # --- Progress logging -----------------------------------------------------
    log_progress_every: int = 10
    sample_limit: Optional[int] = None  # Stop after scraping this many records

    # --- Debug ----------------------------------------------------------------
    save_screenshots_on_failure: bool = True
    screenshots_dir: str = "debug_screenshots"

    # --- Chrome ---------------------------------------------------------------
    chrome: ChromeConfig = field(default_factory=ChromeConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)


# ---------------------------------------------------------------------------
# Top-level pipeline config
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """
    Wires the core stages together.
    """

    work_dir: str = "."

    # --- File names -----------------------------------------------------------
    raw_urls_file: str = "raw_urls.json"
    article_urls_file: str = "article_urls.json"
    scraped_data_file: str = "output.json"

    # --- Infrastructure -------------------------------------------------------
    checkpoint_file: str = ".scraper_checkpoint.json"
    log_file: str = "pipeline.log"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 3

    # --- Stage toggles --------------------------------------------------------
    run_collect: bool = True
    run_deduplicate: bool = True
    run_scrape: bool = True

    # --- Per-stage configs ----------------------------------------------------
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)

    def resolve(self, filename: str) -> Path:
        """Resolve `filename` relative to work_dir."""
        return Path(self.work_dir) / filename
