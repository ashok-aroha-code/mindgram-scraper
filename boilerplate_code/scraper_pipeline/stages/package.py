"""
stages/package.py — Stage 5: meeting metadata packaging.

Wraps the final abstract list in a meeting envelope dict and writes
the deliverable output file.

Input:  numbered_data.json          (list of record dicts)
Output: WCN_2026_Annual_Meeting.json (meeting envelope with abstracts)
"""

from __future__ import annotations

import logging
from pathlib import Path

from scraper_pipeline.config import MeetingConfig
from scraper_pipeline.utils.io import read_json, write_json

_log = logging.getLogger(__name__)


class MeetingWrapper:
    """
    Produces the final deliverable by nesting the abstract list inside
    a meeting metadata envelope.

    Output schema:
        {
            "meeting_name": "WCN 2026 Annual Meeting",
            "date":         "2026-04-01",
            "link":         "https://...",
            "abstracts":    [ { ...record... }, ... ]
        }
    """

    def __init__(self, cfg: MeetingConfig) -> None:
        self._cfg = cfg

    def run(self, input_path: Path, output_path: Path) -> int:
        """
        Wrap abstracts in the meeting envelope and write the final file.

        Args:
            input_path:  numbered_data.json
            output_path: final deliverable (e.g. WCN_2026_Annual_Meeting.json)

        Returns:
            Number of abstracts included.
        """
        abstracts: list[dict] = read_json(input_path)

        envelope = {
            "meeting_name": self._cfg.meeting_name,
            "date": self._cfg.date,
            "link": self._cfg.link,
            "abstracts": abstracts,
        }

        write_json(output_path, envelope)
        _log.info(
            "Packaged %d abstracts for '%s' → %s",
            len(abstracts),
            self._cfg.meeting_name,
            output_path,
        )
