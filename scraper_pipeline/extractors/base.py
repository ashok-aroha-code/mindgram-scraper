"""
extractors/base.py — contract for all site-specific extractors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import undetected_chromedriver as uc


class BaseExtractor(ABC):
    """
    Interface every site-specific extractor must implement.

    Engine contract:
        • The page is fully loaded before extract() is called.
        • Do NOT call driver.get() inside extract().
        • Raise any exception to signal failure → engine retries.
        • Return ({}, {}) if the page loaded but contained no data.

    Implementing a new site:
        1. Subclass BaseExtractor.
        2. Implement extract() with your site's XPath/CSS selectors.
        3. Pass an instance to Pipeline or ScraperEngine.
    """

    @abstractmethod
    def extract(self, driver: uc.Chrome) -> tuple[dict, dict]:
        """
        Extract fields from the already-loaded page.

        Args:
            driver: Selenium WebDriver with the target page loaded.

        Returns:
            record  (dict): scraped data. Do NOT set "link" — the engine sets it.
            missing (dict): {field_name: "Missing"} for absent fields.
                            Return {} if every expected field was found.
        """
        ...
