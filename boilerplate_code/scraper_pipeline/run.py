#!/usr/bin/env python3
"""
run.py — command-line entry point for the scraper pipeline.

Run the full pipeline:
    python run.py

Run only specific stages (skip the rest):
    python run.py --skip-collect --skip-dedup
    python run.py --only-scrape
    python run.py --only-package

Override work directory and output file:
    python run.py --work-dir ./output --output-file "My_Conference_2026.json"

Headless Chrome (for servers):
    python run.py --headless

Environment variable overrides also work:
    HEADLESS=true python run.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add the parent directory to sys.path so we can import 'scraper_pipeline'
# as a top-level package even when run.py is executed directly.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scraper_pipeline import Pipeline, PipelineConfig
from scraper_pipeline.config import (
    ChromeConfig,
    CollectorConfig,
    MeetingConfig,
    NumberConfig,
    ScraperConfig,
)


# ==============================================================================
# ✏️  CONFERENCE CONFIGURATION — update these for each new conference
# ==============================================================================


def build_config(args: argparse.Namespace) -> PipelineConfig:
    """
    Construct the full PipelineConfig from defaults + CLI overrides.

    ✏️  Things to change per conference:
        1. page_urls list in CollectorConfig
        2. MeetingConfig fields
        3. NumberConfig.pattern if the abstract numbering scheme differs
        4. ScraperConfig.page_load_indicator_xpath if the site structure differs
    """
    chrome = ChromeConfig(
        chrome_version=135,  # ✏️  match your installed Chrome major version
        headless=args.headless,
    )

    collector = CollectorConfig(
        page_urls=[
            # ✏️  Add all paginated listing page URLs here
            f"https://www.kireports.org/issue/S2468-0249(26)X2002-2?pageStart={i}"
            for i in range(51)
        ],
        css_selector="h3 a",  # ✏️  CSS selector for article links on listing pages
        chrome=chrome,
    )

    scraper = ScraperConfig(
        page_load_indicator_xpath='(//h4[@class="panel-title-text"])[1]',  # ✏️
        first_page_wait=30,
        max_retries=3,
        chrome=chrome,
    )

    number = NumberConfig(
        pattern=r"^(WCN26-\d+)",  # ✏️  match this conference's number format
    )

    meeting = MeetingConfig(
        meeting_name="WCN 2026 Annual Meeting",  # ✏️
        date="2026-04-01",  # ✏️
        link="https://events.theisn.org/wcn26/program/search",  # ✏️
    )

    return PipelineConfig(
        work_dir=args.work_dir,
        output_file=args.output_file,
        # Stage toggles from CLI flags
        run_collect=not args.skip_collect,
        run_deduplicate=not args.skip_dedup,
        run_scrape=not args.skip_scrape,
        run_number=not args.skip_number,
        run_package=not args.skip_package,
        collector=collector,
        scraper=scraper,
        number=number,
        meeting=meeting,
    )


# ==============================================================================
# CLI
# ==============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="WCN abstract scraping pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --- Output ---------------------------------------------------------------
    parser.add_argument(
        "--work-dir", default=".", help="Working directory for all files (default: .)"
    )
    parser.add_argument(
        "--output-file",
        default="WCN_2026_Annual_Meeting.json",
        help="Final output filename",
    )

    # --- Chrome ---------------------------------------------------------------
    parser.add_argument(
        "--headless", action="store_true", help="Run Chrome in headless mode"
    )

    # --- Stage skipping -------------------------------------------------------
    skip = parser.add_argument_group("stage skipping (skip stages already completed)")
    skip.add_argument(
        "--skip-collect", action="store_true", help="Skip Stage 1: URL collection"
    )
    skip.add_argument(
        "--skip-dedup", action="store_true", help="Skip Stage 2: deduplication"
    )
    skip.add_argument(
        "--skip-scrape", action="store_true", help="Skip Stage 3: article scraping"
    )
    skip.add_argument(
        "--skip-number", action="store_true", help="Skip Stage 4: number extraction"
    )
    skip.add_argument(
        "--skip-package", action="store_true", help="Skip Stage 5: meeting packaging"
    )

    # --- Convenience shortcuts ------------------------------------------------
    shortcuts = parser.add_argument_group("convenience shortcuts")
    shortcuts.add_argument(
        "--only-scrape", action="store_true", help="Skip all stages except scraping"
    )
    shortcuts.add_argument(
        "--only-package", action="store_true", help="Skip all stages except packaging"
    )

    args = parser.parse_args()

    # Apply shortcuts
    if args.only_scrape:
        args.skip_collect = args.skip_dedup = True
        args.skip_number = args.skip_package = True
    if args.only_package:
        args.skip_collect = args.skip_dedup = True
        args.skip_scrape = args.skip_number = True

    return args


def main() -> None:
    args = parse_args()
    cfg = build_config(args)
    result = Pipeline(cfg).run()

    # Exit with non-zero code if scraping had failures (useful for CI)
    if result.scraped_failed > 0:
        print(f"\nWarning: {result.scraped_failed} URLs failed to scrape.")
        sys.exit(1)


if __name__ == "__main__":
    main()
