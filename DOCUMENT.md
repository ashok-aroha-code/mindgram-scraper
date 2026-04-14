# Scraper Pipeline Guide

This pipeline is for browser-based extraction from sources you are permitted to access and automate. If a site presents a block or challenge page, the pipeline reports that state clearly instead of trying to work around it.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r scraper_pipeline/requirements.txt
   ```

2. Create or edit a YAML config in `scrapers/`.

3. Run:
   ```bash
   python run_yaml.py scrapers/ASE_2024.yaml
   ```

## Stages

1. Collect: visits listing pages and gathers article URLs into `raw_urls.json`.
2. Deduplicate: flattens collected URLs into `article_urls.json`.
3. Scrape: visits each article page, extracts fields, and writes incremental output.

## Access Handling

- The browser can reuse a real local Chrome profile for legitimate logged-in access.
- If the site shows a block or challenge page, the run waits for manual clearance when enabled.
- If the block is not cleared, the URL is recorded as failed instead of being retried with stealth tactics.

## Recommended Alternatives For Restricted Sources

- Publisher or partner APIs
- Licensed datasets or feeds
- Manual exports
- Institution-approved access workflows
