"""
stages/deduplicate.py — Stage 2: URL deduplication.

Flattens the page-keyed dict from Stage 1 into a single deduplicated
list, preserving insertion order.

Input:  raw_urls.json      ({"page_1": [...], "page_2": [...], ...})
Output: article_urls.json  ([url1, url2, ...])
"""

from __future__ import annotations

import logging
from pathlib import Path

from scraper_pipeline.utils.io import read_json, write_json

_log = logging.getLogger(__name__)


class URLDeduplicator:
    """Flattens and deduplicates a page-keyed URL dict."""

    @staticmethod
    def run(input_path: Path, output_path: Path) -> list[str]:
        """
        Read `input_path`, flatten all page lists, deduplicate (order-preserving),
        and write the result to `output_path`.

        Args:
            input_path:  raw_urls.json  — dict or flat list (both accepted)
            output_path: article_urls.json — flat deduplicated URL list

        Returns:
            The deduplicated URL list.
        """
        raw = read_json(input_path)

        # Accept both {"page_1": [...], ...} and a plain list
        if isinstance(raw, dict):
            flat: list[str] = []
            for urls in raw.values():
                flat.extend(urls)
        elif isinstance(raw, list):
            flat = raw
        else:
            raise ValueError(
                f"Unexpected format in {input_path}: expected dict or list, got {type(raw).__name__}"
            )

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for url in flat:
            if url and url not in seen:
                seen.add(url)
                unique.append(url)

        duplicates_removed = len(flat) - len(unique)
        _log.info(
            "Deduplication: %d total → %d unique (%d duplicates removed)",
            len(flat),
            len(unique),
            duplicates_removed,
        )

        write_json(output_path, unique)
        _log.info("Unique URLs written → %s", output_path)
        return unique
