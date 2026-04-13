"""
config.py — all pipeline configuration in one place.

Every ✏️  comment marks a field you change for a new conference.
All other fields have production-sensible defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Shared defaults
# ---------------------------------------------------------------------------

_DEFAULT_USER_AGENTS: List[str] = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    ),
]


# ---------------------------------------------------------------------------
# Shared Chrome settings (reused by both the collector and scraper stages)
# ---------------------------------------------------------------------------


@dataclass
class ChromeConfig:
    chrome_version: int = 146
    headless: bool = False
    user_agents: List[str] = field(default_factory=lambda: list(_DEFAULT_USER_AGENTS))


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

    # ✏️  CSS selector that matches the <a> tags for individual articles
    css_selector: str = "h3 a"

    page_load_wait: int = 10  # seconds to sleep after driver.get()
    inter_page_delay: int = 3  # seconds between pages
    first_page_wait: int = 30  # seconds for manual CAPTCHA on page 1
    max_retries: int = 3
    chrome: ChromeConfig = field(default_factory=ChromeConfig)


# ---------------------------------------------------------------------------
# Stage 3 — Article scraping
# ---------------------------------------------------------------------------


@dataclass
class ScraperConfig:
    """
    Config for visiting individual article pages and extracting abstract data.

    Tuned for production: retry with backoff, driver auto-restart,
    first-page manual-CAPTCHA window, jittered request delays.
    """

    # --- Timing ---------------------------------------------------------------
    request_delay_min: float = 0.5
    request_delay_max: float = 1.5
    first_page_wait: int = 30  # seconds for manual CAPTCHA on first URL
    page_load_timeout: int = 20  # WebDriverWait ceiling
    post_nav_jitter: float = 1.5  # extra random sleep after driver.get()

    # --- Reliability ----------------------------------------------------------
    max_retries: int = 3
    retry_backoff_base: float = 2.0  # wait = base^attempt seconds
    max_driver_restarts: int = 5

    # --- Page detection  ✏️ ---------------------------------------------------
    # XPath of an element whose presence signals the page is fully loaded.
    page_load_indicator_xpath: str = '(//h4[@class="panel-title-text"])[1]'

    # --- Progress logging -----------------------------------------------------
    log_progress_every: int = 10  # log stats every N URLs

    # --- Debug ----------------------------------------------------------------
    save_screenshots_on_failure: bool = True
    screenshots_dir: str = "debug_screenshots"

    # --- Chrome ---------------------------------------------------------------
    chrome: ChromeConfig = field(default_factory=ChromeConfig)


# ---------------------------------------------------------------------------
# Stage 4 — Abstract number extraction
# ---------------------------------------------------------------------------


@dataclass
class NumberConfig:
    """
    Config for parsing the abstract's conference number out of the title.

    ✏️  Update `pattern` to match the current conference's numbering scheme.
    Examples:
        WCN 2026  → r"^(WCN26-\\d+)"
        CROI 2025 → r"^(CROI-\\d+)"
        Generic   → r"^([A-Z0-9]+-\\d+)"   ← default
    """

    pattern: str = r"^([A-Z0-9]+-\d+)"


# ---------------------------------------------------------------------------
# Stage 5 — Meeting packaging
# ---------------------------------------------------------------------------


@dataclass
class MeetingConfig:
    """
    Metadata envelope written around the final abstracts list.
    ✏️  Update for each conference.
    """

    meeting_name: str = "WCN 2026 Annual Meeting"  # ✏️
    date: str = "2026-04-01"  # ✏️
    link: str = "https://events.theisn.org/wcn26/program/search"  # ✏️


# ---------------------------------------------------------------------------
# Top-level pipeline config
# ---------------------------------------------------------------------------


@dataclass
class PipelineConfig:
    """
    Wires all five stages together.

    Skip stages already completed:
        cfg.run_collect = False    # article_urls.json already exists
        cfg.run_scrape  = False    # scraped_data.json already exists

    All file paths are relative to `work_dir`.
    """

    work_dir: str = "."

    # --- File names for each stage's output -----------------------------------
    raw_urls_file: str = "raw_urls.json"  # stage 1 → 2
    article_urls_file: str = "article_urls.json"  # stage 2 → 3
    scraped_data_file: str = "scraped_data.json"  # stage 3 → 4
    numbered_data_file: str = "numbered_data.json"  # stage 4 → 5
    output_file: str = "WCN_2026_Annual_Meeting.json"  # stage 5 final

    # --- Infrastructure -------------------------------------------------------
    checkpoint_file: str = ".scraper_checkpoint.json"
    log_file: str = "pipeline.log"
    log_max_bytes: int = 10 * 1024 * 1024  # 10 MB per file
    log_backup_count: int = 3

    # --- Stage toggles --------------------------------------------------------
    run_collect: bool = True
    run_deduplicate: bool = True
    run_scrape: bool = True
    run_number: bool = True
    run_package: bool = True

    # --- Per-stage configs ----------------------------------------------------
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    number: NumberConfig = field(default_factory=NumberConfig)
    meeting: MeetingConfig = field(default_factory=MeetingConfig)

    def resolve(self, filename: str) -> Path:
        """Resolve `filename` relative to work_dir."""
        return Path(self.work_dir) / filename
