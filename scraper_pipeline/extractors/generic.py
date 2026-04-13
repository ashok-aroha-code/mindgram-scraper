"""
extractors/generic.py — A selector-driven extractor for any site.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Any, Tuple

from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

from scraper_pipeline.extractors.base import BaseExtractor

if TYPE_CHECKING:
    import undetected_chromedriver as uc

_log = logging.getLogger(__name__)


class GenericExtractor(BaseExtractor):
    """
    Extracts data using a dictionary of field names to CSS/XPath selectors.
    
    Supports:
        - CSS: "h1.title"
        - XPath: "//div[@id='content']"
        - Attributes: "img@src", "a@href"
    """

    def __init__(self, field_map: Dict[str, str]) -> None:
        self._field_map = field_map

    def extract(self, driver: uc.Chrome) -> Tuple[Dict[str, Any], Dict[str, str]]:
        record: Dict[str, Any] = {}
        missing: Dict[str, str] = {}

        for field, selector in self._field_map.items():
            try:
                val = self._extract_field(driver, selector)
                if val:
                    record[field] = val
                else:
                    missing[field] = "Missing"
            except Exception as exc:
                _log.debug("Failed to extract %s (%s): %s", field, selector, exc)
                missing[field] = "Error"

        return record, missing

    def _extract_field(self, driver: uc.Chrome, selector: str) -> str | None:
        """
        Extract text or attribute from an element.
        Format: selector[@attribute]
        Example: "h1.title", "img@src", "//a@href"
        """
        attr = None
        if "@" in selector:
            # Handle formats like "img@src" or "//div[@id='x']@text"
            # We split by the LAST @ if it's not part of an XPath predicate
            parts = selector.rsplit("@", 1)
            # Basic heuristic: if the first part looks like it's missing a closing bracket or quote, 
            # the @ might be inside an XPath predicate.
            if parts[0].count("[") == parts[0].count("]") and parts[0].count("'") % 2 == 0:
                selector = parts[0]
                attr = parts[1]

        # Determine if it's XPath or CSS
        by = By.XPATH if selector.startswith("/") or selector.startswith("(") else By.CSS_SELECTOR
        
        elements = driver.find_elements(by, selector)
        if not elements:
            return None

        el = elements[0]
        if attr:
            if attr.lower() == "text":
                return el.text.strip()
            val = el.get_attribute(attr)
            return val.strip() if val else None
        
        return el.text.strip()
