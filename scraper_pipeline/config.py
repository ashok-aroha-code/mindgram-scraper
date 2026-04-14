"""All pipeline configuration in one place."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class CloudflareConfig:
    """Settings for handling access-block and challenge pages."""

    auto_wait_seconds: int = 10
    total_timeout_seconds: int = 300
    check_interval: float = 1.0
    allow_manual_clearance: bool = True
    fail_on_access_block: bool = True


@dataclass
class ChromeConfig:
    chrome_version: int = 147
    headless: bool = False
    user_agents: List[str] = field(default_factory=list)
    user_data_dir: Optional[str] = "chrome_profile"
    profile_name: Optional[str] = None


@dataclass
class CollectorConfig:
    """Config for crawling listing pages and collecting article URLs."""

    page_urls: List[str] = field(default_factory=list)
    url_template: Optional[str] = None
    start_page: int = 1
    end_page: Optional[int] = None
    page_increment: int = 1
    css_selector: str = "h3 a"
    page_load_wait: int = 10
    inter_page_delay_min: float = 4.0
    inter_page_delay_max: float = 9.0
    first_page_wait: int = 30
    max_retries: int = 3
    chrome: ChromeConfig = field(default_factory=ChromeConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)


@dataclass
class ScraperConfig:
    """Config for visiting individual article pages and extracting data."""

    request_delay_min: float = 2.0
    request_delay_max: float = 5.0
    first_page_wait: int = 30
    page_load_timeout: int = 25
    post_nav_jitter: float = 3.0
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    max_driver_restarts: int = 5
    page_load_indicator_xpath: str = "//h1"
    log_progress_every: int = 10
    sample_limit: Optional[int] = None
    save_screenshots_on_failure: bool = True
    screenshots_dir: str = "debug_screenshots"
    chrome: ChromeConfig = field(default_factory=ChromeConfig)
    cloudflare: CloudflareConfig = field(default_factory=CloudflareConfig)


@dataclass
class PipelineConfig:
    """Wire the core stages together."""

    work_dir: str = "."
    raw_urls_file: str = "raw_urls.json"
    article_urls_file: str = "article_urls.json"
    scraped_data_file: str = "output.json"
    checkpoint_file: str = ".scraper_checkpoint.json"
    log_file: str = "pipeline.log"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 3
    run_collect: bool = True
    run_deduplicate: bool = True
    run_scrape: bool = True
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)

    def resolve(self, filename: str) -> Path:
        """Resolve filename relative to work_dir."""
        return Path(self.work_dir) / filename
