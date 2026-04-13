"""
extractors/wcn.py — extractor for the WCN 2026 abstract pages.

✏️  To adapt for a different site:
    1. Copy this file, rename the class.
    2. Replace each XPath/CSS selector with the correct one for your site.
    3. Add/remove record fields to match the target schema.
    4. Pass your new extractor class to PipelineConfig or ScraperEngine.

Field pattern:
    try:
        value = driver.find_element(By.XPATH, "//your/xpath").text.strip()
    except NoSuchElementException:
        value = ""
        missing["field_name"] = "Missing"
"""

from __future__ import annotations

import logging

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from .base import BaseExtractor

_log = logging.getLogger(__name__)


class WCNExtractor(BaseExtractor):
    """Extracts abstract data from individual WCN 2026 article pages."""

    # XPaths as class-level constants — easy to update when the site changes
    _XPATH_TITLE = '(//h4[@class="panel-title-text"])[1]'
    _XPATH_SESSION_NAMES = "//p/b"
    _XPATH_SESSION_TOPIC = '//p[@class="trackname innertracks"]'
    _XPATH_TIME = (
        '//div[contains(@class,"date-time-room-div") and .//i[@class="fa fa-clock-o"]]'
    )
    _XPATH_AUTHOR_ROWS = '//div[@class="col-sm-9 col-xs-8"]'
    _XPATH_AUTHOR_NAME = './/span[@class="text-large"]'
    _XPATH_ABSTRACT = (
        '//div[@class="panel-body" and starts-with(normalize-space(.), "Info")]'
    )

    def extract(self, driver: uc.Chrome) -> tuple[dict, dict]:
        missing: dict[str, str] = {}

        # --- Title ------------------------------------------------------------
        try:
            title = (
                driver.find_element(By.XPATH, self._XPATH_TITLE)
                .text.strip()
                .replace("\n", " ")
            )
        except NoSuchElementException:
            title = ""
            missing["title"] = "Missing"

        # --- Session name (multiple <b> tags joined) --------------------------
        try:
            session_name = " ".join(
                el.text.strip().replace("\n", " ")
                for el in driver.find_elements(By.XPATH, self._XPATH_SESSION_NAMES)
            )
        except NoSuchElementException:
            session_name = ""
            missing["session_name"] = "Missing"

        # --- Session topic ----------------------------------------------------
        try:
            session_topic = " ".join(
                el.text.strip().replace("\n", " ")
                for el in driver.find_elements(By.XPATH, self._XPATH_SESSION_TOPIC)
            )
        except NoSuchElementException:
            session_topic = ""
            missing["session_topic"] = "Missing"

        # --- Presentation time ------------------------------------------------
        try:
            presentation_time = (
                driver.find_element(By.XPATH, self._XPATH_TIME)
                .text.strip()
                .replace("\n", " ")
            )
        except NoSuchElementException:
            presentation_time = ""
            missing["presentation_time"] = "Missing"

        # --- Author / affiliation pairs (repeated block) ----------------------
        try:
            parts: list[str] = []
            for row in driver.find_elements(By.XPATH, self._XPATH_AUTHOR_ROWS):
                try:
                    author = (
                        row.find_element(By.XPATH, self._XPATH_AUTHOR_NAME)
                        .text.strip()
                        .replace("\n", " ")
                    )
                    full_text = row.text.strip()
                    affiliation = (
                        full_text.split(author, 1)[-1].strip().lstrip("\n")
                        if author and author in full_text
                        else ""
                    )
                except NoSuchElementException:
                    author = affiliation = ""

                if author or affiliation:
                    parts.append(f"{author}; {affiliation}")

            author_info = ", ".join(parts)
            if not author_info:
                missing["author_info"] = "Missing"
        except NoSuchElementException:
            author_info = ""
            missing["author_info"] = "Missing"

        # --- Abstract (plain text + raw HTML) ---------------------------------
        try:
            el = driver.find_element(By.XPATH, self._XPATH_ABSTRACT)
            abstract = el.text.strip().replace("\n", " ")
            abstract_html = el.get_attribute("outerHTML")
        except NoSuchElementException:
            abstract = abstract_html = ""
            missing["abstract"] = "Missing"

        # --- Build record -----------------------------------------------------
        # "link" is intentionally absent here — the engine sets it.
        record: dict = {
            "link": None,
            "title": title,
            "doi": "",
            "number": "",
            "author_info": author_info,
            "abstract": abstract,
            "abstract_html": abstract_html,
            "abstract_markdown": "",
            "abstract_metadata": {
                "session_name": session_name,
                "session_topic": session_topic,
                "presentation_time": presentation_time,
            },
        }

        if missing:
            _log.debug("Missing fields on this page: %s", list(missing.keys()))

        return record, missing
