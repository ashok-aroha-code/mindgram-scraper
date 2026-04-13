# Scraper Pipeline Boilerplate Guide

This boilerplate provides a production-grade, 5-stage pipeline for scraping conference abstracts. It is designed to be resilient, resumable, and easy to adapt for new conferences.

## 🚀 Quick Start

1.  **Environment Setup**:
    ```bash
    # install dependencies
    pip install -r scraper_pipeline/requirements.txt
    ```

2.  **Configuration**:
    Open `scraper_pipeline/run.py` and look for the pencil emojis (**✏️**). These are the only lines you typically need to change.

3.  **Run the Pipeline**:
    ```bash
    cd scraper_pipeline
    python run.py
    ```

---

## 🏗️ The 5-Stage Architecture

The pipeline processes data in discrete stages to ensure auditability and crash recovery:

1.  **Collect** (`URLCollector`):
    - Visits paginated listing pages (e.g., search results).
    - Collects all article URLs matching the `css_selector`.
    - Output: `raw_urls.json`

2.  **Deduplicate** (`URLDeduplicator`):
    - Flattens the page-keyed results from Stage 1 into a unique list.
    - Output: `article_urls.json`

3.  **Scrape** (`ScraperEngine`):
    - Visits each article URL.
    - Uses an `Extractor` (default: `WCNExtractor`) to pull fields (Title, Abstract, Authors, etc.).
    - **Features**: Exponential backoff, proxy/UA rotation, and checkpoint-based resume.
    - Output: `scraped_data.json`

4.  **Process** (`NumberExtractor`):
    - Extracts conference numbers (e.g., "WCN26-1234") from the title or other fields using regex.
    - Output: `numbered_data.json`

5.  **Package** (`MeetingWrapper`):
    - Wraps the individual abstracts into a JSON envelope with meeting metadata (Name, Date, Link).
    - Output: `Your_Meeting_Name.json`

---

## ✏️ Adapting for a New Conference

### 1. Update Site Logic
Most changes happen in `scraper_pipeline/run.py`:
- **Page URLs**: Add the list of listing pages to `CollectorConfig`.
- **Selectors**: Update the `css_selector` in `CollectorConfig`.
- **Extractor**: If the site layout is different, create a new class in `extractors/` and update `WCNExtractor` or create a new one.

### 2. Update Metadata
- **Meeting Props**: Update `MeetingConfig` (name, date, main site link).
- **Number Format**: Update `NumberConfig.pattern` with the regex for this meeting's IDs.

---

## 🛠️ Advanced Usage

### Resuming a Scrape
If Stage 3 crashes, simply run it again. The `ScraperEngine` uses `.scraper_checkpoint.json` to skip URLs that have already been successfully processed.

### Running Specific Stages
You can skip stages that are already finished to save time:
```bash
python run.py --skip-collect --skip-dedup  # Start from scraping
python run.py --only-package               # Re-generate the final JSON only
```

### Headless Mode
For running on servers/CI:
```bash
python run.py --headless
```

---

## ❓ Troubleshooting

- **Chrome Version Mismatch**: If you see a driver error, update `chrome_version` in `run.py` to match your local Chrome major version (e.g., 135, 136).
- **CAPTCHAs**: On the first URL, the script pauses for 30 seconds by default. Use this time to solve any initial CAPTCHAs manually.
- **Failures**: Check `debug_screenshots/` for images of pages that failed to load during the scraping stage.
