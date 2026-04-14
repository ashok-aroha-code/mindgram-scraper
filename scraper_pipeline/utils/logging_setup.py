import logging
import logging.handlers
import sys
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    """Adds ANSI color codes to log levels for terminal output."""
    
    # ANSI escape sequences
    BLUE = "\x1b[38;5;39m"
    CYAN = "\x1b[36;1m"
    GREEN = "\x1b[32;1m"
    YELLOW = "\x1b[33;1m"
    RED = "\x1b[31;1m"
    BOLD = "\x1b[1m"
    RESET = "\x1b[0m"

    COLORS = {
        logging.DEBUG: (BLUE, "⚙️ "),
        logging.INFO: (CYAN, "ℹ️ "),
        logging.WARNING: (YELLOW, "⚠️ "),
        logging.ERROR: (RED, "❌ "),
        logging.CRITICAL: (RED, "🚨 "),
    }

    def format(self, record):
        log_color, icon = self.COLORS.get(record.levelno, (self.RESET, ""))
        
        # Format: [Time] ICON LEVEL Message
        levelname = f"{log_color}{record.levelname:8s}{self.RESET}"
        
        # We simplify the message for terminal by removing the logger name if it's too noisy
        # or we just make it subtle
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        
        # Build the final string
        s = f"[{record.asctime}] {icon}{log_color}{record.levelname:7s}{self.RESET} — {record.message}"
        
        if record.exc_info:
            # Cache the traceback text to avoid re-generating
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        
        if record.exc_text:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + record.exc_text
        
        if record.stack_info:
            if s[-1:] != "\n":
                s = s + "\n"
            s = s + self.formatStack(record.stack_info)
            
        return s

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

    stream_handler = logging.StreamHandler(
        open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)
    )
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
