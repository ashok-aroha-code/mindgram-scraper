"""
stages/process.py — Stage 4: abstract number extraction.

Parses the conference abstract number (e.g. "WCN26-1234") from the
beginning of each record's `title` field and writes it into the `number` field.

Input:  scraped_data.json   (list of record dicts)
Output: numbered_data.json  (same list, `number` field populated)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from scraper_pipeline.config import NumberConfig
from scraper_pipeline.utils.io import read_json, write_json

_log = logging.getLogger(__name__)


class NumberExtractor:
    """
    Extracts an abstract number from the title of each scraped record.

    Configurable via NumberConfig.pattern.  The first capture group of the
    regex is used as the number value.

    Examples:
        "WCN26-1234 Some Title"  → number = "WCN26-1234"
        "CROI-5678 Another..."   → number = "CROI-5678"
        "No number here"         → number = ""  (warning logged)
    """

    def __init__(self, cfg: NumberConfig) -> None:
        self._pattern = re.compile(cfg.pattern)

    def run(self, input_path: Path, output_path: Path) -> int:
        """
        Read records, extract numbers, write updated records.

        Args:
            input_path:  scraped_data.json
            output_path: numbered_data.json

        Returns:
            Count of records where a number was successfully extracted.
        """
        records: list[dict] = read_json(input_path)

        extracted = 0
        for record in records:
            title = record.get("title") or ""
            number = self._extract(title)
            record["number"] = number
            if number:
                extracted += 1
            else:
                _log.debug("No number pattern found in title: %.60s", title)

        write_json(output_path, records)
        _log.info(
            "Number extraction: %d/%d records had a number → %s",
            extracted,
            len(records),
            output_path,
        )
        return extracted

    def _extract(self, title: str) -> str:
        """Return the first capture group if the pattern matches, else ''."""
        if not title:
            return ""
        match = self._pattern.match(title.strip())
        return match.group(1) if match else ""
