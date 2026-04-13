"""
models.py — shared data objects used across pipeline stages.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single-URL scrape outcome
# ---------------------------------------------------------------------------


@dataclass
class ScrapeResult:
    """Outcome of scraping one article URL."""

    url: str
    record: Optional[dict] = None
    missing_fields: dict = field(default_factory=dict)
    error: Optional[str] = None
    duration_sec: float = 0.0
    attempts: int = 1

    @property
    def is_success(self) -> bool:
        return self.record is not None and self.error is None

    @property
    def is_partial(self) -> bool:
        """Scraped successfully but some fields were absent."""
        return self.is_success and bool(self.missing_fields)

    @property
    def is_failed(self) -> bool:
        return not self.is_success


# ---------------------------------------------------------------------------
# Checkpoint — tracks which URLs have already been scraped
# ---------------------------------------------------------------------------


class CheckpointManager:
    """
    Persists a set of completed URLs to a JSON file.

    The file is written after every URL so progress survives crashes.
    Checkpoint is always updated AFTER the data file, so data and
    checkpoint state can never be out of sync.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._done: set[str] = self._load()

    def _load(self) -> set[str]:
        if not self._path.exists():
            return set()
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            return set(data) if isinstance(data, list) else set()
        except (json.JSONDecodeError, OSError):
            _log.warning("Checkpoint unreadable — starting fresh: %s", self._path)
            return set()

    def is_done(self, url: str) -> bool:
        return url in self._done

    def mark_done(self, url: str) -> None:
        self._done.add(url)
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(list(self._done), f)
        except OSError as exc:
            _log.warning("Checkpoint flush failed: %s", exc)

    @property
    def count(self) -> int:
        return len(self._done)


# ---------------------------------------------------------------------------
# Stats — live progress tracker for the scrape stage
# ---------------------------------------------------------------------------


class StatsTracker:
    """
    Tracks success/partial/failed/skipped counts and computes ETA.
    Call log_progress() periodically; call log_summary() at the end.
    """

    def __init__(self, total: int) -> None:
        self.total = total
        self.success = 0
        self.partial = 0
        self.failed = 0
        self.skipped = 0
        self._durations: list[float] = []
        self._start = time.monotonic()

    def record(self, result: ScrapeResult) -> None:
        if result.is_failed:
            self.failed += 1
        elif result.is_partial:
            self.partial += 1
            self._durations.append(result.duration_sec)
        else:
            self.success += 1
            self._durations.append(result.duration_sec)

    def record_skipped(self) -> None:
        self.skipped += 1

    @property
    def processed(self) -> int:
        return self.success + self.partial + self.failed

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

    @property
    def avg_duration(self) -> Optional[float]:
        return sum(self._durations) / len(self._durations) if self._durations else None

    @property
    def eta_seconds(self) -> Optional[float]:
        avg = self.avg_duration
        remaining = self.total - self.processed - self.skipped
        return (remaining * avg) if (avg and remaining > 0) else None

    def log_progress(self, url: str = "") -> None:
        eta = self.eta_seconds
        avg = self.avg_duration
        eta_str = f"{eta:.0f}s" if eta is not None else "—"
        _log.info(
            "Scrape [%d/%d] ok=%d partial=%d fail=%d skip=%d avg=%.1fs eta=%s | %s",
            self.processed,
            self.total,
            self.success,
            self.partial,
            self.failed,
            self.skipped,
            avg or 0.0,
            eta_str,
            url[:80] if url else "",
        )

    def log_summary(self) -> None:
        _log.info(
            "Scrape done — total=%d ok=%d partial=%d fail=%d skip=%d "
            "elapsed=%.1fs avg=%.2fs",
            self.total,
            self.success,
            self.partial,
            self.failed,
            self.skipped,
            self.elapsed,
            self.avg_duration or 0.0,
        )


# ---------------------------------------------------------------------------
# Pipeline-level summary
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Rolled-up stats from all pipeline stages."""

    urls_collected: int = 0
    urls_after_dedup: int = 0
    scraped_success: int = 0
    scraped_partial: int = 0
    scraped_failed: int = 0
    scraped_skipped: int = 0
    scraped_skipped: int = 0
    output_file: str = ""

    def log(self) -> None:
        _log.info(
            "=== PIPELINE COMPLETE === "
            "collected=%d deduped=%d scraped(ok=%d partial=%d fail=%d skip=%d) "
            "→ %s",
            self.urls_collected,
            self.urls_after_dedup,
            self.scraped_success,
            self.scraped_partial,
            self.scraped_failed,
            self.scraped_skipped,
            self.output_file,
        )
