"""
utils/io.py — crash-safe JSON and JSONL file helpers.

Why JSONL for intermediate writes?
    Appending a line to a JSONL file is atomic at the OS level.
    Writing a JSON array requires reading the whole file, modifying it,
    and rewriting it — not safe if the process is killed mid-write.
    All scrape results go to JSONL first; finalize() merges them into
    the pretty JSON array expected downstream.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


def read_json(path: Path) -> Any:
    """Read and return a JSON file. Raises on missing file or bad JSON."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any, indent: int = 4) -> None:
    """Write `data` to a pretty-printed JSON file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    _log.debug(
        "Wrote %s (%d top-level items)",
        path,
        len(data) if hasattr(data, "__len__") else "?",
    )


def append_jsonl(path: Path, record: dict) -> None:
    """
    Append one record as a JSON line to `path`.
    File is created if it doesn't exist; records are never lost on crash.
    """
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        _log.error("JSONL append failed → %s: %s", path, exc)


def jsonl_to_json(src: Path, dst: Path) -> int:
    """
    Merge a JSONL working file into a pretty-printed JSON array at `dst`.
    Skips malformed lines with a warning.

    Returns:
        Number of records written to `dst`.
    """
    records: list[dict] = []
    if src.exists():
        with open(src, encoding="utf-8") as f:
            for lineno, raw in enumerate(f, 1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    _log.warning(
                        "Skipping malformed JSONL line %d in %s: %s", lineno, src, exc
                    )

    if records:
        write_json(dst, records)
        _log.info("Merged %d records: %s → %s", len(records), src.name, dst.name)
    return len(records)
