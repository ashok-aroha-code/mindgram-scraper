#!/usr/bin/env python3
"""Orchestrate the scraping pipeline from a YAML configuration file."""

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

from scraper_pipeline import Pipeline, PipelineConfig
from scraper_pipeline.config import ChromeConfig, CloudflareConfig, CollectorConfig, ScraperConfig
from scraper_pipeline.extractors.generic import GenericExtractor
from scraper_pipeline.utils.logging_setup import setup_logging

_log = logging.getLogger(__name__)


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_from_yaml(yaml_path: str, headless: bool = False):
    config_name = Path(yaml_path).stem
    work_dir = str(Path("Data") / config_name)

    log_path = Path(work_dir) / "pipeline.log"
    _setup_global_logging(log_path)
    _log.info("Output folder: %s", work_dir)

    data = load_yaml(yaml_path)
    name = data.get("name", "One-Time Scraper")
    listing = data.get("listing", {})
    scraping = data.get("scraping", {})
    output_file = data.get("output", "output.json")
    _log.info("Starting scraper: %s", name)

    chrome_data = data.get("chrome", {})
    user_data_dir = chrome_data.get("user_data_dir", "chrome_profile")
    if user_data_dir:
        user_data_dir = os.path.expandvars(user_data_dir)

    _log.info("Initializing Chrome browser...")
    chrome = ChromeConfig(
        chrome_version=chrome_data.get("version", 147),
        headless=headless,
        user_data_dir=user_data_dir,
        profile_name=chrome_data.get("profile_name"),
    )

    collector = CollectorConfig(
        page_urls=listing.get("urls", []),
        url_template=listing.get("url_template"),
        start_page=listing.get("start_page", 1),
        end_page=listing.get("end_page"),
        page_increment=listing.get("page_increment", 1),
        css_selector=listing.get("item_selector", "a"),
        chrome=chrome,
        cloudflare=CloudflareConfig(
            allow_manual_clearance=listing.get("allow_manual_clearance", True),
            fail_on_access_block=listing.get("fail_on_access_block", True),
        ),
    )

    scraper = ScraperConfig(
        page_load_indicator_xpath=scraping.get("indicator_xpath", "//h1"),
        request_delay_min=scraping.get("request_delay_min", 2.0),
        request_delay_max=scraping.get("request_delay_max", 5.0),
        post_nav_jitter=scraping.get("post_nav_jitter", 3.0),
        sample_limit=data.get("sample"),
        chrome=chrome,
        cloudflare=CloudflareConfig(
            allow_manual_clearance=scraping.get("allow_manual_clearance", True),
            fail_on_access_block=scraping.get("fail_on_access_block", True),
        ),
    )

    cfg = PipelineConfig(
        work_dir=work_dir,
        scraped_data_file=output_file,
        collector=collector,
        scraper=scraper,
    )

    # --- Smart Resume Logic ---
    # Skip Stage 1 (Collect) if raw_urls.json already exists
    if cfg.resolve(cfg.raw_urls_file).exists():
        _log.info("Found existing '%s' - Stage 1 (Collection) will be skipped.", cfg.raw_urls_file)
        cfg.run_collect = False

    # Skip Stage 2 (Dedup) if article_urls.json already exists
    if cfg.resolve(cfg.article_urls_file).exists():
        _log.info("Found existing '%s' - Stage 2 (Deduplication) will be skipped.", cfg.article_urls_file)
        cfg.run_deduplicate = False

    extractor = GenericExtractor(scraping.get("fields", {}))
    pipeline = Pipeline(cfg, extractor=extractor)
    return pipeline.run()


def _setup_global_logging(log_file: Path):
    """Set up the application logger."""
    logger = setup_logging(log_file)
    global _log
    _log = logger
    logging.getLogger("undetected_chromedriver").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="Run a scraper from YAML config.")
    parser.add_argument("config", help="Path to the YAML config file")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()

    try:
        run_from_yaml(args.config, args.headless)
    except Exception as exc:
        logging.basicConfig(level=logging.INFO)
        logging.error("Failed to run scraper from YAML: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
