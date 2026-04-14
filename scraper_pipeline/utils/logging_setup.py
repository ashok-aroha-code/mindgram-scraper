import logging
import logging.handlers
import sys
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console

def setup_logging(
    log_file: Path,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure logging with Rich for terminal and standard rotating files for storage.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Plain Formatter for File (production style)
    file_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s — %(name)-15s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)

    # 2. Rich Handler for Console (premium aesthetics)
    # We use a custom console to ensure encoding is handled correctly
    console = Console(force_terminal=True, color_system="auto")
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=True,
        omit_repeated_times=True,
        markup=True
    )
    # Customize the format for Rich (it handles levels/time itself)
    rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="%H:%M:%S"))

    logger = logging.getLogger("scraper_pipeline")
    
    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(rich_handler)
    logger.propagate = False

    return logger
