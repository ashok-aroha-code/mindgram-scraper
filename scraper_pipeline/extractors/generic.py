"""
extractors/generic.py — A selector-driven extractor for any site.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, Any, Tuple

from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

from bs4 import BeautifulSoup
from scraper_pipeline.extractors.base import BaseExtractor
from scraper_pipeline.models import finalize_record
from scraper_pipeline.utils.dates import normalize_date

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

    def __init__(self, field_map: Dict[str, str], metadata_map: Dict[str, str] = None) -> None:
        self._field_map = field_map
        self._metadata_map = metadata_map or {}

    def extract(self, driver: uc.Chrome) -> Tuple[Dict[str, Any], Dict[str, str]]:
        record: Dict[str, Any] = {}
        missing: Dict[str, str] = {}

        for field, selector in self._field_map.items():
            try:
                val = self._extract_field(driver, selector)
                if val:
                    if field == "date" or field.endswith("_date"):
                        val = normalize_date(val)
                    record[field] = val
                else:
                    missing[field] = "Missing"
            except Exception as exc:
                _log.debug("Failed to extract %s (%s): %s", field, selector, exc)
                missing[field] = "Error"

        # Extract metadata fields
        for field, selector in self._metadata_map.items():
            try:
                val = self._extract_field(driver, selector)
                if val:
                    if field == "date" or field.endswith("_date"):
                        val = normalize_date(val)
                    record[field] = val
                else:
                    missing[field] = "Missing (Metadata)"
            except Exception as exc:
                _log.debug("Failed to extract metadata %s (%s): %s", field, selector, exc)
                missing[field] = "Error (Metadata)"

        # Handle abstract_html and abstract_markdown if abstract selector is present
        if "abstract" in self._field_map:
            abstract_selector = self._field_map["abstract"]
            # Force @innerHTML for the html version
            html_selector = abstract_selector
            if "@" not in html_selector:
                html_selector += "@innerHTML"
            elif not html_selector.endswith("@innerHTML"):
                 # if it has an attribute, we might still want innerHTML of the core element
                 # but usually abstract is a div.
                 parts = html_selector.rsplit("@", 1)
                 html_selector = parts[0] + "@innerHTML"

            html_val = self._extract_field(driver, html_selector)
            if html_val:
                record["abstract_html"] = html_val
                record["abstract_markdown"] = self._html_to_markdown(html_val)

        return finalize_record(record), missing

    def _html_to_markdown(self, html: str) -> str:
        """Convert basic HTML to Markdown using BeautifulSoup."""
        if not html:
            return ""
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Basic tag replacements
        for tag in soup.find_all(["b", "strong"]):
            tag.replace_with(f"**{tag.get_text()}**")
        for tag in soup.find_all(["i", "em"]):
            tag.replace_with(f"*{tag.get_text()}*")
        for tag in soup.find_all("h1"):
            tag.replace_with(f"\n# {tag.get_text()}\n")
        for tag in soup.find_all("h2"):
            tag.replace_with(f"\n## {tag.get_text()}\n")
        for tag in soup.find_all("h3"):
            tag.replace_with(f"\n### {tag.get_text()}\n")
        for tag in soup.find_all("p"):
            tag.replace_with(f"\n{tag.get_text()}\n")
        for tag in soup.find_all("br"):
            tag.replace_with("\n")
        for tag in soup.find_all("a"):
            href = tag.get("href", "")
            tag.replace_with(f"[{tag.get_text()}]({href})")

        return soup.get_text().strip()

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
            attr_lower = attr.lower()
            if attr_lower == "text":
                return el.text.strip()
            if attr_lower == "innerhtml":
                return el.get_attribute("innerHTML").strip()
            if attr_lower == "outerhtml":
                return el.get_attribute("outerHTML").strip()
                
            val = el.get_attribute(attr)
            return val.strip() if val else None
        
        return el.text.strip()
