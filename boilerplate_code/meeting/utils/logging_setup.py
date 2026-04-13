"""
utils/logging_setup.py — configure the root 'scraper_pipeline' logger.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


def setup_logging(
    log_file: Path,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure the 'scraper_pipeline' logger with:
      - RotatingFileHandler  — keeps last `backup_count` files at `max_bytes` each
      - StreamHandler        — prints to stdout in real time

    Returns the configured logger.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fmt = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger("scraper_pipeline")
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False

    return logger
