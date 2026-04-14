"""
utils/dates.py — Date normalization and formatting.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

_log = logging.getLogger(__name__)

# Target formats
FORMAT_ISO = "%Y-%m-%d"
FORMAT_FULL = "%A, %B %d, %Y"

def normalize_date(date_str: str, target_format: str = FORMAT_ISO) -> str:
    """
    Attempt to parse a date string and normalize it to the target format.
    If parsing fails, returns the original string.
    """
    if not date_str or date_str == "-":
        return date_str

    # Clean up common noise
    clean_str = re.sub(r'\s+', ' ', date_str.strip())
    
    # Try common formats
    formats_to_try = [
        "%Y-%m-%d",
        "%d %B %Y",
        "%B %d, %Y",
        "%A, %B %d, %Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
    ]

    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(clean_str, fmt)
            return dt.strftime(target_format)
        except ValueError:
            continue

    # Try a few more complex patterns with regex if needed
    # For now, if no format matches, return as is.
    _log.debug("Could not normalize date: %s", date_str)
    return date_str
