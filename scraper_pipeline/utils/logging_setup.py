import logging
import logging.handlers
import sys
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    """Adds ANSI color codes to log levels for terminal output."""
    
    # ANSI escape sequences
    GREY = "\x1b[38;20m"
    CYAN = "\x1b[36;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"

    COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: CYAN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, self.RESET)
        # Use a more readable format for levels
        orig_levelname = record.levelname
        record.levelname = f"{log_color}{orig_levelname:8s}{self.RESET}"
        
        # Format names to be fixed width for better alignment
        orig_name = record.name
        record.name = f"{orig_name[:15]:15s}"
        
        result = super().format(record)
        
        # Restore original values to avoid side effects if other handlers use the record
        record.levelname = orig_levelname
        record.name = orig_name
        return result

def setup_logging(
    log_file: Path,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure the 'scraper_pipeline' logger with professional aesthetics.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Clean, modern format
    fmt = "[%(asctime)s] %(levelname)s — %(name)s — %(message)s"
    datefmt = "%H:%M:%S"
    
    # 1. Plain Formatter for File (production style)
    file_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s — %(name)-15s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 2. Colored Formatter for Terminal (human readable)
    console_formatter = ColoredFormatter(fmt, datefmt=datefmt)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(file_formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(console_formatter)

    logger = logging.getLogger("scraper_pipeline")
    
    # Avoid duplicate handlers if setup_logging is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()
        
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False

    return logger
