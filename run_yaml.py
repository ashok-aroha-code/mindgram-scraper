#!/usr/bin/env python3
"""
run_yaml.py — Orchestrates a scraping pipeline using a YAML configuration file.

Usage:
    python run_yaml.py scrapers/kireports.yaml
"""

import sys
import yaml
import logging
import argparse
from pathlib import Path

# Imports from scraper_pipeline (assumed to be in root)
from scraper_pipeline import Pipeline, PipelineConfig

from scraper_pipeline import Pipeline, PipelineConfig
from scraper_pipeline.utils.logging_setup import setup_logging
from scraper_pipeline.config import ChromeConfig, CollectorConfig, ScraperConfig
from scraper_pipeline.extractors.generic import GenericExtractor

_log = logging.getLogger(__name__)

def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_work_dir(name: str) -> str:
    """Sanitize name to use as a valid folder name."""
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")

def run_from_yaml(yaml_path: str, headless: bool = False):
    # 0. Output directory based on YAML filename
    config_name = Path(yaml_path).stem
    work_dir = str(Path("Data") / config_name)
    
    # 1. Initialize professional logging unified across runner and pipeline
    log_path = Path(work_dir) / "pipeline.log"
    _setup_global_logging(log_path)
    
    _log.info("Output folder: %s", work_dir)

    # Load YAML data
    data = load_yaml(yaml_path)

    # Extract sections from YAML
    name = data.get("name", "One-Time Scraper")
    listing = data.get("listing", {})
    scraping = data.get("scraping", {})
    output_file = data.get("output", "output.json")
    
    _log.info("Starting scraper: %s", name)

    # 1. Shared Chrome Config
    chrome_data = data.get("chrome", {})
    chrome = ChromeConfig(
        chrome_version=chrome_data.get("version", 146),
        headless=headless,
        user_data_dir=chrome_data.get("profile", "chrome_profile")
    )

    # 2. Collector Config
    collector = CollectorConfig(
        page_urls=listing.get("urls", []),
        url_template=listing.get("url_template"),
        start_page=listing.get("start_page", 1),
        end_page=listing.get("end_page"),
        page_increment=listing.get("page_increment", 1),
        css_selector=listing.get("item_selector", "a"),
        chrome=chrome
    )

    # 3. Scraper Config
    scraper = ScraperConfig(
        page_load_indicator_xpath=scraping.get("indicator_xpath", "//h1"),
        sample_limit=data.get("sample"),
        chrome=chrome
    )

    # 4. Folder organization (Simplified)
    # work_dir is now determined at the start of the function

    # 5. Full Pipeline Config
    cfg = PipelineConfig(
        work_dir=work_dir,
        scraped_data_file=output_file,
        collector=collector,
        scraper=scraper
    )

    # Instantiate Generic Extractor from YAML fields
    fields = scraping.get("fields", {})
    extractor = GenericExtractor(fields)

    # Run Pipeline
    pipeline = Pipeline(cfg, extractor=extractor)
    return pipeline.run()

def _setup_global_logging(log_file: Path):
    """Sets up the professional colored logger for the entire application."""
    logger = setup_logging(log_file)
    # Also redirect the root logger and script logger to use our beautiful setup
    global _log
    _log = logger
    # Redirect common libraries to stay quiet
    logging.getLogger("undetected_chromedriver").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)

def main():
    parser = argparse.ArgumentParser(description="Run a scraper from YAML config.")
    parser.add_argument("config", help="Path to the YAML config file")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()

    # Logging is now handled dynamically inside run_from_yaml 
    # based on the YAML filename/Data folder.

    try:
        run_from_yaml(args.config, args.headless)
    except Exception as exc:
        # Fallback logging if run_from_yaml fails before setup
        logging.basicConfig(level=logging.INFO)
        logging.error("Failed to run scraper from YAML: %s", exc, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
